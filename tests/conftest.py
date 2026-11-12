"""
Shared pytest setup.

* Points VTW_CONFIG_FILE at a temp file *before* the package is imported, so the
  tests never read or overwrite the user's ~/.video_tag_writer_config.json.
* Provides session-scoped real video clips (MP4 + MPG) generated with ffmpeg for the
  ExifTool integration tests; those tests are skipped when ffmpeg/ExifTool are absent.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

_TMP_CFG_DIR = tempfile.mkdtemp(prefix="vtw_test_cfg_")
os.environ["VTW_CONFIG_FILE"] = os.path.join(_TMP_CFG_DIR, "config.json")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))


def pytest_sessionfinish(session, exitstatus):
    try:
        from video_tag_writer import exiftool_utils
        exiftool_utils.shutdown()
    except Exception:
        pass
    shutil.rmtree(_TMP_CFG_DIR, ignore_errors=True)


def _exiftool_ok() -> bool:
    try:
        from video_tag_writer import exiftool_utils
        exiftool_utils.check_exiftool_available()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def exiftool_available():
    if not _exiftool_ok():
        pytest.skip("ExifTool / PyExifTool not available")


@pytest.fixture(scope="session")
def clip_dir(tmp_path_factory, exiftool_available):
    """Directory holding pristine 2-second test clips: clip.mp4 and clip.mpg."""
    from video_tag_writer.video_utils import find_ff_tools
    ffmpeg, _ = find_ff_tools('')
    if not ffmpeg:
        pytest.skip("ffmpeg not available to generate test clips")
    d = tmp_path_factory.mktemp("clips")
    src = ["-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=2"]
    jobs = {
        "clip.mp4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"],
        "clip.mpg": ["-c:v", "mpeg2video", "-c:a", "mp2", "-shortest"],
    }
    for name, codec in jobs.items():
        res = subprocess.run([ffmpeg, "-v", "error", "-y", *src, *codec, str(d / name)],
                             capture_output=True)
        if res.returncode != 0 or not (d / name).exists():
            pytest.skip(f"ffmpeg could not generate {name}: {res.stderr[-300:]!r}")
    return d


@pytest.fixture
def clips(clip_dir, tmp_path):
    """Per-test copies of the clips (tests may modify them)."""
    out = {}
    for name in ("clip.mp4", "clip.mpg"):
        dst = tmp_path / name
        shutil.copy2(clip_dir / name, dst)
        out[name.split('.')[1]] = str(dst)
    return out
