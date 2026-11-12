"""
VideoTagWriter - ThemeMixin: apply_theme, zoom_ui, dark mode toggle.
"""

import logging

from PyQt6.QtWidgets import QApplication, QDialog

from .config import config
from .theme import DEFAULT_THEME, is_dark_theme, get_fusion_palette
from .widgets.theme_dialog import ThemeDialog

logger = logging.getLogger(__name__)


class ThemeMixin:
    """Mixin providing theme application, UI zoom, and dark mode toggle."""

    def apply_theme(self):
        """Apply the current theme palette to the application."""
        QApplication.instance().setPalette(get_fusion_palette(self.current_theme))
        self.set_status(f"Applied {self.current_theme} theme")
        logger.info(f"Applied theme: {self.current_theme}")

    def on_select_theme(self):
        """Open the theme picker dialog."""
        dialog = ThemeDialog(self.current_theme, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.get_selected_theme()
            if selected != self.current_theme:
                self.current_theme = selected
                self.apply_theme()
                self.dark_mode = is_dark_theme(self.current_theme)
                self.dark_mode_action.setChecked(self.dark_mode)
                config.current_theme = self.current_theme
                config.dark_mode = self.dark_mode
                config.save_config()
                self.set_status(f"Theme changed to {self.current_theme}")
                logger.info(f"Theme changed to {self.current_theme}")

    def on_toggle_dark_mode(self):
        """Toggle between Default Light and Dark themes."""
        self.current_theme = DEFAULT_THEME if is_dark_theme(self.current_theme) else "dark"
        self.apply_theme()
        self.dark_mode = is_dark_theme(self.current_theme)
        self.dark_mode_action.setChecked(self.dark_mode)
        config.current_theme = self.current_theme
        config.dark_mode = self.dark_mode
        config.save_config()

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def zoom_ui(self, delta: float):
        """Change UI zoom by delta (e.g. +0.1 or -0.1)."""
        new_zoom = round(self.ui_scale_factor + delta, 1)
        if new_zoom > 1.5:
            self.set_status("Maximum zoom reached (150%)")
            return
        if new_zoom < 0.5:
            self.set_status("Minimum zoom reached (50%)")
            return
        self.ui_scale_factor = new_zoom
        self._apply_ui_zoom()
        config.ui_zoom_factor = new_zoom
        config.save_config()

    def reset_zoom(self):
        """Reset UI zoom to 100%."""
        self.ui_scale_factor = 1.0
        self._apply_ui_zoom()
        config.ui_zoom_factor = 1.0
        config.save_config()

    def _apply_ui_zoom(self):
        """Apply current zoom factor to the application stylesheet."""
        pct = int(self.ui_scale_factor * 100)
        if hasattr(self, 'zoom_label'):
            self.zoom_label.setText(f"  {pct}%")
        self.set_status(f"Zoom: {pct}%")

        base_pt = 9.0
        pt = base_pt * self.ui_scale_factor

        zoom_css = f"""
        /* ZOOM_STYLES_START */
        QWidget {{ font-size: {pt:.1f}pt; }}
        QPushButton {{
            font-size: {pt:.1f}pt;
            padding: {int(6 * self.ui_scale_factor)}px {int(12 * self.ui_scale_factor)}px;
            min-width: {int(80 * self.ui_scale_factor)}px;
        }}
        QLabel {{ font-size: {pt:.1f}pt; }}
        QLineEdit {{ font-size: {pt:.1f}pt; padding: {int(4 * self.ui_scale_factor)}px; }}
        QTextEdit {{ font-size: {pt:.1f}pt; }}
        QComboBox {{
            font-size: {pt:.1f}pt;
            padding: {int(4 * self.ui_scale_factor)}px {int(8 * self.ui_scale_factor)}px;
        }}
        QMenuBar {{ font-size: {pt:.1f}pt; }}
        QMenu {{ font-size: {pt:.1f}pt; }}
        QStatusBar {{ font-size: {pt:.1f}pt; }}
        /* ZOOM_STYLES_END */
        """
        self._zoom_css = zoom_css
        QApplication.instance().setStyleSheet(zoom_css)

        logger.debug(f"Zoom set to {pct}% ({pt:.1f}pt)")
