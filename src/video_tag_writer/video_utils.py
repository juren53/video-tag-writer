"""
Video Tag Writer - Technical stream info and poster frames (ATW's audio_utils counterpart).

ffprobe/ffmpeg are optional helpers.  When present they supply the richest technical
info (codecs, duration for MPG) and the poster frame shown in the VideoPanel; when
absent, technical info falls back to the tags ExifTool already read.

The *newest* ffmpeg build found is used, not simply the first on PATH — the probe
machine had an old ffmpeg snapshot in ~/bin ahead of a current build.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from functools import lru_cache

from .constants import EMBEDDED_EXTENSIONS, SIDECAR_EXTENSIONS

logger = logging.getLogger(__name__)

_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0  # CREATE_NO_WINDOW
_EXE = '.exe' if sys.platform == 'win32' else ''

_FORMAT_MAP = {'.mp4': 'MP4', '.m4v': 'M4V', '.mpg': 'MPEG-PS (MPG)', '.mpeg': 'MPEG-PS (MPEG)'}


# ----------------------------------------------------------------------
# Locating ffmpeg / ffprobe
# ----------------------------------------------------------------------

def _run(cmd: list[str], timeout: float = 15, binary: bool = False):
    return subprocess.run(
        cmd, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW,
        **({} if binary else {'text': True, 'encoding': 'utf-8', 'errors': 'replace'}),
    )


def _version_key(exe: str) -> tuple:
    """Sortable version of an ffmpeg-family binary; git snapshots ('N-51106') sort lowest."""
    try:
        out = _run([exe, '-version'], timeout=10).stdout
    except Exception:
        return (-1,)
    m = re.search(r'version\s+n?(\d+)\.(\d+)(?:\.(\d+))?', out)
    if m:
        return tuple(int(g or 0) for g in m.groups())
    return (0,)


def _candidate_dirs(configured_dir: str) -> list[str]:
    dirs = []
    if configured_dir:
        dirs.append(configured_dir)
    if getattr(sys, 'frozen', False):
        dirs.append(getattr(sys, '_MEIPASS', ''))
    dirs.extend(p for p in os.environ.get('PATH', '').split(os.pathsep) if p)
    seen, out = set(), []
    for d in dirs:
        key = os.path.normcase(os.path.abspath(d))
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


@lru_cache(maxsize=4)
def find_ff_tools(configured_dir: str = '') -> tuple[str | None, str | None]:
    """
    Return (ffmpeg, ffprobe) paths from the directory holding the newest ffprobe.
    Either may be None.
    """
    best_dir, best_ver = None, None
    for d in _candidate_dirs(configured_dir):
        probe = os.path.join(d, 'ffprobe' + _EXE)
        if os.path.isfile(probe):
            ver = _version_key(probe)
            if best_ver is None or ver > best_ver:
                best_dir, best_ver = d, ver
    if best_dir is None:
        found = shutil.which('ffmpeg')
        return (found, None)
    ffmpeg = os.path.join(best_dir, 'ffmpeg' + _EXE)
    ffprobe = os.path.join(best_dir, 'ffprobe' + _EXE)
    logger.info(f"Using ffprobe from {best_dir} (version key {best_ver})")
    return (ffmpeg if os.path.isfile(ffmpeg) else shutil.which('ffmpeg'), ffprobe)


def _tools():
    try:
        from .config import config
        return find_ff_tools(config.ffmpeg_dir or '')
    except Exception:
        return find_ff_tools('')


def ff_tool_versions() -> dict:
    """{'ffmpeg': (path, version line), 'ffprobe': (...)} for diagnostics."""
    ffmpeg, ffprobe = _tools()
    out = {}
    for name, exe in (('ffmpeg', ffmpeg), ('ffprobe', ffprobe)):
        if exe:
            try:
                line = _run([exe, '-version'], timeout=10).stdout.splitlines()[0]
            except Exception as e:
                line = f"error: {e}"
            out[name] = (exe, line)
        else:
            out[name] = (None, 'not found')
    return out


# ----------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------

def format_duration(seconds) -> str:
    try:
        secs = float(seconds)
    except (TypeError, ValueError):
        return '--'
    if secs <= 0:
        return '--'
    total = int(round(secs))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_bitrate(bps) -> str:
    try:
        v = float(bps)
    except (TypeError, ValueError):
        return '--'
    if v <= 0:
        return '--'
    return f"{v / 1_000_000:.2f} Mbps" if v >= 1_000_000 else f"{v / 1000:.0f} kbps"


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} MB"
    return f"{size / 1024 ** 3:.2f} GB"


def _frame_rate(rate: str) -> str:
    try:
        num, den = rate.split('/')
        fps = float(num) / float(den)
        if fps <= 0:
            return '--'
        return f"{fps:.3f}".rstrip('0').rstrip('.') + " fps"
    except Exception:
        return '--'


def _channels(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return '--'
    return {1: 'Mono', 2: 'Stereo'}.get(n, f"{n} ch")


# ----------------------------------------------------------------------
# Technical info
# ----------------------------------------------------------------------

def _empty_info(path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    return {
        'filename': os.path.basename(path), 'format': _FORMAT_MAP.get(ext, ext.upper().lstrip('.')),
        'duration': '--', 'duration_secs': 0.0, 'overall_bitrate': '--',
        'video_codec': '--', 'resolution': '--', 'aspect_ratio': '--', 'frame_rate': '--',
        'scan_type': '--', 'video_bitrate': '--',
        'audio_codec': '--', 'sample_rate': '--', 'channels': '--', 'audio_bitrate': '--',
        'file_size': '--', 'modified': '--',
        'metadata_storage': '--', 'info_source': '--',
    }


def probe_with_ffprobe(path: str) -> dict | None:
    """Raw ffprobe JSON (format + streams), or None if ffprobe is unavailable/failed."""
    _, ffprobe = _tools()
    if not ffprobe:
        return None
    try:
        res = _run([ffprobe, '-v', 'error', '-print_format', 'json',
                    '-show_format', '-show_streams', path], timeout=30)
        if res.returncode != 0:
            logger.warning(f"ffprobe failed for {path}: {res.stderr.strip()[:300]}")
            return None
        return json.loads(res.stdout or '{}')
    except Exception as e:
        logger.warning(f"ffprobe error for {path}: {e}")
        return None


def _fill_from_ffprobe(info: dict, data: dict):
    fmt = data.get('format', {})
    if fmt.get('duration'):
        info['duration_secs'] = float(fmt['duration'])
        info['duration'] = format_duration(fmt['duration'])
    info['overall_bitrate'] = format_bitrate(fmt.get('bit_rate'))

    streams = data.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'
                  and not s.get('disposition', {}).get('attached_pic')), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if video:
        codec = video.get('codec_name', '--').upper()
        if video.get('profile'):
            codec += f" ({video['profile']})"
        info['video_codec'] = codec
        if video.get('width') and video.get('height'):
            info['resolution'] = f"{video['width']} × {video['height']}"
        if video.get('display_aspect_ratio') and video['display_aspect_ratio'] != '0:1':
            info['aspect_ratio'] = video['display_aspect_ratio']
        info['frame_rate'] = _frame_rate(video.get('avg_frame_rate') or video.get('r_frame_rate', ''))
        field_order = video.get('field_order')
        if field_order:
            info['scan_type'] = 'Progressive' if field_order == 'progressive' else f"Interlaced ({field_order.upper()})"
        info['video_bitrate'] = format_bitrate(video.get('bit_rate'))
    if audio:
        info['audio_codec'] = audio.get('codec_name', '--').upper()
        if audio.get('sample_rate'):
            info['sample_rate'] = f"{int(audio['sample_rate']):,} Hz"
        info['channels'] = audio.get('channel_layout', '').title() or _channels(audio.get('channels'))
        info['audio_bitrate'] = format_bitrate(audio.get('bit_rate'))
    info['info_source'] = 'ffprobe'


def _fill_from_exiftool(info: dict, tags: dict):
    """Fallback technical info from ExifTool tags (no -n, so values are printable)."""
    def first(*keys):
        for k in keys:
            v = tags.get(k)
            if v not in (None, ''):
                return v
        return None

    dur = first('QuickTime:Duration', 'Composite:Duration', 'MPEG:Duration')
    if dur:
        info['duration'] = str(dur)
        m = re.match(r'([\d.]+)\s*s', str(dur))
        if m:
            info['duration_secs'] = float(m.group(1))
            info['duration'] = format_duration(m.group(1))
    size = first('Composite:ImageSize')
    if size:
        info['resolution'] = str(size).replace('x', ' × ')
    fr = first('Track1:VideoFrameRate', 'MPEG:FrameRate')
    if fr:
        info['frame_rate'] = f"{fr} fps" if isinstance(fr, (int, float)) else str(fr)
    vc = first('Track1:CompressorName', 'Track1:CompressorID')
    if vc:
        info['video_codec'] = str(vc)
    elif 'MPEG:ImageWidth' in tags:
        info['video_codec'] = 'MPEG-1/2 Video'
    br = first('Composite:AvgBitrate')
    if br:
        info['overall_bitrate'] = str(br)
    af = first('Track2:AudioFormat')
    if af:
        info['audio_codec'] = str(af)
    elif 'MPEG:AudioLayer' in tags:
        info['audio_codec'] = f"MPEG Audio Layer {tags['MPEG:AudioLayer']}"
    sr = first('Track2:AudioSampleRate', 'MPEG:SampleRate')
    if sr:
        info['sample_rate'] = f"{int(sr):,} Hz" if str(sr).isdigit() else str(sr)
    ch = first('Track2:AudioChannels')
    info['channels'] = _channels(ch) if ch else str(first('MPEG:ChannelMode') or '--')
    ab = first('MPEG:AudioBitrate')
    if ab:
        info['audio_bitrate'] = str(ab)
    info['info_source'] = 'ExifTool'


def get_video_info(path: str, exif_tags: dict | None = None) -> dict:
    """
    Human-readable technical properties.  All values are strings ('--' when unknown)
    except 'duration_secs' (float).
    """
    info = _empty_info(path)

    try:
        st = os.stat(path)
        info['file_size'] = format_size(st.st_size)
        info['modified'] = datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')
    except OSError as e:
        logger.warning(f"stat failed for {path}: {e}")

    ext = os.path.splitext(path)[1].lower()
    if ext in SIDECAR_EXTENSIONS:
        from .exiftool_utils import sidecar_path_for
        sc = sidecar_path_for(path)
        info['metadata_storage'] = (f"XMP sidecar ({os.path.basename(sc)})" if os.path.isfile(sc)
                                    else "XMP sidecar (not created yet)")
    elif ext in EMBEDDED_EXTENSIONS:
        info['metadata_storage'] = "Embedded in file"

    data = probe_with_ffprobe(path)
    if data:
        try:
            _fill_from_ffprobe(info, data)
        except Exception as e:
            logger.warning(f"Could not interpret ffprobe output: {e}")
            data = None
    if not data and exif_tags:
        _fill_from_exiftool(info, exif_tags)
    return info


# ----------------------------------------------------------------------
# Poster frame
# ----------------------------------------------------------------------

def extract_poster_frame(path: str, duration_secs: float = 0.0, width: int = 480) -> bytes | None:
    """Grab one frame (~10% in, at most 30 s) as PNG bytes using ffmpeg; None on failure."""
    ffmpeg, _ = _tools()
    if not ffmpeg:
        return None
    at = min(max(duration_secs * 0.10, 0.0), 30.0) if duration_secs else 1.0
    cmd = [ffmpeg, '-v', 'error', '-ss', f"{at:.2f}", '-i', path, '-frames:v', '1',
           '-vf', f"scale={width}:-2", '-f', 'image2pipe', '-vcodec', 'png', '-']
    try:
        res = _run(cmd, timeout=30, binary=True)
        if res.returncode == 0 and res.stdout:
            return res.stdout
        # Seeking past the end of very short clips yields nothing — retry at 0
        if at > 0:
            cmd[cmd.index('-ss') + 1] = '0'
            res = _run(cmd, timeout=30, binary=True)
            if res.returncode == 0 and res.stdout:
                return res.stdout
        logger.debug(f"ffmpeg poster frame failed: {res.stderr[:300]!r}")
    except Exception as e:
        logger.debug(f"ffmpeg poster frame error: {e}")
    return None
