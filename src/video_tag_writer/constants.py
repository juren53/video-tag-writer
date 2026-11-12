"""
Video Tag Writer - Constants, version info, and default mode definitions.

Field spec format (interpreted by MetadataManager):

    {
        "label":      str,          # UI label and internal key
        "tag":        str,          # Primary ExifTool tag, group-qualified ("ItemList:Title")
        "widget":     str,          # "line" | "text" | "hidden"
        "max_chars":  int,          # Truncation limit on read (default 2000)
        "aliases":    [str, ...],   # Extra tags written with the same value; read fallback
        "date_field": bool,         # ISO date input (YYYY / YYYY-MM / YYYY-MM-DD), converted per tag
        "list_field": bool,         # "a; b; c" in the UI  <->  list value in the file
        "int_field":  bool,         # value must be a whole number (ExifTool parses "abc" as hex!)
        "auto_value": str,          # Value for hidden fields; "__app_version__" is a sentinel
    }

Tag groups and where they can be written:

    ItemList:*   MP4 'ilst' atoms (iTunes-style) — what players, Windows Explorer and
                 ffprobe show.  Embedded files only (MP4/M4V).
    XMP-*:*      XMP — archival schemas (Dublin Core etc.).  Written into MP4/M4V and
                 into the .xmp sidecar used for MPG/MPEG.

See notes/TOOL_COMPARISON_mutagen-vs-ffmpeg-vs-exiftool-video.md for the probe results
behind these choices.
"""

APP_NAME = "Video Tag Writer"
APP_VERSION = "0.1.0"
APP_TIMESTAMP = "2026-11-11 2015 CST"
APP_ORGANIZATION = "SynchroSoft"
APP_USER_MODEL_ID = "SynchroSoft.VTW"
GITHUB_REPO = "juren53/video-tag-writer"

# Files whose metadata is written inside the file
EMBEDDED_EXTENSIONS = ['.mp4', '.m4v']
# Files that cannot hold descriptive tags — metadata goes to a <name>.xmp sidecar
SIDECAR_EXTENSIONS = ['.mpg', '.mpeg']

VIDEO_EXTENSIONS = EMBEDDED_EXTENSIONS + SIDECAR_EXTENSIONS

# Tag groups that can be written into an XMP sidecar
SIDECAR_WRITABLE_PREFIX = "XMP-"

# Detection rules: ordered dict of {mode_name: tag}.
# First mode whose tag is non-empty in the file (or sidecar) wins.
DEFAULT_DETECT_FRAMES = {
    "TV Episode":     "ItemList:TVShow",
    "General":        "ItemList:Genre",   # archival profile never writes Genre
    "Archival Video": "",                 # no discriminating tag — default
}
DEFAULT_DETECT_DEFAULT = "Archival Video"

