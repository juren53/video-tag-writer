"""
Video Tag Writer - MenuMixin: create_menu_bar() and create_toolbar().
"""

from PyQt6.QtWidgets import QToolBar, QLabel, QComboBox
from PyQt6.QtGui import QAction, QKeySequence

from .config import config


class MenuMixin:
    """Mixin providing the full menu bar and toolbar."""

    def _action(self, text, slot, shortcut=None, tip=None, checkable=False, checked=False):
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        if tip:
            act.setToolTip(tip)
            act.setStatusTip(tip)
        if checkable:
            act.setCheckable(True)
            act.setChecked(checked)
        act.triggered.connect(slot)
        return act

    def create_menu_bar(self):
        mb = self.menuBar()

        # ── File ──────────────────────────────────────────────────────
        m = mb.addMenu("&File")
        m.addAction(self._action("&Open…", self.on_open, "Ctrl+O"))
        m.addAction(self._action("Open &Directory…", self.on_open_directory))
        m.addSeparator()
        self.recent_menu = m.addMenu("Recent &Files")
        self.recent_directories_menu = m.addMenu("Recent &Directories")
        self.update_recent_menu()
        self.update_recent_directories_menu()
        m.addSeparator()
        m.addAction(self._action("&Save Metadata", self.on_save, "Ctrl+S",
                                 "Write metadata into the MP4, or into the XMP sidecar for MPG/MPEG"))
        m.addSeparator()
        m.addAction(self._action("&Export Metadata to JSON…", self.on_export))
        m.addAction(self._action("&Import Metadata from JSON…", self.on_import))
        m.addSeparator()
        m.addAction(self._action("&Quit", self.close, "Ctrl+Q"))

        # ── Edit ──────────────────────────────────────────────────────
        m = mb.addMenu("&Edit")
        m.addAction(self._action("&Clear Fields", self.on_clear, "Ctrl+L"))
        m.addSeparator()
        m.addAction(self._action("&Rename File…", self.on_rename_file, "F2",
                                 "Rename the video (and its XMP sidecar)"))
        m.addSeparator()
        m.addAction(self._action("Copy &FQFN to Clipboard", self.on_copy_path, "Ctrl+Shift+C",
                                 "Copy the fully qualified file name to the clipboard"))

        # ── View ──────────────────────────────────────────────────────
        m = mb.addMenu("&View")
        m.addAction(self._action("&Refresh", self.on_refresh, "F5"))
        m.addSeparator()
        m.addAction(self._action("&View All Tags…", self.on_view_all_tags, "Ctrl+T"))
        self.poster_action = self._action(
            "Show &Poster Frame", self.on_toggle_poster_frame,
            tip="Extract a frame with ffmpeg when a file is loaded",
            checkable=True, checked=config.show_poster_frame)
        m.addAction(self.poster_action)
        m.addSeparator()
        self.dark_mode_action = self._action("Toggle &Dark Mode", self.on_toggle_dark_mode, "Ctrl+D",
                                             checkable=True, checked=getattr(self, 'dark_mode', False))
        m.addAction(self.dark_mode_action)
        m.addAction(self._action("Select &Theme…", self.on_select_theme))
        m.addSeparator()
        m.addAction(self._action("Zoom &In", lambda: self.zoom_ui(0.1), "Ctrl++"))
        m.addAction(self._action("Zoom &Out", lambda: self.zoom_ui(-0.1), "Ctrl+-"))
        m.addAction(self._action("&Reset Zoom", self.reset_zoom, "Ctrl+0"))
        m.addSeparator()
        self.auto_detect_action = self._action(
            "&Auto-detect Mode on Load", self.on_toggle_auto_detect,
            tip="Automatically switch the metadata mode when opening a file",
            checkable=True, checked=config.auto_detect_mode)
        self.auto_detect_action.setIconText("Auto Detect")
        m.addAction(self.auto_detect_action)

        # ── Tools ─────────────────────────────────────────────────────
        m = mb.addMenu("&Tools")
        m.addAction(self._action("&Set Cover Art…", self.on_set_cover_art, "Ctrl+Shift+A",
                                 "Embed an image as MP4 cover art"))
        m.addAction(self._action("&Remove Cover Art", self.on_remove_cover_art,
                                 tip="Remove embedded MP4 cover art"))
        m.addSeparator()
        m.addAction(self._action("&Manage Modes…", self.on_manage_modes,
                                 tip="Add, rename, reorder or delete metadata modes"))
        m.addSeparator()
        self.keep_backup_action = self._action(
            "&Keep Backup on Save (*_original)", self.on_toggle_keep_backup,
            tip="Let ExifTool keep a '<file>_original' copy each time metadata is written",
            checkable=True, checked=config.keep_backup)
        m.addAction(self.keep_backup_action)
        m.addAction(self._action("Tool &Locations…", self.on_tool_locations,
                                 tip="Show which ExifTool / ffmpeg / ffprobe are in use"))

        # ── Help ──────────────────────────────────────────────────────
        m = mb.addMenu("&Help")
        m.addAction(self._action("&README…", self.on_readme))
        m.addAction(self._action("&Changelog…", self.on_changelog))
        m.addAction(self._action("&Issue Log…", self.on_issue_log,
                                 tip="Open the GitHub issue tracker in your browser"))
        m.addSeparator()
        m.addAction(self._action("&About…", self.on_about))

    def create_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction(self._action("◀  Prev", self.on_previous, tip="Previous file in directory  (↑)"))
        tb.addAction(self._action("Open", self.on_open, tip="Open video file  (Ctrl+O)"))
        tb.addAction(self._action("Next  ▶", self.on_next, tip="Next file in directory  (↓)"))
        tb.addSeparator()
        tb.addAction(self._action("Save", self.on_save, tip="Save metadata  (Ctrl+S)"))
        tb.addSeparator()
        tb.addAction(self._action("Export JSON", self.on_export, tip="Export metadata to JSON"))
        tb.addAction(self._action("Import JSON", self.on_import, tip="Import metadata from JSON"))
        tb.addSeparator()
        tb.addAction(self._action("View Tags", self.on_view_all_tags, tip="View all raw tags  (Ctrl+T)"))
        tb.addSeparator()

        tb.addWidget(QLabel("  Mode: "))
        self.mode_combo = QComboBox()
        self.mode_combo.setToolTip("Switch metadata field set")
        self.mode_combo.setMinimumWidth(160)
        self.mode_combo.addItems(list(config.modes.keys()))
        self.mode_combo.setCurrentText(config.get_active_mode())
        self.mode_combo.currentTextChanged.connect(self.on_switch_mode)
        tb.addWidget(self.mode_combo)
        tb.addAction(self.auto_detect_action)
        tb.addSeparator()

        tb.addAction(self._action("−", lambda: self.zoom_ui(-0.1), tip="Zoom out  (Ctrl+−)"))
        self.zoom_label = QLabel("  100%")
        self.zoom_label.setMinimumWidth(44)
        tb.addWidget(self.zoom_label)
        tb.addAction(self._action("+", lambda: self.zoom_ui(0.1), tip="Zoom in  (Ctrl++)"))
        tb.addSeparator()

        self._toolbar_file_label = QLabel("  No file loaded")
        tb.addWidget(self._toolbar_file_label)

    def _update_toolbar_label(self, text: str):
        if hasattr(self, '_toolbar_file_label'):
            self._toolbar_file_label.setText(f"  {text}")
