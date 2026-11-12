"""
VideoTagWriter - ExifTool wrapper (the VTW counterpart of ATW's mutagen_utils).

One persistent ExifTool process (PyExifTool, -stay_open) serves the whole session.

Rules learned from the 2026-11-11 probe (see notes/TOOL_COMPARISON_*.md):
  * Tag values never travel as command-line arguments — on Windows non-ASCII text is
    mangled there.  Values are written through a UTF-8 JSON file (-json=FILE).
  * An empty field is deleted with a "-TAG=" argument.  JSON null writes the literal
    text "null" and JSON "" writes an empty atom, so neither is used for deletes.
  * File names are passed with -charset filename=utf8.
  * MPG/MPEG cannot be written; their descriptive metadata lives in a <name>.xmp sidecar.
"""

import json
import logging
import os
import re
import shutil
import sys
import tempfile

from .constants import SIDECAR_EXTENSIONS

logger = logging.getLogger(__name__)

# Minimal XMP packet used to create a new sidecar that ExifTool then updates in place.
# (Creating a sidecar from the video with "-o x.xmp video.mpg" also copies unwanted
# technical tags such as XMP-tiff:ImageWidth into it.)
_EMPTY_XMP = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    ' </rdf:RDF>\n'
    '</x:xmpmeta>\n'
    '<?xpacket end="w"?>\n'
)

_COMMON_ARGS = ["-G1", "-charset", "filename=utf8"]


class ExifToolError(Exception):
    """Raised when ExifTool is missing, or a read/write fails."""


# ----------------------------------------------------------------------
# Locating the binary
# ----------------------------------------------------------------------

def find_exiftool(configured: str = '') -> str | None:
    """Return the path of the ExifTool executable, or None if not found."""
    candidates = []
    if configured:
        candidates.append(configured)
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(getattr(sys, '_MEIPASS', ''), 'exiftool.exe'))
    found = shutil.which('exiftool')
    if found:
        candidates.append(found)
    candidates.append(os.path.join(os.path.expanduser('~'), 'bin', 'exiftool.exe'))
    candidates.append(os.path.join(os.path.expanduser('~'), 'bin', 'exiftool'))

    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


# ----------------------------------------------------------------------
# Persistent session
# ----------------------------------------------------------------------

_helper = None
_helper_path = None


def _configured_path() -> str:
    try:
        from .config import config
        return config.exiftool_path or ''
    except Exception:
        return ''


def get_helper():
    """Return the running ExifToolHelper, starting it on first use."""
    global _helper, _helper_path
    if _helper is not None and _helper.running:
        return _helper

    try:
        import exiftool  # PyExifTool
    except ImportError as e:
        raise ExifToolError(
            "The 'PyExifTool' package is not installed.\n\n"
            "Install it with:  pip install PyExifTool"
        ) from e

    path = find_exiftool(_configured_path())
    if not path:
        raise ExifToolError(
            "ExifTool was not found.\n\n"
            "Install it from https://exiftool.org and make sure 'exiftool' is on your PATH,\n"
            "or set its location in the configuration file (exiftool_path)."
        )
    try:
        _helper = exiftool.ExifToolHelper(
            executable=path, common_args=list(_COMMON_ARGS), encoding="utf-8",
            auto_start=False,
        )
        _helper.run()
        _helper_path = path
        logger.info(f"ExifTool {_helper.version} started from {path}")
        return _helper
    except Exception as e:
        _helper = None
        raise ExifToolError(f"Could not start ExifTool ({path}): {e}") from e


def check_exiftool_available() -> str:
    """Pre-flight check: start ExifTool and return its version string."""
    return str(get_helper().version)


def exiftool_info() -> tuple[str | None, str | None]:
    """(path, version) of the running ExifTool, or (None, None)."""
    try:
        h = get_helper()
        return _helper_path, str(h.version)
    except ExifToolError:
        return None, None


