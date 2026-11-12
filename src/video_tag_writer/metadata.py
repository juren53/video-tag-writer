"""
Video Tag Writer - MetadataManager: field-spec driven read/write via ExifTool.

Same contract as ATW's MetadataManager (label-keyed values, mode field specs, alias
fan-out on save, alias fallback on read, JSON export/import).  The tag access layer
is ExifTool instead of Mutagen, and MPG/MPEG files are written to an XMP sidecar.
"""

import datetime as _dt
import json
import logging
import os
import re
from dataclasses import dataclass, field

from .config import config
from .constants import APP_NAME, APP_VERSION, SIDECAR_WRITABLE_PREFIX
from .exiftool_utils import (
    ExifToolError, read_metadata, tag_text, uses_sidecar, sidecar_path_for,
    ensure_sidecar, write_tags,
)

logger = logging.getLogger(__name__)

APP_VERSION_SENTINEL = '__app_version__'


# ----------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------

_ISO_INPUT = re.compile(r'^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$')
_ANY_DATE = re.compile(r'^\s*(\d{4})(?:[:\-](\d{2}))?(?:[:\-](\d{2}))?')


def parse_iso_date(value: str) -> tuple[int, int | None, int | None]:
    """
    Parse 'YYYY', 'YYYY-MM' or 'YYYY-MM-DD' (the only formats the UI accepts).
    Raises ValueError with a user-facing message otherwise.
    """
    m = _ISO_INPUT.match(value.strip())
    if not m:
        raise ValueError(f'"{value}" is not a date in YYYY, YYYY-MM or YYYY-MM-DD form')
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else None
    day = int(m.group(3)) if m.group(3) else None
    if month is not None and not 1 <= month <= 12:
        raise ValueError(f'"{value}": month must be 01-12')
    if day is not None:
        try:
            _dt.date(year, month, day)
        except ValueError:
            raise ValueError(f'"{value}" is not a valid calendar date')
    return year, month, day


def display_date(raw: str) -> str:
    """
    Normalize a date read from ExifTool to ISO for display:
    '1948:05:03 00:00:00-06:00' -> '1948-05-03', '1948:05' -> '1948-05', '1948' -> '1948'.
    Unrecognized text is returned unchanged.
    """
    if not raw:
        return ''
    m = _ANY_DATE.match(str(raw))
    if not m:
        return str(raw)
    return '-'.join(p for p in m.groups() if p)


def _utc_offset_for(date: _dt.date) -> str:
    """Local UTC offset ('-06:00') for local midnight on date (falls back to today's)."""
    try:
        aware = _dt.datetime(date.year, date.month, date.day).astimezone()
    except (OverflowError, OSError, ValueError):
        # Windows cannot localize pre-1970 timestamps
        aware = _dt.datetime.now().astimezone()
    off = aware.strftime('%z')  # '-0600'
    return f"{off[:3]}:{off[3:]}" if len(off) == 5 else 'Z'


def date_tag_value(tag: str, iso_value: str) -> tuple[str, str]:
    """
    Convert an ISO date entered in the UI into (json_key, value) for one tag.

    * XMP-* tags take ISO dates at any precision, unchanged.
    * ItemList:ContentCreateDate ('©day') only accepts a raw year or a full
      'YYYY:MM:DD HH:MM:SS<tz>' value (probe T1d).  Year or year-month input is
      written as a raw year ('Tag#' key); a full date is written as local midnight
      with the local UTC offset, so the calendar date never shifts.
    """
    year, month, day = parse_iso_date(iso_value)
    if tag.startswith('XMP-'):
        parts = [f"{year:04d}"]
        if month is not None:
            parts.append(f"{month:02d}")
        if day is not None:
            parts.append(f"{day:02d}")
        return tag, '-'.join(parts)
    if day is None:
        return f"{tag}#", f"{year:04d}"
    offset = _utc_offset_for(_dt.date(year, month, day))
    return tag, f"{year:04d}:{month:02d}:{day:02d} 00:00:00{offset}"


