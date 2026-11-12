"""
Video Tag Writer - Video file scanning utilities.
"""

import os
import logging

from .constants import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)


def get_video_files(directory: str) -> list:
    """Return a sorted list of supported video file paths in directory."""
    if not directory or not os.path.isdir(directory):
        return []
    files = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file(follow_symlinks=False):
                    if os.path.splitext(entry.name)[1].lower() in VIDEO_EXTENSIONS:
                        files.append(entry.path)
        files.sort(key=lambda x: os.path.basename(x).lower())
        return files
    except Exception as e:
        logger.error(f"Error scanning directory '{directory}': {e}")
        return []