DEFAULT_MODES = {
    # HSTL archival profile — mirrors ATW "Archival Recording".
    # Every visible field has an XMP tag (primary or alias) so it survives in an
    # MPG/MPEG sidecar, and player-visible ItemList atoms where one fits.
    "Archival Video": [
        {"label": "Title",               "tag": "ItemList:Title",          "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-dc:Title"]},
        # ItemList:Comment alias keeps the description visible in players: on files without
        # an existing 'desc' atom ExifTool writes Description to '©des', which ffprobe ignores.
        {"label": "Description",         "tag": "ItemList:Description",    "widget": "text", "max_chars": 1000,
         "aliases": ["ItemList:Comment", "XMP-dc:Description"]},
        {"label": "Accession Number",    "tag": "XMP-dc:Identifier",       "widget": "line", "max_chars": 2000},
        {"label": "Speakers / People",   "tag": "XMP-dc:Contributor",      "widget": "line", "max_chars": 2000,
         "list_field": True},
        {"label": "Date Recorded",       "tag": "XMP-dc:Date",             "widget": "line", "max_chars": 2000,
         "aliases": ["ItemList:ContentCreateDate"], "date_field": True},
        {"label": "Restrictions",        "tag": "ItemList:Copyright",      "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-dc:Rights"]},
        {"label": "Location",            "tag": "XMP-iptcCore:Location",   "widget": "line", "max_chars": 2000},
        {"label": "Production/Copyright", "tag": "ItemList:Publisher",     "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-dc:Publisher"]},
        {"label": "Original Filename",   "tag": "XMP-xmpMM:PreservedFileName", "widget": "line", "max_chars": 2000},
        {"label": "Collection",          "tag": "ItemList:Grouping",       "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-xmpDM:Album"]},
        {"label": "Source URL",          "tag": "XMP-dc:Source",           "widget": "line", "max_chars": 2000},
        {"label": "NAC URL",             "tag": "XMP-dc:Relation",         "widget": "line", "max_chars": 2000},
        {"label": "Institution ID",      "tag": "XMP-photoshop:TransmissionReference", "widget": "line", "max_chars": 2000},
        # --- Hidden auto-written fields (not shown in UI) ---
        {"label": "Artist",           "tag": "ItemList:Artist",     "widget": "hidden",
         "auto_value": "Harry S. Truman Library", "aliases": ["XMP-dc:Creator"]},
        {"label": "Tagging Software", "tag": "XMP-xmp:CreatorTool", "widget": "hidden",
         "auto_value": "__app_version__"},
    ],
    "General": [
        {"label": "Title",       "tag": "ItemList:Title",       "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-dc:Title"]},
        {"label": "Artist",      "tag": "ItemList:Artist",      "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-dc:Creator"]},
        {"label": "Album",       "tag": "ItemList:Album",       "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-xmpDM:Album"]},
        {"label": "Date",        "tag": "XMP-dc:Date",          "widget": "line", "max_chars": 2000,
         "aliases": ["ItemList:ContentCreateDate"], "date_field": True},
        {"label": "Genre",       "tag": "ItemList:Genre",       "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-xmpDM:Genre"]},
        {"label": "Description", "tag": "ItemList:Description", "widget": "text", "max_chars": 1000,
         "aliases": ["XMP-dc:Description"]},
        {"label": "Comment",     "tag": "ItemList:Comment",     "widget": "text", "max_chars": 1000,
         "aliases": ["XMP-xmpDM:LogComment"]},
        {"label": "Keywords",    "tag": "XMP-dc:Subject",       "widget": "line", "max_chars": 2000,
         "list_field": True},
        {"label": "Copyright",   "tag": "ItemList:Copyright",   "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-dc:Rights"]},
    ],
    # TV/episode atoms exist only in MP4 — these fields are not saved to MPG sidecars
    # except where an XMP alias is given.
    "TV Episode": [
        {"label": "Title",            "tag": "ItemList:Title",           "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-dc:Title"]},
        {"label": "Show",             "tag": "ItemList:TVShow",          "widget": "line", "max_chars": 2000},
        {"label": "Season",           "tag": "ItemList:TVSeason",        "widget": "line", "max_chars": 10,
         "int_field": True},
        {"label": "Episode",          "tag": "ItemList:TVEpisode",       "widget": "line", "max_chars": 10,
         "int_field": True},
        {"label": "Episode ID",       "tag": "ItemList:TVEpisodeID",     "widget": "line", "max_chars": 2000},
        {"label": "Network",          "tag": "ItemList:TVNetworkName",   "widget": "line", "max_chars": 2000},
        {"label": "Air Date",         "tag": "ItemList:ContentCreateDate", "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-dc:Date"], "date_field": True},
        {"label": "Genre",            "tag": "ItemList:Genre",           "widget": "line", "max_chars": 2000,
         "aliases": ["XMP-xmpDM:Genre"]},
        {"label": "Description",      "tag": "ItemList:Description",     "widget": "text", "max_chars": 1000,
         "aliases": ["XMP-dc:Description"]},
        {"label": "Long Description", "tag": "ItemList:LongDescription", "widget": "text", "max_chars": 4000},
    ],
}
