# Video Tag Writer

A desktop application for viewing and editing descriptive metadata in **MP4, MPG and MPEG** video files. It is built for archival workflows (the HSTL profile), and the design follows [Audio Tag Writer](https://github.com/juren53/audio-tag-writer).

## Features

- **MP4 / M4V — metadata embedded in the file.** Fields are written as iTunes-style atoms (seen by players, Windows Explorer and ffprobe) and also as XMP (Dublin Core and other archival schemas).
- **MPG / MPEG — metadata in an XMP sidecar.** MPEG Program Stream has no slot for descriptive tags, so VTW writes `<name>.xmp` next to the video and never modifies the video itself.
- **Three built-in modes**: *Archival Video* (HSTL profile), *General*, and *TV Episode*, plus your own modes via **Tools ▸ Manage Modes**.
- **Auto-detect mode on load** from the file's tags.
- **Video panel**: embedded cover art, or a poster frame grabbed from the video, plus technical info (container, duration, codecs, resolution, frame rate, scan type, audio, bitrates).
- **Directory navigation**: Prev / Next (↑ ↓) through all supported videos in a folder.
- **View All Tags**: a searchable table of every tag ExifTool sees, including the sidecar.
- **Export / Import JSON**, **Rename** (moves the sidecar too), **Copy FQFN**, recent files and directories, themes, zoom, and a single-instance guard.

## Requirements

- Python 3.10+
- PyQt6 ≥ 6.4.2, PyExifTool ≥ 0.5.6 (installed by the launcher)
- **ExifTool** (required): [exiftool.org](https://exiftool.org). It must be on `PATH`, or set `exiftool_path` in the config file.
- **ffmpeg / ffprobe** (optional): richer technical info and poster frames. If several builds are installed, VTW uses the newest one on `PATH`.

## Quick Start

```powershell
git clone https://github.com/juren53/video-tag-writer.git
cd video-tag-writer
.\run.ps1                      # creates venv, installs deps, launches
.\run.ps1 path\to\video.mp4    # open a file directly
```

Linux/macOS: `./run.sh`

## Where metadata goes

| Format | Stored in | Tag groups |
|---|---|---|
| MP4, M4V | the video file | `ItemList:*` (player-visible) + `XMP-*` (archival) |
| MPG, MPEG | `<name>.xmp` sidecar | `XMP-*` only; MP4-only fields are greyed out |

The sidecar uses the Adobe/ExifTool naming convention: `Newsreel.mpg` → `Newsreel.xmp`.
Keep the two files together when copying or archiving.

## Archival Video mode (HSTL profile)

| Field | Primary tag | Also written |
|---|---|---|
| Title | `ItemList:Title` | `XMP-dc:Title` |
| Description | `ItemList:Description` | `ItemList:Comment`, `XMP-dc:Description` |
| Accession Number | `XMP-dc:Identifier` | |
| Speakers / People | `XMP-dc:Contributor` (list, `;`-separated) | |
| Date Recorded | `XMP-dc:Date` | `ItemList:ContentCreateDate` |
| Restrictions | `ItemList:Copyright` | `XMP-dc:Rights` |
| Location | `XMP-iptcCore:Location` | |
| Production/Copyright | `ItemList:Publisher` | `XMP-dc:Publisher` |
| Original Filename | `XMP-xmpMM:PreservedFileName` | |
| Collection | `ItemList:Grouping` | `XMP-xmpDM:Album` |
| Source URL | `XMP-dc:Source` | |
| NAC URL | `XMP-dc:Relation` | |
| Institution ID | `XMP-photoshop:TransmissionReference` | |
| *(hidden)* Artist | `ItemList:Artist` = "Harry S. Truman Library" | `XMP-dc:Creator` |
| *(hidden)* Tagging Software | `XMP-xmp:CreatorTool` = "Video Tag Writer vX.Y.Z" | |

Dates are entered as `YYYY`, `YYYY-MM` or `YYYY-MM-DD`.

## Keyboard shortcuts

| Key | Action |
|---|---|
| Ctrl+O | Open file |
| ↑ / ↓ | Previous / next video in folder |
| Ctrl+S | Save metadata |
| F2 | Rename file (and sidecar) |
| F5 | Refresh |
| Ctrl+T | View all tags |
| Ctrl+L | Clear fields |
| Ctrl+Shift+C | Copy fully qualified file name |
| Ctrl+D | Toggle dark mode |
| Ctrl + / − / 0 | Zoom in / out / reset |

## Development

```powershell
python -m pytest tests          # 51 tests; ExifTool integration tests auto-skip if tools are missing
```

## Building the Windows EXE

```powershell
.\build_exe.ps1                  # -> dist\video-tag-writer.exe (~41 MB, ExifTool bundled)
.\build_exe.ps1 -IncludeFFmpeg   # also bundle ffmpeg + ffprobe (much larger)
.\build_exe.ps1 -ExifTool C:\tools\exiftool.exe   # bundle a specific ExifTool
```

The script creates or updates `venv\`, runs the test suite, generates the EXE version resource, and builds with `video-tag-writer.spec`. It then runs the built EXE with `--self-test`, which checks that the shared modules, the bundled ExifTool, the version resource, the docs, and the Qt main window all work inside the frozen bundle. The build fails if any check fails.

The build needs `~/Projects/ThemeManager` and `~/Projects/Icon_Manager_Module`, plus an `exiftool.exe`. That can be the single-file build (≤ 12.87) or the newer exe + `exiftool_files` folder.

Background on the choice of ExifTool over Mutagen and FFmpeg:
[notes/TOOL_COMPARISON_mutagen-vs-ffmpeg-vs-exiftool-video.md](notes/TOOL_COMPARISON_mutagen-vs-ffmpeg-vs-exiftool-video.md).

## License

TBD