# ----------------------------------------------------------------------
# Write plan
# ----------------------------------------------------------------------

@dataclass
class WritePlan:
    target: str                                   # file ExifTool writes (video or .xmp)
    sidecar: bool                                 # True if target is an XMP sidecar
    set_values: dict = field(default_factory=dict)
    delete_tags: list = field(default_factory=list)
    skipped: list = field(default_factory=list)   # labels with a value that cannot be stored

    @property
    def empty(self) -> bool:
        return not self.set_values and not self.delete_tags


def _base_tag(key: str) -> str:
    return key[:-1] if key.endswith('#') else key


def field_tags(spec: dict) -> list[str]:
    """Primary tag followed by aliases, without duplicates or blanks."""
    out = []
    for t in [spec.get('tag', '')] + list(spec.get('aliases', [])):
        if t and t not in out:
            out.append(t)
    return out


def storable_in_sidecar(spec: dict) -> bool:
    """True if at least one of the field's tags can be written to an XMP sidecar."""
    return any(t.startswith(SIDECAR_WRITABLE_PREFIX) for t in field_tags(spec))


# ----------------------------------------------------------------------
# Manager
# ----------------------------------------------------------------------

class MetadataManager:
    """Manages video metadata read/write via ExifTool."""

    def __init__(self):
        self._values = {}       # label -> str value
        self._field_specs = []  # list of spec dicts from active mode
        self.current_path = None
        self._rebuild_from_mode()

    # -- mode ---------------------------------------------------------------

    def _rebuild_from_mode(self, mode_name=None):
        self._field_specs = config.get_mode_fields(mode_name)
        self._reset_values()

    def _reset_values(self):
        self._values = {}
        for spec in self._field_specs:
            label = spec['label']
            self._values[label] = spec.get('auto_value', '') if spec.get('widget') == 'hidden' else ''

    def reload_mode(self, mode_name=None):
        """Switch to a different mode, clearing current values."""
        self._rebuild_from_mode(mode_name)
        self.current_path = None

    def get_field_specs(self):
        return list(self._field_specs)

    # -- field access -------------------------------------------------------

    def get_field(self, label, default=''):
        return self._values.get(label, default)

    def set_field(self, label, value):
        self._values[label] = value

    def get_all_fields(self):
        return dict(self._values)

    def clear(self):
        self._rebuild_from_mode()
        self.current_path = None

    # -- read ---------------------------------------------------------------

    def load_from_file(self, path: str) -> bool:
        """Read tags with ExifTool (plus sidecar for MPG/MPEG) into the field store."""
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return False
        try:
            file_tags, sidecar_tags = read_metadata(path)
        except ExifToolError as e:
            logger.error(f"ExifToolError loading '{path}': {e}")
            self._reset_values()
            self.current_path = path
            return False
        self.load_from_tags(path, sidecar_tags if sidecar_tags is not None else file_tags)
        return True

    def load_from_tags(self, path: str, tags: dict):
        """Populate field values from an already-read tag dict."""
        self._reset_values()
        self.current_path = path
        for spec in self._field_specs:
            if spec.get('widget') == 'hidden':
                continue
            raw = ''
            for tag in field_tags(spec):
                raw = tag_text(tags, tag)
                if raw:
                    break
            if raw and spec.get('date_field'):
                raw = display_date(raw)
            self._values[spec['label']] = self._sanitize_value(raw, spec.get('max_chars', 2000))
        logger.info(f"Loaded metadata for '{path}'")

    # -- validate / plan / write -------------------------------------------

    def validate(self) -> list[str]:
        """Return user-facing problems with the current values (empty list = OK)."""
        problems = []
        for spec in self._field_specs:
            if spec.get('widget') == 'hidden':
                continue
            label = spec['label']
            value = self._values.get(label, '').strip()
            if not value:
                continue
            if spec.get('date_field'):
                try:
                    parse_iso_date(value)
                except ValueError as e:
                    problems.append(f"{label}: {e}")
            if spec.get('int_field') and not value.isdigit():
                problems.append(f'{label}: "{value}" must be a whole number')
        return problems

    def _resolved_value(self, spec: dict) -> str:
        if spec.get('widget') == 'hidden':
            auto = spec.get('auto_value', '')
            return f"{APP_NAME} v{APP_VERSION}" if auto == APP_VERSION_SENTINEL else auto
        return self._values.get(spec['label'], '').strip()

    def build_write_plan(self, path: str) -> WritePlan:
        """Translate the current values into ExifTool set/delete operations for path."""
        sidecar = uses_sidecar(path)
        plan = WritePlan(target=sidecar_path_for(path) if sidecar else path, sidecar=sidecar)

        for spec in self._field_specs:
            value = self._resolved_value(spec)
            tags = field_tags(spec)
            if sidecar:
                writable = [t for t in tags if t.startswith(SIDECAR_WRITABLE_PREFIX)]
                if value and not writable and spec.get('widget') != 'hidden':
                    plan.skipped.append(spec['label'])
                tags = writable

            for tag in tags:
                if not value:
                    plan.delete_tags.append(tag)
                    continue
                if spec.get('date_field'):
                    key, val = date_tag_value(tag, value)
                elif spec.get('list_field'):
                    key = tag
                    val = [p.strip() for p in value.split(';') if p.strip()]
                else:
                    key, val = tag, value
                # A later field writing the same tag wins; drop any stale raw/non-raw twin
                for existing in list(plan.set_values):
                    if _base_tag(existing) == _base_tag(key):
                        del plan.set_values[existing]
                plan.set_values[key] = val

        # A tag that is both set (by one field) and deleted (by another) is kept.
        written = {_base_tag(k) for k in plan.set_values}
        deduped = []
        for t in plan.delete_tags:
            if t not in written and t not in deduped:
                deduped.append(t)
        plan.delete_tags = deduped
        return plan

    def save_to_file(self, path: str) -> WritePlan:
        """
        Write current values to path (MP4/M4V) or its XMP sidecar (MPG/MPEG).
        Returns the executed WritePlan.  Raises ValueError for invalid input and
        ExifToolError for write failures.
        """
        problems = self.validate()
        if problems:
            raise ValueError("Please correct the following before saving:\n\n" + "\n".join(problems))

        plan = self.build_write_plan(path)
        if plan.sidecar:
            if not plan.set_values and not os.path.exists(plan.target):
                logger.info("No values to store and no sidecar exists — nothing written")
                plan.delete_tags = []
                return plan
            ensure_sidecar(path)

        write_tags(plan.target, plan.set_values, plan.delete_tags, keep_backup=config.keep_backup)
        logger.info(f"Saved metadata to '{plan.target}'")
        return plan

    # -- export / import ----------------------------------------------------

    def export_to_json(self, path: str) -> bool:
        try:
            data = {
                'filename':    os.path.basename(self.current_path or ''),
                'export_date': _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'mode':        config.get_active_mode(),
                'metadata':    self._values,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"Exported metadata to '{path}'")
            return True
        except Exception as e:
            logger.error(f"Error exporting metadata: {e}")
            return False

    def import_from_json(self, path: str) -> bool:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            imported = data.get('metadata', data)
            for label in self._values:
                if label in imported:
                    self._values[label] = self._sanitize_value(str(imported[label]))
            logger.info(f"Imported metadata from '{path}'")
            return True
        except Exception as e:
            logger.error(f"Error importing metadata: {e}")
            return False

    # -- sanitization -------------------------------------------------------

    @staticmethod
    def _sanitize_value(value, max_chars: int = 2000) -> str:
        if not isinstance(value, str):
            return ''
        value = value.replace('\x00', '')
        value = value.replace('\r\n', '\n').replace('\r', '\n')
        value = value.strip()
        if len(value) > max_chars:
            value = value[:max_chars]
        return value
