# Video Metadata Tool Comparison: Mutagen vs FFmpeg vs ExifTool

**Project:** Video Tag Writer (VTW)
**Date:** 2026-11-11 1942 CST
**Target formats:** MP4 (incl. M4V), MPG, MPEG
**Design pattern:** audio-tag-writer (ATW, Mutagen) · photo tag-writer (PTW, ExifTool via PyExifTool)

---

## Why This Decision Matters

VTW needs a metadata backend for the same two operations ATW performs:

1. **Read** the current descriptive tags (plus technical stream info) from one file.
2. **Write** edited tags back without touching the audio/video streams.

The deciding factor is **MPG/MPEG**. MPEG-1/2 Program Stream (`.mpg` / `.mpeg`) has
**no standard container slot for descriptive metadata** (title, description, etc.).
None of the three candidates can embed tags inside an MPEG-PS file. The realistic
options for those files are:

- a **sidecar** file (e.g. `file.mpg` → `file.xmp`)
- **remuxing** to MP4 (stream copy, no re-encode)
- an **app-only record** (e.g. ATW-style JSON export)

MP4 is straightforward — all three tools can write it, with very different trade-offs.

---

## Capability Matrix

| | **Mutagen** (ATW) | **FFmpeg / ffprobe** | **ExifTool** (PTW) |
|---|---|---|---|
| **MP4/M4V read** | ✅ `ilst` atoms incl. freeform `----:com.apple.iTunes:*` | ✅ but normalized generic keys; unknown atoms may drop | ✅ every group: ItemList, UserData, Keys, XMP |
| **MP4/M4V write** | ✅ in-place, fast | ⚠️ only via full remux to a new file (`-c copy -map_metadata`); fixed key set unless `-movflags use_metadata_tags` | ✅ rewrites container, no re-encode |
| **Custom archival fields** | ✅ freeform atoms (TXXX equivalent) | ⚠️ `mdta` keys only, poorly read by players | ✅ XMP (Dublin Core, xmpMM, IPTC, …) — archival standard |
| **MPG/MPEG read (tags)** | ❌ cannot parse MPEG-PS at all | ✅ technical only (no tags exist) | ✅ technical only |
| **MPG/MPEG write** | ❌ | ❌ `mpeg` muxer ignores metadata | ❌ in-file · ✅ **XMP sidecar** |
| **Technical info** | ⚠️ audio-track only (length, bitrate, channels); no resolution/fps/video codec | ✅ best — full codec/stream detail | ✅ good — size, frame rate, bitrate, codec IDs |
| **Poster frame / thumbnail** | ❌ | ✅ grab a frame at any timestamp | ⚠️ embedded cover art/thumbnails only |
| **Cover art (`covr`)** | ✅ read/write | ⚠️ attach only via remux | ✅ read/write |
| **Dependency** | `pip install mutagen` (pure Python) | ~100 MB binary | ~10 MB binary + PyExifTool |
| **Per-file speed** | very fast | slow writes on large files (full copy + temp disk space) | ~0.3 s startup per call; `-stay_open` (PyExifTool) removes it |
| **Write safety** | in-place | writes new file, then swap | atomic rewrite; optional `_original` backup |

---

## Who Sees What in MP4

- **ItemList (iTunes-style `ilst`)** — `©nam` title, `©cmt` comment, `©ART` artist,
  `©day` date, `©gen` genre, `desc` description. Read by **Windows Explorer Properties,
  VLC, Apple apps, ffprobe**. This is what users will see.
- **XMP** (Adobe `uuid` box) — read by **Bridge, Lightroom, DAM systems, ExifTool**.
  Mostly ignored by consumer players.
- **UserData (`udta`)** — what FFmpeg writes for `.mov`; QuickTime Player reads it.
  Worth reading as a fallback.

For HSTL archival use, write **both ItemList and XMP** — the same idea as ATW's alias
frames (primary frame + cross-schema aliases written with the same value). Only
ExifTool does this natively.

---

## Assessment of Each Candidate

### Mutagen
- **Pros:** zero external binaries, pure Python, fast, exact ATW parity (code reuse).
- **Cons:** MPG/MPEG completely unsupported — not even technical info. No XMP. No video
  stream properties (resolution, frame rate, codec).
