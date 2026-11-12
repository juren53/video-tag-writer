"""
VideoTagWriter - WindowMixin: key events, geometry save/restore, close handler.
"""

import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

from .config import config

logger = logging.getLogger(__name__)


class WindowMixin:
    """Mixin providing keyboard navigation, geometry persistence, and clean shutdown."""

    def eventFilter(self, obj, event):
        """Application-level event filter to intercept Up/Down arrow keys."""
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Up:
                self.on_previous()
                return True
            elif event.key() == Qt.Key.Key_Down:
                self.on_next()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """Up/Down arrows navigate; F5 refreshes; everything else bubbles up."""
        key = event.key()
        if key == Qt.Key.Key_Up:
            self.on_previous()
            event.accept()
        elif key == Qt.Key.Key_Down:
            self.on_next()
            event.accept()
        elif key == Qt.Key.Key_F5:
            self.on_refresh()
            event.accept()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def save_window_geometry(self):
        """Persist current window position and size to config."""
        try:
            g = self.geometry()
            config.window_geometry = [g.x(), g.y(), g.width(), g.height()]
            config.window_maximized = self.isMaximized()
            config.save_config()
        except Exception as e:
            logger.error(f"Error saving window geometry: {e}")

    def restore_window_geometry(self):
        """Restore window position and size from config."""
        try:
            geom = config.window_geometry
            if geom and len(geom) == 4:
                x, y, w, h = geom
                screen = QGuiApplication.primaryScreen().geometry()
                x = max(0, min(x, screen.width() - w))
                y = max(0, min(y, screen.height() - h))
                w = max(800, w)
                h = max(500, h)
                self.setGeometry(x, y, w, h)
                if config.window_maximized:
                    self.showMaximized()
        except Exception as e:
            logger.error(f"Error restoring window geometry: {e}")

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """Save geometry and config on close."""
        if getattr(self, '_is_closing', False):
            event.accept()
            return
        self._is_closing = True
        try:
            self.save_window_geometry()
            config.save_config()
        except Exception as e:
            logger.error(f"Error during close: {e}")
        event.accept()
        QApplication.instance().removeEventFilter(self)
        QApplication.instance().quit()
