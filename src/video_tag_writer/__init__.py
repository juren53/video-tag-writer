"""Video Tag Writer — PyQt6 metadata viewer/editor for MP4, MPG and MPEG video files."""

import datetime as _dt, time as _time

from .constants import APP_VERSION as __version__  # noqa: F401

_now = _dt.datetime.now()
_tz_full = _time.tzname[_time.localtime().tm_isdst]
_tz = "".join(w[0] for w in _tz_full.split())  # "Central Daylight Time" -> "CDT"
__commit_date__ = _now.strftime("%Y-%m-%d %H%M ") + _tz
