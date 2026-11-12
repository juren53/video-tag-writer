"""
Video Tag Writer - VideoPanel widget (cover art / poster frame + technical info).

The VTW counterpart of ATW's AudioPanel.  The image area shows, in priority order:
  1. embedded MP4 cover art ('covr' atom), or
  2. a poster frame extracted with ffmpeg (on a worker thread, so arrow-key
     navigation stays responsive), or
  3. a placeholder.
"""

import html
import logging
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QSizePolicy,
    QPushButton, QMessageBox, QFileDialog, QMainWindow,
)
from PyQt6.QtCore import Qt, QUrl, QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtGui import QPixmap, QDesktopServices

from ..config import config
from ..exiftool_utils import (
    ExifToolError, read_cover_art, write_cover_art, remove_cover_art, uses_sidecar,
    sidecar_path_for,
)
from ..video_utils import extract_poster_frame

logger = logging.getLogger(__name__)

_IMG_W, _IMG_H = 320, 200

_IMAGE_FILTER = "Image Files (*.jpg *.jpeg *.png);;All Files (*)"


class _PosterSignals(QObject):
    done = pyqtSignal(str, bytes)   # (path, png bytes — empty on failure)


class _PosterTask(QRunnable):
    def __init__(self, path: str, duration: float):
        super().__init__()
        self.path, self.duration = path, duration
        self.signals = _PosterSignals()

    def run(self):
        data = extract_poster_frame(self.path, self.duration) or b''
        try:
            self.signals.done.emit(self.path, data)
        except RuntimeError:
            pass  # receiver already gone (app closing)


