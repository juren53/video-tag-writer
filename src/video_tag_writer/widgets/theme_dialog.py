"""
VideoTagWriter - Theme selection dialog.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QDialogButtonBox, QFrame,
)
from PyQt6.QtCore import Qt

import sys, os
_TM_PATH = os.path.expanduser("~/Projects/ThemeManager")
if (not getattr(sys, 'frozen', False)   # the EXE uses its bundled copy (see theme.py)
        and os.path.isdir(_TM_PATH) and _TM_PATH not in sys.path):
    sys.path.insert(0, _TM_PATH)
from theme_manager import get_theme_registry, ThemeCategory


class ThemeDialog(QDialog):
    """Dialog for selecting application theme."""

    def __init__(self, current_theme: str, parent=None):
        super().__init__(parent)
        self._registry = get_theme_registry()
        self._selected = current_theme

        # Build (display_name, key) list ordered by category
        self._themes: list[tuple[str, str]] = []
        for cat in (ThemeCategory.BUILT_IN, ThemeCategory.POPULAR, ThemeCategory.CUSTOM):
            for t in sorted(self._registry.get_themes_by_category(cat), key=lambda x: x.display_name):
                self._themes.append((t.display_name, t.name))

        self.setWindowTitle("Select Theme")
        self.setFixedSize(480, 280)
        self._build_ui()
        self._update_preview()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Choose a theme for the application:"))

        self.theme_combo = QComboBox()
        for display_name, _ in self._themes:
            self.theme_combo.addItem(display_name)
        current_display = next(
            (d for d, k in self._themes if k == self._selected),
            self._themes[0][0] if self._themes else "",
        )
        self.theme_combo.setCurrentText(current_display)
        self.theme_combo.currentIndexChanged.connect(self._on_changed)
        layout.addWidget(self.theme_combo)

        # Palette swatch preview
        self.preview_frame = QFrame()
        self.preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_frame.setFixedHeight(80)
        preview_layout = QHBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(12, 8, 12, 8)

        self.preview_label = QLabel("Sample text — Aa Bb Cc 123")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        preview_layout.addWidget(self.preview_label, 1)

        self.preview_btn = QPushButton("Button")
        self.preview_btn.setFixedWidth(80)
        self.preview_btn.setEnabled(False)
        preview_layout.addWidget(self.preview_btn)

        layout.addWidget(self.preview_frame)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_changed(self, index: int):
        if 0 <= index < len(self._themes):
            self._selected = self._themes[index][1]
            self._update_preview()

    def _update_preview(self):
        theme = self._registry.get_theme(self._selected)
        if theme is None:
            return
        ui = theme.ui_palette
        self.preview_frame.setStyleSheet(
            f"QFrame {{ background-color: {ui.window_color}; border: 1px solid {ui.base_color}; }}"
        )
        self.preview_label.setStyleSheet(f"color: {ui.window_text_color}; background: transparent;")
        self.preview_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ui.button_color}; color: {ui.button_text_color};"
            f" border: 1px solid {ui.base_color}; border-radius: 3px; }}"
        )

    def get_selected_theme(self) -> str:
        """Return the internal registry key of the selected theme."""
        return self._selected
