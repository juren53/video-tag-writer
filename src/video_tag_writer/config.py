"""
VideoTagWriter - Configuration management.

Persists to ~/.video_tag_writer_config.json.  The VTW_CONFIG_FILE environment
variable overrides the location (used by the test suite so tests never touch the
user's real configuration).
"""

import os
import json
import logging

from .constants import (APP_VERSION, APP_TIMESTAMP,
                        DEFAULT_MODES, DEFAULT_DETECT_FRAMES, DEFAULT_DETECT_DEFAULT)

logger = logging.getLogger(__name__)


def _default_config_path() -> str:
    return os.environ.get("VTW_CONFIG_FILE") or os.path.join(
        os.path.expanduser("~"), ".video_tag_writer_config.json")


class Config:
    """Global configuration and state management."""

    def __init__(self, config_file: str | None = None):
        self.app_version = APP_VERSION
        self.app_timestamp = APP_TIMESTAMP

        self.selected_file = None
        self.last_directory = None
        self.recent_files = []
        self.recent_directories = []
        self.directory_video_files = []
        self.current_file_index = -1

        self.dark_mode = False
        self.ui_zoom_factor = 1.0
        self.current_theme = 'light'
        self.window_geometry = None
        self.window_maximized = False

        # External tools — empty string means auto-locate
        self.exiftool_path = ''
        self.ffmpeg_dir = ''
        # Keep ExifTool's "<file>_original" backup on every save
        self.keep_backup = False
        # Extract a poster frame with ffmpeg when a file is loaded
        self.show_poster_frame = True

        # Mode state — seeded from DEFAULT_MODES on first run
        self.active_mode = DEFAULT_DETECT_DEFAULT
        self.modes = {name: list(fields) for name, fields in DEFAULT_MODES.items()}

        # Auto-detect mode settings
        self.auto_detect_mode = True
        self.mode_detect_frames = dict(DEFAULT_DETECT_FRAMES)
        self.mode_detect_default = DEFAULT_DETECT_DEFAULT

        self.config_file = config_file or _default_config_path()
        self.load_config()

    # ------------------------------------------------------------------
    # Recent files / directories
    # ------------------------------------------------------------------

    def add_recent_file(self, file_path):
        if file_path and os.path.exists(file_path):
            if file_path in self.recent_files:
                self.recent_files.remove(file_path)
            self.recent_files.insert(0, file_path)
            self.recent_files = self.recent_files[:10]
            self.save_config()

    def add_recent_directory(self, directory_path):
        if directory_path and os.path.isdir(directory_path):
            if directory_path in self.recent_directories:
                self.recent_directories.remove(directory_path)
            self.recent_directories.insert(0, directory_path)
            self.recent_directories = self.recent_directories[:10]
            self.save_config()

    # ------------------------------------------------------------------
    # Mode helpers
    # ------------------------------------------------------------------

    def get_active_mode(self):
        return self.active_mode

    def set_active_mode(self, mode_name):
        if mode_name in self.modes:
            self.active_mode = mode_name
            self.save_config()

    def get_mode_fields(self, mode_name=None):
        name = mode_name or self.active_mode
        fallback = self.modes.get(DEFAULT_DETECT_DEFAULT) or next(iter(self.modes.values()), [])
        return list(self.modes.get(name, fallback))

    def reset_mode_to_default(self, mode_name):
        if mode_name in DEFAULT_MODES:
            self.modes[mode_name] = list(DEFAULT_MODES[mode_name])
            self.save_config()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    _PERSISTED = (
        'selected_file', 'last_directory', 'recent_files', 'recent_directories',
        'dark_mode', 'ui_zoom_factor', 'current_theme', 'window_geometry',
        'window_maximized', 'exiftool_path', 'ffmpeg_dir', 'keep_backup',
        'show_poster_frame', 'active_mode', 'modes', 'auto_detect_mode',
        'mode_detect_frames', 'mode_detect_default',
    )

    def save_config(self):
        try:
            data = {key: getattr(self, key) for key in self._PERSISTED}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def load_config(self):
        try:
            if not os.path.exists(self.config_file):
                return
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.selected_file = data.get('selected_file')
            self.last_directory = data.get('last_directory')
            self.recent_files = [f for f in data.get('recent_files', []) if os.path.exists(f)]
            self.recent_directories = [
                d for d in data.get('recent_directories', []) if os.path.isdir(d)
            ]
            self.dark_mode = data.get('dark_mode', False)
            self.ui_zoom_factor = data.get('ui_zoom_factor', 1.0)
            self.current_theme = data.get('current_theme', 'light')
            self.window_geometry = data.get('window_geometry')
            self.window_maximized = data.get('window_maximized', False)
            self.exiftool_path = data.get('exiftool_path', '')
            self.ffmpeg_dir = data.get('ffmpeg_dir', '')
            self.keep_backup = data.get('keep_backup', False)
            self.show_poster_frame = data.get('show_poster_frame', True)
            self.auto_detect_mode = data.get('auto_detect_mode', True)
            self.mode_detect_frames = data.get('mode_detect_frames', dict(DEFAULT_DETECT_FRAMES))
            self.mode_detect_default = data.get('mode_detect_default', DEFAULT_DETECT_DEFAULT)

            # Built-in modes always come from DEFAULT_MODES so schema changes take
            # effect immediately; user-added custom modes are preserved (ATW behaviour).
            saved_modes = data.get('modes', {})
            for name, fields in DEFAULT_MODES.items():
                saved_modes[name] = list(fields)
            self.modes = saved_modes

            active = data.get('active_mode', DEFAULT_DETECT_DEFAULT)
            self.active_mode = active if active in self.modes else DEFAULT_DETECT_DEFAULT

            logger.debug(f"Configuration loaded from {self.config_file}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")


config = Config()
