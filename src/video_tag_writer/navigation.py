"""
Video Tag Writer - NavigationMixin: open, prev/next, load_file, recent menus.
"""

import os
import logging

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QApplication
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from .config import config
from .file_utils import get_video_files
from .constants import APP_NAME, APP_VERSION
from .exiftool_utils import read_metadata, detect_mode, ExifToolError
from .video_utils import get_video_info

logger = logging.getLogger(__name__)

_VIDEO_FILTER = (
    "Video Files (*.mp4 *.m4v *.mpg *.mpeg);;"
    "MP4 Files (*.mp4 *.m4v);;"
    "MPEG Files (*.mpg *.mpeg);;"
    "All Files (*)"
)


class NavigationMixin:
    """Mixin providing file open, prev/next navigation, and recent file/dir menus."""

    # -- open ---------------------------------------------------------------

    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video File",
            config.last_directory or os.path.expanduser("~"),
            _VIDEO_FILTER,
        )
        if path:
            self.load_file(path)

    def on_open_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Open Directory", config.last_directory or os.path.expanduser("~"),
        )
        if directory:
            self.open_directory(directory)

    def open_directory(self, directory: str):
        if not os.path.isdir(directory):
            QMessageBox.warning(self, "Directory Not Found", f"Directory not found:\n{directory}")
            return
        files = get_video_files(directory)
        if not files:
            QMessageBox.information(self, "No Video Files",
                                    f"No MP4/MPG/MPEG files found in:\n{directory}")
            return
        self.load_file(files[0])

    # -- prev / next --------------------------------------------------------

    def on_previous(self):
        if not config.directory_video_files:
            self.set_status("No video files in directory")
            return
        if config.current_file_index <= 0:
            config.current_file_index = len(config.directory_video_files) - 1
        else:
            config.current_file_index -= 1
        self.load_file(config.directory_video_files[config.current_file_index])

    def on_next(self):
        if not config.directory_video_files:
            self.set_status("No video files in directory")
            return
        if config.current_file_index >= len(config.directory_video_files) - 1:
            config.current_file_index = 0
        else:
            config.current_file_index += 1
        self.load_file(config.directory_video_files[config.current_file_index])

    # -- load ---------------------------------------------------------------

    def _auto_detect_mode(self, tags) -> bool:
        """Switch mode based on tag content if auto-detect is enabled. Returns True if switched."""
        if not config.auto_detect_mode:
            return False
        detected = detect_mode(tags, config.mode_detect_frames, config.mode_detect_default)
        if detected == config.get_active_mode() or detected not in config.modes:
            return False
        config.set_active_mode(detected)
        self.metadata_manager.reload_mode(detected)
        self.metadata_panel.rebuild_fields()
        if hasattr(self, 'mode_combo'):
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentText(detected)
            self.mode_combo.blockSignals(False)
        return True

    def load_file(self, path: str):
        """Load a video file: update config, scan directory, populate panels."""
        if not os.path.isfile(path):
            QMessageBox.warning(self, "File Not Found", f"File not found:\n{path}")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        filename = os.path.basename(path)
        self.set_status(f"Loading  {filename}…")
        QApplication.processEvents()

        try:
            config.selected_file = path
            config.last_directory = os.path.dirname(path)
            config.add_recent_file(path)

            directory = os.path.dirname(path)
            config.directory_video_files = get_video_files(directory)
            try:
                config.current_file_index = config.directory_video_files.index(path)
            except ValueError:
                norm = os.path.normcase(os.path.abspath(path))
                config.current_file_index = next(
                    (i for i, p in enumerate(config.directory_video_files)
                     if os.path.normcase(os.path.abspath(p)) == norm), -1)

            config.add_recent_directory(directory)
            self.update_recent_directories_menu()
            self.update_recent_menu()

            # One ExifTool read — reused for detection, fields and technical fallback
            read_error = None
            try:
                file_tags, sidecar_tags = read_metadata(path)
            except ExifToolError as e:
                read_error = str(e)
                file_tags, sidecar_tags = {}, None
            field_tags = sidecar_tags if sidecar_tags is not None else file_tags

            self._auto_detect_mode(field_tags)

            info = get_video_info(path, file_tags)

            self.metadata_manager.load_from_tags(path, field_tags)
            self.metadata_panel.set_sidecar_mode(sidecar_tags is not None)
            self.metadata_panel.update_from_manager()

            self.video_panel.display_video(path, info)

            self.setWindowTitle(f"{APP_NAME}  —  {filename}  v{APP_VERSION}")

            idx = config.current_file_index
            total = len(config.directory_video_files)
            pos = f"  [{idx + 1}/{total}]" if idx >= 0 else ""
            status = f"{filename}  ·  {info.get('format', '')}  ·  {info.get('file_size', '')}{pos}"
            if sidecar_tags is not None:
                status += "  ·  XMP sidecar" if sidecar_tags else "  ·  no sidecar yet"
            if read_error:
                status += "  (metadata read failed)"
            self.set_status(status)

            if read_error:
                QMessageBox.warning(self, "Metadata Read Error", read_error)
            logger.info(f"Loaded: {path}")
        finally:
            QApplication.restoreOverrideCursor()

    # -- refresh / clear ----------------------------------------------------

    def on_refresh(self):
        if config.selected_file and os.path.isfile(config.selected_file):
            self.load_file(config.selected_file)
        else:
            self.set_status("No file to refresh")

    def on_clear(self):
        self.metadata_manager.clear()
        self.metadata_panel.update_from_manager()
        self.set_status("Fields cleared")

    def on_copy_path(self):
        if config.selected_file:
            QApplication.clipboard().setText(config.selected_file)
            self.set_status(f"Copied FQFN to clipboard:  {config.selected_file}")

    # -- recent menus -------------------------------------------------------

    def update_recent_menu(self):
        if not hasattr(self, 'recent_menu'):
            return
        self.recent_menu.clear()
        valid = [f for f in config.recent_files if os.path.isfile(f)]
        if not valid:
            act = QAction("No recent files", self)
            act.setEnabled(False)
            self.recent_menu.addAction(act)
            return
        for i, fp in enumerate(valid):
            act = QAction(f"{i + 1}:  {os.path.basename(fp)}", self)
            act.setToolTip(fp)
            act.triggered.connect(lambda checked=False, p=fp: self.load_file(p))
            self.recent_menu.addAction(act)
        self.recent_menu.addSeparator()
        clear_act = QAction("Clear Recent Files", self)
        clear_act.triggered.connect(self.on_clear_recent)
        self.recent_menu.addAction(clear_act)

    def update_recent_directories_menu(self):
        if not hasattr(self, 'recent_directories_menu'):
            return
        self.recent_directories_menu.clear()
        valid = [d for d in config.recent_directories if os.path.isdir(d)]
        if not valid:
            act = QAction("No recent directories", self)
            act.setEnabled(False)
            self.recent_directories_menu.addAction(act)
            return
        for i, dp in enumerate(valid):
            act = QAction(f"{i + 1}:  {dp}", self)
            act.triggered.connect(lambda checked=False, p=dp: self.open_directory(p))
            self.recent_directories_menu.addAction(act)
        self.recent_directories_menu.addSeparator()
        clear_act = QAction("Clear Recent Directories", self)
        clear_act.triggered.connect(self.on_clear_recent_directories)
        self.recent_directories_menu.addAction(clear_act)

    def on_clear_recent(self):
        config.recent_files = []
        config.save_config()
        self.update_recent_menu()
        self.set_status("Recent files cleared")

    def on_clear_recent_directories(self):
        config.recent_directories = []
        config.save_config()
        self.update_recent_directories_menu()
        self.set_status("Recent directories cleared")
