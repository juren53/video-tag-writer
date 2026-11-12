"""
VideoTagWriter - FileOpsMixin: save, export/import, rename, view-all-tags, modes.
"""

import os
import logging

from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QLabel, QPushButton, QAbstractItemView, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer

from .config import config
from .constants import VIDEO_EXTENSIONS
from .exiftool_utils import (
    ExifToolError, read_all_tags_listing, uses_sidecar, sidecar_path_for, exiftool_info,
)

logger = logging.getLogger(__name__)

_JSON_FILTER = "JSON Files (*.json);;All Files (*)"


class FileOpsMixin:
    """Mixin for MainWindow: save, export/import JSON, rename, view all tags, modes."""

    def _require_file(self) -> bool:
        if not config.selected_file:
            QMessageBox.warning(self, "No File", "Please open a video file first.")
            return False
        return True

    # -- save ---------------------------------------------------------------

    def on_save(self):
        if not self._require_file():
            return
        self.metadata_panel.update_manager_from_ui()
        path = config.selected_file

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            plan = self.metadata_manager.save_to_file(path)
        except ValueError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Invalid Values", str(e))
            return
        except ExifToolError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Save Error", str(e))
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.exception("Unexpected save error")
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred:\n{e}")
            return
        QApplication.restoreOverrideCursor()

        where = os.path.basename(plan.target)
        msg = f"Saved  {where}" + ("  (XMP sidecar)" if plan.sidecar else "")
        if plan.empty:
            msg = "Nothing to save — all fields empty and no sidecar exists"
        self.set_status(msg)

        if plan.skipped:
            QMessageBox.information(
                self, "Some Fields Not Saved",
                "MPG/MPEG metadata is stored in an XMP sidecar, which can only hold XMP tags.\n"
                "These fields have no XMP tag in the current mode and were not saved:\n\n  • "
                + "\n  • ".join(plan.skipped),
            )
        # Refresh panels so storage status (e.g. a newly created sidecar) is current
        self._reload_keep_mode(path)
        self.set_status(msg)

    def _reload_keep_mode(self, path: str):
        """Reload path without letting auto-detect change the current mode."""
        auto = config.auto_detect_mode
        config.auto_detect_mode = False
        try:
            self.load_file(path)
        finally:
            config.auto_detect_mode = auto

    # -- export / import ----------------------------------------------------

    def on_export(self):
        if not self._require_file():
            return
        self.metadata_panel.update_manager_from_ui()
        default_name = os.path.splitext(os.path.basename(config.selected_file))[0] + "_metadata.json"
        start_path = os.path.join(config.last_directory or os.path.expanduser("~"), default_name)
        path, _ = QFileDialog.getSaveFileName(self, "Export Metadata as JSON", start_path, _JSON_FILTER)
        if not path:
            return
        if self.metadata_manager.export_to_json(path):
            self.set_status(f"Exported  {os.path.basename(path)}")
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export metadata.")

    def on_import(self):
        if not self._require_file():
            return
        start_dir = config.last_directory or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Import Metadata from JSON", start_dir, _JSON_FILTER)
        if not path:
            return
        if self.metadata_manager.import_from_json(path):
            self.metadata_panel.update_from_manager()
            self.set_status(f"Imported  {os.path.basename(path)}  (not yet saved)")
        else:
            QMessageBox.critical(self, "Import Error", "Failed to import metadata.")

    # -- rename -------------------------------------------------------------

    def _ask_new_filename(self, current_filename: str) -> str:
        """Modal rename prompt; arrow keys go to the line edit, not file navigation."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Rename File")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Enter new filename:"))
        line_edit = QLineEdit(current_filename)
        layout.addWidget(line_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Pre-select the stem so typing replaces the name but keeps the extension
        stem_len = len(os.path.splitext(current_filename)[0])
        QTimer.singleShot(50, lambda: (line_edit.setFocus(), line_edit.setSelection(0, stem_len)))

        QApplication.instance().removeEventFilter(self)
        try:
            ok = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            QApplication.instance().installEventFilter(self)
        return line_edit.text().strip() if ok else ''

    def on_rename_file(self):
        """Rename the current video (and its XMP sidecar, if any) in place."""
        if not self._require_file():
            return
        old_path = config.selected_file
        current_filename = os.path.basename(old_path)
        directory = os.path.dirname(old_path)

        new_filename = os.path.basename(self._ask_new_filename(current_filename))
        if not new_filename or new_filename == current_filename:
            return
        if new_filename in ('.', '..') or '\x00' in new_filename:
            QMessageBox.warning(self, "Invalid Filename", "The filename is invalid.")
            return

        new_ext = os.path.splitext(new_filename)[1].lower()
        if new_ext not in VIDEO_EXTENSIONS:
            reply = QMessageBox.question(
                self, "Extension Changed",
                f'"{new_ext}" is not a supported video extension (MP4, M4V, MPG, MPEG).\nRename anyway?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        new_path = os.path.join(directory, new_filename)
        if os.path.exists(new_path) and os.path.normcase(new_path) != os.path.normcase(old_path):
            QMessageBox.warning(self, "File Exists",
                                f'A file named "{new_filename}" already exists.\nChoose another name.')
            return

        old_sidecar = sidecar_path_for(old_path) if uses_sidecar(old_path) else None
        new_sidecar = sidecar_path_for(new_path)
        move_sidecar = bool(old_sidecar and os.path.isfile(old_sidecar))
        if move_sidecar and os.path.exists(new_sidecar):
            QMessageBox.warning(self, "Sidecar Exists",
                                f'A sidecar named "{os.path.basename(new_sidecar)}" already exists.\n'
                                'Choose another name.')
            return

        # os.rename within one directory is atomic, so — unlike ATW — no full-file backup
        # copy is made (video files can be many GB).
        try:
            os.rename(old_path, new_path)
        except OSError as e:
            QMessageBox.critical(self, "Rename Error", f"Failed to rename file:\n{e}")
            return
        if move_sidecar:
            try:
                os.rename(old_sidecar, new_sidecar)
            except OSError as e:
                QMessageBox.warning(self, "Sidecar Not Renamed",
                                    f"The video was renamed, but its sidecar could not be:\n{e}\n\n"
                                    f"Sidecar is still at:\n{old_sidecar}")

        config.selected_file = new_path
        self.load_file(new_path)
        extra = f"  (+ {os.path.basename(new_sidecar)})" if move_sidecar else ""
        self.set_status(f"Renamed to  {new_filename}{extra}")

    # -- cover art ----------------------------------------------------------

    def on_set_cover_art(self):
        if self._require_file():
            self.video_panel.on_set_cover_art()

    def on_remove_cover_art(self):
        if self._require_file():
            self.video_panel.on_remove_cover_art()

    # -- view all tags ------------------------------------------------------

    def on_view_all_tags(self):
        if not self._require_file():
            return
        path = config.selected_file
        try:
            rows = read_all_tags_listing(path)
            if uses_sidecar(path) and os.path.isfile(sidecar_path_for(path)):
                rows += [(f"Sidecar · {g}", t, v)
                         for g, t, v in read_all_tags_listing(sidecar_path_for(path))]
        except ExifToolError as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        AllTagsDialog(path, rows, parent=self).exec()

    # -- settings toggles ---------------------------------------------------

    def on_toggle_keep_backup(self, checked: bool):
        config.keep_backup = checked
        config.save_config()
        self.set_status("ExifTool backups (*_original) " + ("enabled" if checked else "disabled"))

    def on_toggle_poster_frame(self, checked: bool):
        config.show_poster_frame = checked
        config.save_config()
        self.on_refresh()

    def on_tool_locations(self):
        """Show which ExifTool / ffmpeg / ffprobe binaries are in use."""
        from .video_utils import ff_tool_versions
        et_path, et_ver = exiftool_info()
        lines = [f"ExifTool:  {et_ver or 'NOT FOUND'}", f"    {et_path or '-'}", ""]
        for name, (exe, ver) in ff_tool_versions().items():
            lines += [f"{name}:  {ver}", f"    {exe or '-'}", ""]
        lines.append(f"Configuration file:\n    {config.config_file}")
        dlg = QDialog(self)
        dlg.setWindowTitle("Tool Locations")
        dlg.resize(640, 320)
        lay = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(lines))
        lay.addWidget(text)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    # -- modes --------------------------------------------------------------

    def on_switch_mode(self, mode_name: str):
        if not mode_name or mode_name == config.get_active_mode():
            return
        if self._has_unsaved_edits():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "There are unsaved edits in the current form.\nSwitch mode and discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                self.mode_combo.blockSignals(True)
                self.mode_combo.setCurrentText(config.get_active_mode())
                self.mode_combo.blockSignals(False)
                return
        config.set_active_mode(mode_name)
        self.metadata_manager.reload_mode(mode_name)
        self.metadata_panel.rebuild_fields()
        if config.selected_file and os.path.isfile(config.selected_file):
            self._reload_keep_mode(config.selected_file)  # keep the manually chosen mode
        else:
            self.set_status(f"Mode: {mode_name}")

    def _has_unsaved_edits(self) -> bool:
        return self.metadata_panel.has_unsaved_edits()

    def on_toggle_auto_detect(self, checked: bool):
        config.auto_detect_mode = checked
        config.save_config()
        self.set_status(f"Auto-detect mode {'enabled' if checked else 'disabled'}")

    def on_manage_modes(self):
        from .widgets.manage_modes_dialog import ManageModesDialog
        dlg = ManageModesDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_modes, new_active, new_detect_frames, new_detect_default = dlg.get_result()
        config.modes = new_modes
        config.active_mode = new_active
        config.mode_detect_frames = new_detect_frames
        config.mode_detect_default = new_detect_default
        config.save_config()

        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        self.mode_combo.addItems(list(config.modes.keys()))
        self.mode_combo.setCurrentText(config.get_active_mode())
        self.mode_combo.blockSignals(False)

        self.metadata_manager.reload_mode(config.get_active_mode())
        self.metadata_panel.rebuild_fields()
        if config.selected_file and os.path.isfile(config.selected_file):
            self.load_file(config.selected_file)
        else:
            self.set_status(f"Modes updated  —  Active: {config.get_active_mode()}")


class AllTagsDialog(QDialog):
    """Searchable table of every ExifTool tag (duplicates included) in the open file."""

    def __init__(self, path, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"All Tags — {os.path.basename(path)}")
        self.resize(860, 560)
        self._all_rows = rows

        layout = QVBoxLayout(self)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Type to filter by group, tag or value…")
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search)
        self._count = QLabel()
        search_row.addWidget(self._count)
        layout.addLayout(search_row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Group", "Tag", "Value"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        self._render_rows(rows)

    def _render_rows(self, rows):
        self._table.setRowCount(len(rows))
        for r, (group, tag, val) in enumerate(rows):
            self._table.setItem(r, 0, QTableWidgetItem(group))
            self._table.setItem(r, 1, QTableWidgetItem(tag))
            self._table.setItem(r, 2, QTableWidgetItem(val))
        self._count.setText(f"{len(rows)} / {len(self._all_rows)}")

    def _apply_filter(self, text):
        text = text.lower()
        rows = self._all_rows if not text else [
            row for row in self._all_rows if any(text in c.lower() for c in row)]
        self._render_rows(rows)
