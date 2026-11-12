"""
Video Tag Writer - Main application entry point.

Video Tag Writer v0.1.0
"""

import os
import pathlib
import sys
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# IMM setup at module level so _init_win32() fires before QApplication is created.
_IMM_PATH = os.path.expanduser("~/Projects/Icon_Manager_Module")
if os.path.isdir(_IMM_PATH) and _IMM_PATH not in sys.path:
    sys.path.insert(0, _IMM_PATH)

_app_icons = None
try:
    from icon_loader import IconLoader  # side-effect: _init_win32() on Windows
    if getattr(sys, 'frozen', False):
        _icons_root = pathlib.Path(sys._MEIPASS)
    else:
        _icons_root = pathlib.Path(__file__).resolve().parent.parent
    _icon_dir = _icons_root / "resources" / "icons"
    if any(_icon_dir.glob("app*.png")):
        _app_icons = IconLoader(base_path=_icon_dir)
except Exception:
    pass

from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout,
    QLabel, QSplitter, QStatusBar, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from video_tag_writer.constants import (
    APP_NAME, APP_VERSION, APP_TIMESTAMP, APP_ORGANIZATION, APP_USER_MODEL_ID, VIDEO_EXTENSIONS,
)
from video_tag_writer.config import config
from video_tag_writer.single_instance_guard import SingleInstanceGuard
from video_tag_writer import exiftool_utils
from video_tag_writer.exiftool_utils import ExifToolError
from video_tag_writer.metadata import MetadataManager
from video_tag_writer.widgets import VideoPanel, MetadataPanel
from video_tag_writer.file_ops import FileOpsMixin
from video_tag_writer.navigation import NavigationMixin
from video_tag_writer.window import WindowMixin
from video_tag_writer.menu import MenuMixin
from video_tag_writer.theme import is_dark_theme
from video_tag_writer.theme_mixin import ThemeMixin
from video_tag_writer.help import HelpMixin


def get_app_icon() -> QIcon:
    if _app_icons is not None:
        return _app_icons.app_icon()
    return QIcon()


class MainWindow(NavigationMixin, FileOpsMixin, MenuMixin, ThemeMixin, HelpMixin, WindowMixin, QMainWindow):
    """
    Main application window.
    Splitter layout: MetadataPanel (left) | VideoPanel (right).
    Mixin chain: NavigationMixin → FileOpsMixin → MenuMixin → ThemeMixin → HelpMixin → WindowMixin → QMainWindow
    """

    def __init__(self):
        super().__init__()
        self._is_closing = False
        self.metadata_manager = MetadataManager()

        # Theme / zoom state — must be set before _setup_ui calls create_menu_bar
        self.current_theme = config.current_theme
        self.dark_mode = is_dark_theme(self.current_theme)
        self.ui_scale_factor = config.ui_zoom_factor
        self._zoom_css = ''

        self._setup_ui()
        QApplication.instance().installEventFilter(self)
        self.restore_window_geometry()

        self.apply_theme()
        if self.ui_scale_factor != 1.0:
            self._apply_ui_zoom()

        self._restore_last_file()
        logger.info("Main window initialised")

    # -- UI setup -------------------------------------------------------------

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.resize(1180, 720)
        self.setWindowIcon(get_app_icon())
        self.create_menu_bar()
        self.create_toolbar()
        self._build_central()
        self._build_status_bar()

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.metadata_panel = MetadataPanel(self.metadata_manager)
        splitter.addWidget(self.metadata_panel)
        self.video_panel = VideoPanel(self.metadata_manager)
        splitter.addWidget(self.video_panel)
        splitter.setSizes([700, 480])
        layout.addWidget(splitter)

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label, 1)
        sb.addPermanentWidget(QLabel(f"Ver {APP_VERSION}  ({APP_TIMESTAMP})"))

    def set_status(self, message: str):
        self._status_label.setText(message)
        self._update_toolbar_label(message)

    # -- startup -------------------------------------------------------------

    def _restore_last_file(self):
        if config.selected_file and os.path.isfile(config.selected_file):
            self.load_file(config.selected_file)


# ----------------------------------------------------------------------
# Self-test (used by build_exe.ps1 to verify the frozen bundle)
# ----------------------------------------------------------------------

