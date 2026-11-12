# Video Tag Writer Changelog

All notable changes to the Video Tag Writer project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Video Tag Writer [0.1.0] - 2026-11-11 2015 CST

### Added
- **Initial scaffold**, modeled on audio-tag-writer (ATW) v0.7.14a: the same main-window
  classes (Navigation, FileOps, Menu, Theme, Help, Window), the mode/field-spec system
  with aliases, auto-detect, Manage Modes, JSON export/import, View All Tags, Rename,
  recent files/directories, the single-instance guard, ThemeManager themes and zoom.
- **ExifTool metadata engine** (PyExifTool, one persistent `-stay_open` process),
  replacing ATW's Mutagen layer. The backend was chosen after a tool comparison and
  probe test — see `notes/TOOL_COMPARISON_mutagen-vs-ffmpeg-vs-exiftool-video.md`.
- **MP4 / M4V**: metadata written inside the file as iTunes-style `ItemList` atoms
  (shown by players and Windows Explorer) plus XMP aliases (archival schemas).
- **MPG / MPEG**: metadata written to a `<name>.xmp` sidecar, because MPEG Program
  Stream cannot hold descriptive tags. The video file itself is never modified. Fields
  with no XMP tag are greyed out for these files.
- **Three built-in modes**: Archival Video (HSTL profile; default), General, and
  TV Episode.
- **Video panel**: embedded cover art, or a poster frame extracted by ffmpeg on a
  background thread, plus storage status, Play / Show in Folder, Set/Remove Cover Art
  (MP4), and a technical table (container, duration, codecs, resolution, frame rate,
  scan type, audio, bitrates). Data comes from ffprobe when present, else ExifTool.
- **Date handling**: ISO `YYYY` / `YYYY-MM` / `YYYY-MM-DD` input is validated and
  converted per tag. `©day` accepts only a raw year or a full timestamp, so full dates
  are written as local midnight with the UTC offset, and the calendar date never shifts.
- **Integer field validation** (TV season/episode) — ExifTool would otherwise
  silently read `abc` as hex (2748).
- **Tools ▸ Keep Backup on Save** (ExifTool `*_original` files; off by default) and
  **Tools ▸ Tool Locations** (which ExifTool / ffmpeg / ffprobe are in use).
- Test suite: 51 tests, including end-to-end ExifTool round-trips on ffmpeg-generated
  MP4 and MPG clips (skipped automatically when the tools are absent).

### Changed (relative to ATW)
- **Rename** no longer makes a full-file backup copy before renaming (video files can be
  many GB); `os.rename` within one directory is atomic. Any XMP sidecar is renamed
  along with the video.
- **Manage Modes** keeps aliases, options (date/list/int) and hidden-field `auto_value`
  on OK. ATW's dialog drops every spec key except label, tag, widget and max_chars.
- Saving or switching modes reloads the file **without** re-running auto-detect, so a
  manually chosen mode is not overridden.