def shutdown():
    """Terminate the persistent ExifTool process (call on application exit)."""
    global _helper
    if _helper is not None:
        try:
            if _helper.running:
                _helper.terminate()
        except Exception as e:
            logger.debug(f"ExifTool terminate: {e}")
        _helper = None


# ----------------------------------------------------------------------
# Sidecars
# ----------------------------------------------------------------------

def uses_sidecar(path: str) -> bool:
    """True for formats whose descriptive metadata is stored in an XMP sidecar."""
    return os.path.splitext(path)[1].lower() in SIDECAR_EXTENSIONS


def sidecar_path_for(path: str) -> str:
    """'<dir>/<name>.xmp' — the Adobe/ExifTool %d%f.xmp convention."""
    return os.path.splitext(path)[0] + '.xmp'


def ensure_sidecar(path: str) -> str:
    """Create an empty XMP sidecar for path if none exists; return the sidecar path."""
    sidecar = sidecar_path_for(path)
    if not os.path.exists(sidecar):
        with open(sidecar, 'w', encoding='utf-8', newline='\n') as f:
            f.write(_EMPTY_XMP)
        logger.info(f"Created sidecar {sidecar}")
    return sidecar


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------

def read_tags(path: str, extra_args: list[str] | None = None) -> dict:
    """Return all tags of one file as {'Group:Tag': value} (group = ExifTool family 1)."""
    if not os.path.isfile(path):
        raise ExifToolError(f"File not found: {path}")
    try:
        result = get_helper().get_metadata(path, params=extra_args or [])
    except ExifToolError:
        raise
    except Exception as e:
        raise ExifToolError(f"Could not read '{os.path.basename(path)}': {e}") from e
    tags = dict(result[0]) if result else {}
    tags.pop('SourceFile', None)
    return tags


def read_metadata(path: str) -> tuple[dict, dict | None]:
    """
    Read a video file and, for sidecar formats, its XMP sidecar.

    Returns (file_tags, sidecar_tags).  sidecar_tags is None for embedded formats,
    and {} for sidecar formats whose sidecar does not exist yet.
    """
    file_tags = read_tags(path)
    if not uses_sidecar(path):
        return file_tags, None
    sidecar = sidecar_path_for(path)
    if os.path.isfile(sidecar):
        return file_tags, read_tags(sidecar)
    return file_tags, {}


_TEXT_LINE = re.compile(r'^\[(?P<group>[^\]]+)\]\s+(?P<tag>\S+)\s*:\s?(?P<value>.*)$')


def read_all_tags_listing(path: str) -> list[tuple[str, str, str]]:
    """
    Return every tag (including duplicates, via -a) as (group, tag, value) rows.
    Used by the View All Tags dialog.
    """
    try:
        out = get_helper().execute("-a", "-s", "-G1", "-sep", "; ", path)
    except Exception as e:
        raise ExifToolError(f"Could not list tags of '{os.path.basename(path)}': {e}") from e
    rows = []
    for line in out.splitlines():
        m = _TEXT_LINE.match(line)
        if m:
            rows.append((m.group('group'), m.group('tag'), m.group('value')))
    return rows


def tag_text(tags: dict | None, tag: str, default: str = '') -> str:
    """
    Return a tag's value as display text: lists are joined with '; ', numbers are
    stringified, missing/None -> default.  Lookup is exact, then case-insensitive.
    """
    if not tags or not tag:
        return default
    value = tags.get(tag)
    if value is None:
        lowered = tag.lower()
        for key, v in tags.items():
            if key.lower() == lowered:
                value = v
                break
    if value is None:
        return default
    if isinstance(value, list):
        return '; '.join(str(v) for v in value if v is not None and str(v) != '')
    return str(value)