def run_self_test(report_path: str) -> int:
    """
    Verify the (frozen) build without showing a window: every shared module is
    importable, ExifTool starts and is the bundled copy, and docs are bundled.
    Writes a JSON report to report_path; returns 0 if all required checks pass.
    A windowed EXE has no console, hence the report file instead of stdout.
    """
    import importlib
    import json
    from video_tag_writer.help import HelpMixin as _Help
    from video_tag_writer.video_utils import find_ff_tools

    frozen = bool(getattr(sys, 'frozen', False))
    bundle = getattr(sys, '_MEIPASS', '')
    report = {'app': f"{APP_NAME} {APP_VERSION}", 'frozen': frozen, 'bundle_dir': bundle,
              'checks': {}, 'info': {}}
    checks = report['checks']

    for mod in ('theme_manager', 'icon_loader', 'pyqt_app_info', 'exiftool', 'PyQt6.QtWidgets'):
        try:
            importlib.import_module(mod)
            checks[f'import {mod}'] = True
        except Exception as e:
            checks[f'import {mod}'] = False
            report['info'][f'import {mod} error'] = repr(e)

    try:
        ver = exiftool_utils.check_exiftool_available()
        path, _ = exiftool_utils.exiftool_info()
        report['info']['exiftool'] = f"{ver}  ({path})"
        checks['exiftool starts'] = True
        if frozen:
            checks['exiftool is bundled copy'] = os.path.normcase(os.path.dirname(path)) == os.path.normcase(bundle)
        # Read the running executable itself — proves ExifTool can parse files end to end
        tags = exiftool_utils.read_tags(sys.executable)
        report['info']['self FileType'] = tags.get('File:FileType')
        if frozen:
            report['info']['self ProductVersion'] = tags.get('EXE:ProductVersion')
            checks['exe version info'] = str(tags.get('EXE:ProductVersion')) == APP_VERSION
    except Exception as e:
        checks['exiftool starts'] = False
        report['info']['exiftool error'] = repr(e)
    finally:
        exiftool_utils.shutdown()

    for doc in ('README.md', 'CHANGELOG.md'):
        checks[f'{doc} available'] = _Help._find_file(doc) is not None

    # Qt platform plugin + full window construction (never shown).  The last-file
    # restore is suppressed in memory only, and the window is never closed through
    # closeEvent, so the user's config file is not rewritten.
    try:
        app = QApplication.instance() or QApplication([sys.argv[0]])
        report['info']['qt platform'] = app.platformName()
        config.selected_file = None
        window = MainWindow()
        checks['main window builds'] = window.metadata_panel is not None and window.video_panel is not None
        window.deleteLater()
    except Exception as e:
        checks['main window builds'] = False
        report['info']['main window error'] = repr(e)
    finally:
        exiftool_utils.shutdown()

    ffmpeg, ffprobe = find_ff_tools('')
    report['info']['ffmpeg'] = ffmpeg or 'not found (optional)'
    report['info']['ffprobe'] = ffprobe or 'not found (optional)'

    report['passed'] = all(checks.values())
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return 0 if report['passed'] else 1


# ----------------------------------------------------------------------
# Application entry point
# ----------------------------------------------------------------------

def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--self-test':
        return run_self_test(sys.argv[2])

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)
    app.setWindowIcon(get_app_icon())

    cli_file = None
    if len(sys.argv) > 1:
        candidate = sys.argv[1]
        if os.path.isfile(candidate) and os.path.splitext(candidate)[1].lower() in VIDEO_EXTENSIONS:
            cli_file = os.path.abspath(candidate)

    guard = SingleInstanceGuard(APP_USER_MODEL_ID)
    payload = cli_file.encode("utf-8") if cli_file else b""
    if not guard.try_acquire(payload):
        return 0
    app.aboutToQuit.connect(guard.release)

    try:
        ver = exiftool_utils.check_exiftool_available()
        logger.info(f"ExifTool {ver} is available")
    except ExifToolError as e:
        QMessageBox.critical(None, "Missing Dependency", str(e))
        return 1
    app.aboutToQuit.connect(exiftool_utils.shutdown)

    window = MainWindow()
    guard.connect_window(window, on_payload=window.load_file)
    window.show()

    if _app_icons is not None:
        _app_icons.set_taskbar_icon(window, APP_USER_MODEL_ID)

    if cli_file:
        window.load_file(cli_file)

    try:
        return app.exec()
    except KeyboardInterrupt:
        app.quit()
        return 0
    finally:
        exiftool_utils.shutdown()


if __name__ == "__main__":
    sys.exit(main())