class VideoPanel(QWidget):
    """Right-column panel: image, storage status, actions, technical info."""

    def __init__(self, metadata_manager=None, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._metadata_manager = metadata_manager
        self._current_path = None
        self._duration = 0.0
        self._pool = QThreadPool.globalInstance()
        self._tasks = []
        self._setup_ui()

    # -- UI ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Sunken)
        frame.setFixedSize(_IMG_W + 4, _IMG_H + 4)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(2, 2, 2, 2)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setFixedSize(_IMG_W, _IMG_H)
        fl.addWidget(self._image_label)
        layout.addWidget(frame, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._image_caption = QLabel()
        self._image_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_caption.setStyleSheet("font-size: 8pt; color: grey;")
        layout.addWidget(self._image_caption)

        art_row = QHBoxLayout()
        self._set_art_button = QPushButton("Set Cover Art…")
        self._set_art_button.setToolTip("Embed an image as MP4 cover art")
        self._set_art_button.clicked.connect(self.on_set_cover_art)
        art_row.addWidget(self._set_art_button)
        self._remove_art_button = QPushButton("Remove Art")
        self._remove_art_button.setToolTip("Remove embedded MP4 cover art")
        self._remove_art_button.clicked.connect(self.on_remove_cover_art)
        art_row.addWidget(self._remove_art_button)
        layout.addLayout(art_row)

        play_row = QHBoxLayout()
        self._play_button = QPushButton("▶  Play")
        self._play_button.setToolTip("Open in the system video player")
        self._play_button.clicked.connect(self._on_play)
        play_row.addWidget(self._play_button)
        self._folder_button = QPushButton("Show in Folder")
        self._folder_button.setToolTip("Open the containing folder")
        self._folder_button.clicked.connect(self._on_show_folder)
        play_row.addWidget(self._folder_button)
        layout.addLayout(play_row)

        self._storage_label = QLabel()
        self._storage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._storage_label.setWordWrap(True)
        self._storage_label.setStyleSheet("font-size: 8pt;")
        layout.addWidget(self._storage_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        info_widget = QWidget()
        il = QVBoxLayout(info_widget)
        il.setContentsMargins(4, 4, 4, 4)
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._info_label.setTextFormat(Qt.TextFormat.RichText)
        self._info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        il.addWidget(self._info_label)
        il.addStretch()
        scroll.setWidget(info_widget)
        layout.addWidget(scroll, 1)

        self.clear()

    # -- public API ----------------------------------------------------------

    def display_video(self, path: str, info: dict):
        self._current_path = path
        self._duration = float(info.get('duration_secs') or 0.0)
        embedded = not uses_sidecar(path)
        self._play_button.setEnabled(True)
        self._folder_button.setEnabled(True)
        self._set_art_button.setEnabled(embedded)
        self._update_storage(path)
        self._update_image()
        self._info_label.setText(self._build_info_html(info))

    def clear(self):
        self._current_path = None
        for b in (self._play_button, self._folder_button, self._set_art_button, self._remove_art_button):
            b.setEnabled(False)
        self._show_placeholder("No file loaded")
        self._storage_label.setText("")
        self._info_label.setText(self._build_info_html({}))

    # -- image ---------------------------------------------------------------

    def _show_pixmap(self, pixmap: QPixmap, caption: str):
        scaled = pixmap.scaled(_IMG_W, _IMG_H, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self._image_label.setStyleSheet("")
        self._image_label.setPixmap(scaled)
        self._image_caption.setText(caption)

    def _show_placeholder(self, caption: str):
        self._image_label.clear()
        self._image_label.setText("🎞")
        self._image_label.setStyleSheet("font-size: 64pt; color: #aaaaaa; background: #f0f0f0;")
        self._image_caption.setText(caption)

    def _update_image(self):
        path = self._current_path
        art = read_cover_art(path) if path and not uses_sidecar(path) else None
        if art:
            pm = QPixmap()
            if pm.loadFromData(art):
                self._show_pixmap(pm, "●  Cover art embedded")
                self._remove_art_button.setEnabled(True)
                return
        self._remove_art_button.setEnabled(False)

        if not config.show_poster_frame:
            self._show_placeholder("Poster frame off  (View ▸ Show Poster Frame)")
            return
        self._show_placeholder("Extracting poster frame…")
        task = _PosterTask(path, self._duration)
        task.signals.done.connect(self._on_poster_ready)
        self._tasks.append(task)  # keep signals object alive until done
        self._pool.start(task)

    def _on_poster_ready(self, path: str, data: bytes):
        self._tasks = [t for t in self._tasks if t.path != path]
        if path != self._current_path:
            return  # user already moved on to another file
        pm = QPixmap()
        if data and pm.loadFromData(data):
            self._show_pixmap(pm, "○  Poster frame (no cover art)")
        else:
            self._show_placeholder("No preview  (ffmpeg not found or frame unreadable)")

    # -- storage -------------------------------------------------------------

    def _update_storage(self, path: str):
        if uses_sidecar(path):
            sc = sidecar_path_for(path)
            if os.path.isfile(sc):
                self._storage_label.setText(f"●  Metadata: XMP sidecar  {os.path.basename(sc)}")
                self._storage_label.setStyleSheet("font-size: 8pt; color: green;")
            else:
                self._storage_label.setText("○  No sidecar yet — created on first save")
                self._storage_label.setStyleSheet("font-size: 8pt; color: grey;")
        else:
            self._storage_label.setText("●  Metadata: embedded in file")
            self._storage_label.setStyleSheet("font-size: 8pt; color: green;")

    # -- actions -------------------------------------------------------------

    def _on_play(self):
        if self._current_path and os.path.isfile(self._current_path):
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(self._current_path)):
                QMessageBox.warning(self, "Playback Error",
                                    f"Could not open the file with the system player:\n{self._current_path}")

    def _on_show_folder(self):
        if self._current_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self._current_path)))

    def on_set_cover_art(self):
        path = self._current_path
        if not path:
            return
        if uses_sidecar(path):
            QMessageBox.information(self, "Cover Art",
                                    "Cover art can only be embedded in MP4/M4V files.")
            return
        image, _ = QFileDialog.getOpenFileName(self, "Select Cover Art", os.path.dirname(path), _IMAGE_FILTER)
        if not image:
            return
        try:
            write_cover_art(path, image, keep_backup=config.keep_backup)
        except ExifToolError as e:
            QMessageBox.critical(self, "Cover Art Error", str(e))
            return
        self._update_image()
        self._set_main_status(f"Cover art set  —  {os.path.basename(path)}")

    def on_remove_cover_art(self):
        path = self._current_path
        if not path or uses_sidecar(path):
            return
        try:
            remove_cover_art(path, keep_backup=config.keep_backup)
        except ExifToolError as e:
            QMessageBox.critical(self, "Cover Art Error", str(e))
            return
        self._update_image()
        self._set_main_status(f"Cover art removed  —  {os.path.basename(path)}")

    def _set_main_status(self, message: str):
        main = self.window()
        if isinstance(main, QMainWindow) and hasattr(main, 'set_status'):
            main.set_status(message)

    # -- info table ----------------------------------------------------------

    @staticmethod
    def _build_info_html(info: dict) -> str:
        def row(label, key, always=True):
            val = info.get(key, '--')
            if not always and val in ('--', '', None):
                return ''
            return (f"<tr><td style='font-weight:bold; padding-right:8px; white-space:nowrap;'>"
                    f"{label}:</td><td>{html.escape(str(val))}</td></tr>")

        def section(title):
            return f"<tr><td colspan='2' style='padding-top:6px; color:grey;'>{title}</td></tr>"

        return (
            f"<b>{html.escape(info.get('filename', '--'))}</b>"
            "<table style='margin-top:6px; border-spacing:2px 3px;'>"
            + row('Container', 'format') + row('Duration', 'duration')
            + row('Overall Bitrate', 'overall_bitrate')
            + section('Video')
            + row('Codec', 'video_codec') + row('Resolution', 'resolution')
            + row('Aspect Ratio', 'aspect_ratio', False) + row('Frame Rate', 'frame_rate')
            + row('Scan Type', 'scan_type', False) + row('Bitrate', 'video_bitrate', False)
            + section('Audio')
            + row('Codec', 'audio_codec') + row('Sample Rate', 'sample_rate')
            + row('Channels', 'channels') + row('Bitrate', 'audio_bitrate', False)
            + section('File')
            + row('Size', 'file_size') + row('Modified', 'modified')
            + row('Metadata', 'metadata_storage') + row('Info Source', 'info_source', False)
            + "</table>"
        )