- **Verdict:** does not meet the MP4 + MPG + MPEG requirement.

### FFmpeg / ffprobe
- **Pros:** best technical inspection; can extract poster frames; can remux MPG → MP4.
- **Cons:** every metadata save rewrites the entire video file (slow, needs free disk,
  risk on large archival masters); generic key normalization loses fidelity; cannot tag
  MPG either.
- **Verdict:** wrong tool as the editor's writer; excellent as an optional helper.

### ExifTool
- **Pros:** reads/writes MP4 in every tag group; XMP for archival schemas; XMP sidecars
  for MPG/MPEG; already used by PTW via PyExifTool (shared backend and habits).
- **Cons:** external binary; per-call startup cost (solved by `-stay_open`).
- **Verdict:** best fit.

---

## Recommendation

**ExifTool as the metadata engine, ffmpeg/ffprobe as an optional helper.**

| Format | Read | Write |
|---|---|---|
| MP4 / M4V | ExifTool — ItemList + XMP + UserData fallback | In-file: ItemList (player-visible) + XMP aliases (archival) |
| MPG / MPEG | ExifTool technical info + XMP sidecar if present | XMP sidecar (`<name>.xmp`) |

- **ffprobe / ffmpeg** (if present): richer technical panel and a **poster frame** in the
  right-hand panel (the video analog of ATW's album art). The app degrades gracefully
  without them.
- **ATW pattern is preserved** — modes, field specs, aliases, panels, mixin chain. Only
  the tag-access layer changes: Mutagen frame IDs (`TIT2`, `TXXX:…`) become ExifTool
  group-qualified tag names (`ItemList:Title`, `XMP-dc:Description`).

---

## Options for MPG / MPEG

1. **XMP sidecar** *(recommended default)* — non-destructive, standards-based,
   readable by ExifTool and Adobe/DAM tools. Risk: the `.xmp` can be separated from
   the video.
2. **Remux MPG → MP4 on demand** (stream copy) — tags then travel inside the file,
   but this changes the preservation master's container (an archival-policy decision).
3. **Both** — sidecar by default plus a "Convert to MP4…" tool for selected files.
   *Status: on hold — not to be implemented until approved.*

---

## Probe Test Results

**Run:** 2026-11-11 ~1950 CST · Windows 11
**Tools:** ExifTool 12.60 (`~/bin/exiftool.exe`) · FFmpeg 7.1.1 gyan.dev full build
(`C:\Program Files\Video Downloader\ffmpeg\`) · Mutagen 1.48.1
**Test files:** 3-second `testsrc` clips — `t.mp4` (H.264 + AAC), `t.mpg` / `t.mpeg`
(MPEG-2 video + MP2 audio, Program Stream)

> Note: `~/bin/ffmpeg.exe` is an old build (`N-51106`) that lacks the `sine` /
> working `aevalsrc` filters. VTW should locate ffmpeg/ffprobe explicitly and prefer
> the newest build found, not just the first on `PATH`.

### Summary

| # | Test | Result |
|---|---|---|
| T1 | ExifTool writes MP4 ItemList + XMP (title, comment, publisher, grouping, copyright, dc:identifier, dc:contributor list, xmpMM:PreservedFileName) | ✅ all written, read back correctly |
| T1b | Non-ASCII (`—`, `é`) passed as **command-line args** | ❌ **mangled** (`Caf�` in ItemList, `Caf?` in XMP) |
| T1b | Same values via `-@ argfile` (UTF-8) | ✅ correct |
| T1c | Write via `-json=file.json` — Unicode, multi-line, list | ✅ correct |
| T1c | JSON `""` | ⚠️ writes an **empty string**, does not delete |
| T1c | JSON `null` | ❌ writes the **literal text `"null"`** |
| T1e | `-TAG=` (empty assignment) in argfile / command line | ✅ deletes the tag |
| T1e | `-json=` plus `-TAG=` deletes in **one** call | ✅ works |
| T1d | `ItemList:ContentCreateDate` (`©day`) formats | ⚠️ see *Dates* below |
| T2 | ffprobe (player view) of ExifTool-written MP4 | ✅ title, comment, grouping, copyright, date visible · ❌ `©des` description and `©pub` publisher not shown |
| T3 | Mutagen reads ExifTool-written MP4 | ✅ ilst atoms (incl. `©pub`, `©des`) · ❌ no XMP · ❌ no video properties (`info.width` absent) |
| T3 | Mutagen on `.mpg` | ❌ **misdetects as MP3** (reads the MP2 audio track, reports 6.06 s "sketchy" for a 3.01 s file) |
| T4 | ExifTool in-file write to `.mpg` / `.mpeg` | ❌ `Writing of MPG/MPEG files is not yet supported` |
| T5 | ExifTool technical read of `.mpg` | ✅ width/height, frame rate, audio layer/bitrate/sample rate, channel mode · ❌ no duration |
| T5b | ffprobe technical read of `.mpg` | ✅ codecs, size, fps, sample rate, channels, **duration**, overall bitrate |
| T6 | `ffmpeg -c copy -metadata title=…` into `.mpg` | ❌ metadata **silently dropped** (not in ffprobe output, string not present in file bytes); also emits buffer-underflow warnings on remux |
| T7 | ExifTool XMP sidecar for `.mpg` (`-o file.xmp`) | ✅ created; Unicode + lists correct; source `.mpg` unchanged (md5 verified) |
| T7 | Update existing sidecar in place | ✅ |
| T7 | Read video + sidecar in one call | ✅ |

### Dates (`ItemList:ContentCreateDate` / `©day`)

| Input | Result |
|---|---|
| `1948`, `1948-05-03`, `1948:05:03` | ❌ rejected (PrintConvInv) |
| `1948:05:03 00:00:00` (no TZ) | ❌ rejected (ValueConvInv) |
| `1948:05:03 00:00:00Z` or `…-06:00` | ✅ stored as ISO `1948-05-03T00:00:00Z`; ffprobe shows it as `date` |
| `-n 1948` (year only, raw) | ✅ stored as `1948` |
| `-n 1948-05`, `-n 1948-05-03T00:00:00Z`, `-n "May 3, 1948"` | ❌ rejected |

`XMP-dc:Date` accepts `1948-05` / `1948-05-03` but ExifTool **displays** them as
`1948:05` / `1948:05:03` (even with `-n`).

### Description atom quirk

ExifTool's `ItemList:Description` maps to **two** atoms: `desc` (what FFmpeg/players
read as *description*) and `©des`. On a file that already has `desc`, a write updates
both. On a file **without** `desc`, ExifTool creates only `©des`, which ffprobe does not
show. Writing a value to `ItemList:Comment` (`©cmt`) as well (as ATW already does for
Description) keeps the description visible in players either way.

### Design Implications for VTW

1. **Never pass tag values on the command line.** Write through `-json=<tmp>.json`
   (UTF-8, newlines, lists) and put deletes in the same call as `-TAG=` arguments.
   Use `-@ argfile` for any other value-bearing arguments.
2. **Delete, don't null.** An empty field must become a `-TAG=` delete, never JSON
   `null` (which writes "null") or `""` (which writes an empty atom).
3. **Date fields need conversion.** The UI accepts ISO `YYYY` / `YYYY-MM` /
   `YYYY-MM-DD`. Write `©day` as `YYYY` (with `-n`) or `YYYY:MM:DD 00:00:00Z`, and
   write `XMP-dc:Date` with the exact precision entered. Normalize ExifTool's
   colon display (`1948:05:03`) back to ISO on read.
4. **Description:** alias to `ItemList:Comment` (as ATW does) so it is visible in
   players regardless of the `desc` / `©des` quirk.
5. **MPG/MPEG:** read technical info (ffprobe preferred for duration and codecs, ExifTool
   as fallback), and read/write descriptive tags in a `<name>.xmp` sidecar. When
   creating a sidecar, write only the descriptive tags. A plain `-o x.xmp src.mpg`
   also copied `XMP-tiff:ImageWidth/Height` from the source.
6. **Mutagen is ruled out.** It has no MPG support (it misreads MPG as MP3) and no XMP.
7. **FFmpeg is ruled out as a writer**, confirmed for MPG (metadata dropped) and
   unnecessary for MP4. Keep it for technical info and poster frames.
8. **Option 3 (MPG → MP4 remux)** — not tested, **on hold** per instruction.