def rule_matches(tags: dict | None, rule: str) -> bool:
    """
    True if a detection rule matches tags.  A rule is one or more "|"-separated
    alternatives, each either "Group:Tag" (non-empty) or "Group:Tag=Value"
    (case-insensitive; for list tags, any one item may match).
    """
    if not tags or not rule:
        return False
    for alt in rule.split('|'):
        alt = alt.strip()
        if not alt:
            continue
        if '=' in alt:
            tag, expected = (s.strip() for s in alt.split('=', 1))
            expected = expected.casefold()
            items = [v.strip().casefold() for v in tag_text(tags, tag).split(';')]
            if expected in items:
                return True
        elif tag_text(tags, alt):
            return True
    return False


def detect_mode(tags, detect_frames: dict, default: str) -> str:
    """First mode whose detection rule matches tags wins; else default."""
    if tags:
        for mode_name, rule in detect_frames.items():
            if rule_matches(tags, rule):
                return mode_name
    return default


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------

def write_tags(target: str, set_values: dict, delete_tags: list[str],
               keep_backup: bool = False) -> str:
    """
    Write tags to target (a video file or an .xmp sidecar).

    set_values:  {'Group:Tag': value}; value may be str or list.  A trailing '#' on the
                 key (e.g. 'ItemList:ContentCreateDate#') writes the raw value.
    delete_tags: tags to remove ('-TAG=').
    Returns ExifTool's summary line.  Raises ExifToolError on failure.
    """
    if not set_values and not delete_tags:
        return "Nothing to write"
    if not os.path.isfile(target):
        raise ExifToolError(f"File not found: {target}")

    args = [] if keep_backup else ["-overwrite_original"]
    tmp = None
    try:
        if set_values:
            fd, tmp = tempfile.mkstemp(prefix="vtw_", suffix=".json")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump([dict(SourceFile=target, **set_values)], f, ensure_ascii=False)
            args.append(f"-json={tmp}")
        args.extend(f"-{tag}=" for tag in delete_tags)
        args.append(target)

        helper = get_helper()
        stdout = helper.execute(*args)
        stderr = (helper.last_stderr or '').strip()
        summary = ' '.join((stdout or '').split() + stderr.split())
        logger.info(f"ExifTool write {os.path.basename(target)}: {summary}")

        # ExifTool reports errors on stderr ("Error: ...") with "0 image files updated".
        if re.search(r'(^|\s)Error:', stderr) or 'files weren\'t updated' in summary:
            raise ExifToolError(f"ExifTool could not write '{os.path.basename(target)}':\n{stderr}")
        return summary
    except ExifToolError:
        raise
    except Exception as e:
        raise ExifToolError(f"ExifTool write failed for '{os.path.basename(target)}': {e}") from e
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ----------------------------------------------------------------------
# Cover art (MP4 'covr' atom)
# ----------------------------------------------------------------------

def read_cover_art(path: str) -> bytes | None:
    """Return the embedded MP4 cover art image bytes, or None."""
    if uses_sidecar(path):
        return None
    try:
        data = get_helper().execute("-b", "-ItemList:CoverArt", path, raw_bytes=True)
        return bytes(data) if data else None
    except Exception as e:
        logger.debug(f"Cover art read failed for {path}: {e}")
        return None


def write_cover_art(path: str, image_path: str, keep_backup: bool = False) -> str:
    """Embed image_path as MP4 cover art (replacing any existing art)."""
    if uses_sidecar(path):
        raise ExifToolError("Cover art can only be embedded in MP4/M4V files.")
    args = [] if keep_backup else ["-overwrite_original"]
    args += [f"-ItemList:CoverArt<={image_path}", path]
    helper = get_helper()
    out = helper.execute(*args)
    stderr = (helper.last_stderr or '').strip()
    if re.search(r'(^|\s)Error:', stderr):
        raise ExifToolError(f"Could not set cover art:\n{stderr}")
    return ' '.join((out or '').split())


def remove_cover_art(path: str, keep_backup: bool = False) -> str:
    """Remove MP4 cover art."""
    if uses_sidecar(path):
        raise ExifToolError("Cover art can only be embedded in MP4/M4V files.")
    return write_tags(path, {}, ["ItemList:CoverArt"], keep_backup)
