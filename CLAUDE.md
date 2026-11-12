# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Video Tag Writer (VTW) is a PyQt6 desktop application for viewing and editing descriptive metadata in **MP4, M4V, MPG and MPEG** video files. It is modeled on audio-tag-writer (ATW, `~/Projects/audio-tag-writer`) and keeps ATW's architecture. The metadata layer is **ExifTool** (via PyExifTool), not Mutagen. Current version: v0.1.0.

Why ExifTool, and the rules below: `notes/TOOL_COMPARISON_mutagen-vs-ffmpeg-vs-exiftool-video.md` (includes probe test results).

## Development Commands

```powershell
.\run.ps1                       # venv + deps + launch
python src/main.py [file]       # direct (venv active)
python -m pytest tests          # tests; integration tests need ExifTool + ffmpeg
```

## Critical Project Rules

### Timezone Convention
**ALL timestamps MUST use Central Time USA (CST/CDT), NEVER UTC** — changelog headers, `APP_TIMESTAMP`, docs.
Changelog header format: `## Video Tag Writer [X.Y.Z] - YYYY-MM-DD HHMM CST`.

### Version Numbering
`v0.X.Y` releases, `v0.X.Ya/b` point releases. Update: `constants.py` (APP_VERSION, APP_TIMESTAMP), `src/main.py` header, `README.md`, `CHANGELOG.md`.
`__commit_date__` in `src/video_tag_writer/__init__.py` is computed from the clock — never hardcode it.

### ExifTool rules (learned from the probe — do not regress)
1. **Never pass tag values as command-line arguments**: non-ASCII text is mangled on Windows. Values go through a UTF-8 JSON file (`-json=FILE`). See `exiftool_utils.write_tags`.
2. **Clear a field with a `-TAG=` delete.** JSON `null` writes the text "null", and JSON `""` writes an empty atom.
3. **`ItemList:ContentCreateDate` (©day)** accepts only a raw year (`Tag#` key) or `YYYY:MM:DD HH:MM:SS±TZ`. Use `metadata.date_tag_value()`.
4. **Integer atoms (TVSeason, TVEpisode)**: validate them (`int_field`). ExifTool parses "abc" as hex.
5. **MPG/MPEG are read-only to ExifTool.** Their descriptive metadata lives in a `<name>.xmp` sidecar, and only `XMP-*` tags can go there. Create a sidecar from `_EMPTY_XMP`, not `-o x.xmp video.mpg`, which copies tech tags into it.
6. `ItemList:Description` writes `©des` on files without `desc`, and ffprobe ignores `©des`. Keep `ItemList:Comment` as a Description alias.

### On hold
**Converting MPG to MP4 (remux)**: not to be built or tested until the user approves.

## Architecture

```python
class MainWindow(NavigationMixin, FileOpsMixin, MenuMixin,
                 ThemeMixin, HelpMixin, WindowMixin, QMainWindow):
```

Dependency flow: constants → config → exiftool_utils → metadata → video_utils/file_utils → widgets → mixins → main. **No circular imports.**

| Module | Purpose |
|---|---|
| `constants.py` | APP_*, extensions (embedded vs sidecar), `DEFAULT_MODES` field specs, detect rules |
| `config.py` | Config singleton → `~/.video_tag_writer_config.json` (`VTW_CONFIG_FILE` env overrides; tests use it) |
| `exiftool_utils.py` | Persistent ExifTool session, read/write, sidecar helpers, cover art, `detect_mode`, `tag_text` |
| `metadata.py` | `MetadataManager`, date conversion, `WritePlan` (pure; unit-testable without ExifTool) |
| `video_utils.py` | ffprobe technical info (ExifTool fallback), poster frames; picks the **newest** ffmpeg on PATH |
| `file_utils.py` | `get_video_files` |
| `navigation.py` / `file_ops.py` / `menu.py` / `window.py` / `theme*.py` / `help.py` | Mixins (as in ATW) |
| `widgets/metadata_panel.py` | Dynamic form; greys out MP4-only fields for sidecar files |
| `widgets/video_panel.py` | Cover art / poster frame (QThreadPool worker), storage status, technical table |
| `widgets/manage_modes_dialog.py` | Mode editor (Tag, Aliases, Widget, Max Chars, Options) |

### Field spec
`label`, `tag` (ExifTool `Group:Tag`), `widget` (line/text/hidden), `max_chars`, `aliases`, `date_field`, `list_field` (`;`-separated ↔ list), `int_field`, `auto_value` (`__app_version__` sentinel).
Read: first non-empty of tag + aliases. Write: value goes to the tag and every alias. For sidecar files, only `XMP-*` tags are written.

### Modes
| Mode | Detect tag | Notes |
|---|---|---|
| TV Episode | `ItemList:TVShow` | Most fields are MP4-only |
| General | `ItemList:Genre` | Archival never writes Genre |
| Archival Video | *(default)* | HSTL profile; every field has an XMP tag |

### Shared modules (external)
ThemeManager, Icon Manager Module, pyqt-app-info: referenced via `sys.path` as in ATW. `single_instance_guard.py` is vendored.

## Not yet done
- PyInstaller spec / `build_exe.ps1` (must bundle exiftool.exe; optionally ffmpeg/ffprobe)
- App icon (`resources/icons/` is empty; IMM is skipped when it has no icons)
- GitHub repo / CI workflow
