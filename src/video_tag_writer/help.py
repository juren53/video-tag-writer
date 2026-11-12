"""
VideoTagWriter - HelpMixin: About and Changelog dialogs.
"""

import os
import sys
import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt

from .constants import APP_NAME, APP_VERSION, APP_TIMESTAMP

logger = logging.getLogger(__name__)


def _project_root():
    # From src/video_tag_writer/ go up two levels
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


class HelpMixin:
    """Mixin providing About and Changelog dialogs."""

    def on_about(self):
        """Show About dialog, preferring pyqt_app_info if available."""
        from .exiftool_utils import exiftool_info
        et_ver = exiftool_info()[1] or 'not found'

        try:
            from pyqt_app_info import AppIdentity, gather_info
            from pyqt_app_info.qt import AboutDialog

            identity = AppIdentity(
                name=APP_NAME,
                version=APP_VERSION,
                commit_date=APP_TIMESTAMP,
                description=(
                    "Metadata viewer/editor for MP4, MPG and MPEG video files.\n"
                    f"ExifTool {et_ver}"
                ),
            )
            info = gather_info(identity, caller_file=__file__)
            AboutDialog(info, parent=self).exec()
        except Exception as e:
            logger.debug(f"pyqt_app_info unavailable ({e}), falling back to QMessageBox")
            QMessageBox.about(
                self,
                f"About {APP_NAME}",
                f"<b>{APP_NAME}</b>&nbsp; v{APP_VERSION}<br><br>"
                f"Metadata viewer/editor for MP4, MPG and MPEG video files.<br>"
                f"Built with <b>PyQt6</b> + <b>ExifTool {et_ver}</b>.<br><br>"
                f"<small>{APP_TIMESTAMP}</small>",
            )

    _README_URL    = "https://github.com/juren53/video-tag-writer/blob/master/README.md"
    _CHANGELOG_URL = "https://github.com/juren53/video-tag-writer/blob/master/CHANGELOG.md"
    _ISSUES_URL    = "https://github.com/juren53/video-tag-writer/issues"

    def on_readme(self):
        """Show README.md in a resizable dialog, falling back to the GitHub URL."""
        path = self._find_file('README.md')
        if path:
            try:
                dialog = QDialog(self)
                dialog.setWindowTitle("README")
                dialog.resize(800, 600)
                dialog.setWindowFlags(
                    Qt.WindowType.Window |
                    Qt.WindowType.WindowMinimizeButtonHint |
                    Qt.WindowType.WindowMaximizeButtonHint |
                    Qt.WindowType.WindowCloseButtonHint
                )
                layout = QVBoxLayout(dialog)

                text = QTextEdit()
                text.setReadOnly(True)
                with open(path, encoding='utf-8') as f:
                    text.setMarkdown(f.read())
                layout.addWidget(text)

                btn = QPushButton("Close")
                btn.clicked.connect(dialog.accept)
                layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

                dialog.exec()
                return
            except Exception as e:
                logger.error(f"Error showing README: {e}")

        import webbrowser
        try:
            webbrowser.open(self._README_URL)
        except Exception as e:
            logger.error(f"Error opening README URL: {e}")
            QMessageBox.warning(self, "README", f"Could not open README.\n\nURL: {self._README_URL}")

    def on_changelog(self):
        """Show CHANGELOG.md locally, falling back to the GitHub URL."""
        changelog_path = self._find_file('CHANGELOG.md')

        if changelog_path:
            try:
                dialog = QDialog(self)
                dialog.setWindowTitle("Changelog")
                dialog.resize(740, 560)
                dialog.setWindowFlags(
                    Qt.WindowType.Window |
                    Qt.WindowType.WindowMinimizeButtonHint |
                    Qt.WindowType.WindowMaximizeButtonHint |
                    Qt.WindowType.WindowCloseButtonHint
                )
                layout = QVBoxLayout(dialog)

                text = QTextEdit()
                text.setReadOnly(True)
                with open(changelog_path, encoding='utf-8') as f:
                    text.setPlainText(f.read())
                layout.addWidget(text)

                btn = QPushButton("Close")
                btn.clicked.connect(dialog.accept)
                layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

                dialog.exec()
                return
            except Exception as e:
                logger.error(f"Error showing local changelog: {e}")

        # Local file unavailable (frozen EXE without bundled file, or source tree missing) —
        # open GitHub page in the default browser.
        import webbrowser
        try:
            webbrowser.open(self._CHANGELOG_URL)
        except Exception as e:
            logger.error(f"Error opening changelog URL: {e}")
            QMessageBox.warning(
                self, "Changelog",
                f"Could not open changelog.\n\nURL: {self._CHANGELOG_URL}"
            )

    def on_issue_log(self):
        """Open the GitHub issue tracker in the default browser."""
        import webbrowser
        try:
            webbrowser.open(self._ISSUES_URL)
        except Exception as e:
            logger.error(f"Error opening issue log URL: {e}")
            QMessageBox.warning(self, "Issue Log",
                                f"Could not open issue log.\n\nURL: {self._ISSUES_URL}")

    @staticmethod
    def _find_file(filename):
        """Locate a project-root file in the frozen EXE bundle or source tree."""
        # 1. Frozen EXE: PyInstaller extracts bundled data to sys._MEIPASS
        if getattr(sys, 'frozen', False):
            candidate = os.path.join(sys._MEIPASS, filename)
            if os.path.isfile(candidate):
                return candidate

        # 2. Source tree: two levels up from src/video_tag_writer/
        candidate = os.path.join(_project_root(), filename)
        if os.path.isfile(candidate):
            return candidate

        return None
