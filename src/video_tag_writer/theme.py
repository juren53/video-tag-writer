"""
VideoTagWriter - ThemeManager integration.

Sets up the ThemeManager module path and re-exports the helpers the app needs.
Registers four VTW-specific themes (Warm Light, High Contrast, Monokai,
GitHub Dark) into the global registry alongside the six built-in themes,
giving VideoTagWriter ten themes in total.
"""

from __future__ import annotations
import os
import sys

# Source runs only: the frozen EXE must use its bundled copy, or a module missing from
# the bundle goes unnoticed on the build machine (ATW v0.7.14a).
_TM_PATH = os.path.expanduser("~/Projects/ThemeManager")
if (not getattr(sys, 'frozen', False)
        and os.path.isdir(_TM_PATH) and _TM_PATH not in sys.path):
    sys.path.insert(0, _TM_PATH)

from theme_manager import (  # noqa: F401
    ThemeColors, UIPalette, Theme, ThemeCategory,
    get_theme_registry, get_fusion_palette, detect_system_theme,
)

DEFAULT_THEME = "light"

_DARK_THEMES = {"dark", "solarized_dark", "dracula", "high_contrast", "monokai", "github_dark"}


def is_dark_theme(name: str) -> bool:
    return name in _DARK_THEMES


# Migrate old display-name keys (stored in config files before this migration)
# to ThemeManager internal registry keys.
LEGACY_NAME_MAP: dict[str, str] = {
    "Default Light":   "light",
    "Warm Light":      "warm_light",
    "Dark":            "dark",
    "Solarized Light": "solarized_light",
    "Solarized Dark":  "solarized_dark",
    "High Contrast":   "high_contrast",
    "Monokai":         "monokai",
    "GitHub Dark":     "github_dark",
}


def _register_vtw_themes() -> None:
    """Register VideoTagWriter-specific themes into the global ThemeRegistry."""
    registry = get_theme_registry()

    registry.register_theme(Theme(
        name="warm_light",
        display_name="Warm Light",
        content_colors=ThemeColors(
            heading_color="#504741",
            body_text_color="#504741",
            background_color="#eee9e0",
            link_color="#6699cc",
            blockquote_color="#7a7068",
            code_bg_color="#e6e1d7",
            border_color="#b4aa9a",
        ),
        ui_palette=UIPalette(
            window_color="#eee9e0",
            window_text_color="#504741",
            base_color="#f0ebe2",
            alternate_base_color="#e6e1d7",
            text_color="#504741",
            button_color="#e6e1d7",
            button_text_color="#504741",
            highlight_color="#6699cc",
            highlighted_text_color="#ffffff",
            secondary_highlight_color="#cc6666",
        ),
        description="Warm neutral light theme",
        is_built_in=False,
        category=ThemeCategory.CUSTOM,
    ))

    registry.register_theme(Theme(
        name="high_contrast",
        display_name="High Contrast",
        content_colors=ThemeColors(
            heading_color="#ffffff",
            body_text_color="#ffffff",
            background_color="#000000",
            link_color="#ffff00",
            blockquote_color="#cccccc",
            code_bg_color="#1a1a1a",
            border_color="#ffffff",
        ),
        ui_palette=UIPalette(
            window_color="#000000",
            window_text_color="#ffffff",
            base_color="#000000",
            alternate_base_color="#1a1a1a",
            text_color="#ffffff",
            button_color="#333333",
            button_text_color="#ffffff",
            highlight_color="#ffff00",
            highlighted_text_color="#000000",
            secondary_highlight_color="#ff8800",
        ),
        description="High contrast theme for accessibility",
        is_built_in=False,
        category=ThemeCategory.CUSTOM,
    ))

    registry.register_theme(Theme(
        name="monokai",
        display_name="Monokai",
        content_colors=ThemeColors(
            heading_color="#a6e22e",
            body_text_color="#f8f8f2",
            background_color="#272822",
            link_color="#66d9e8",
            blockquote_color="#75715e",
            code_bg_color="#3e3d32",
            border_color="#75715e",
        ),
        ui_palette=UIPalette(
            window_color="#272822",
            window_text_color="#f8f8f2",
            base_color="#1e1f29",
            alternate_base_color="#49483e",
            text_color="#f8f8f2",
            button_color="#49483e",
            button_text_color="#f8f8f2",
            highlight_color="#a6e22e",
            highlighted_text_color="#272822",
            secondary_highlight_color="#fd971f",
        ),
        description="Classic Monokai dark theme",
        is_built_in=False,
        category=ThemeCategory.POPULAR,
    ))

    registry.register_theme(Theme(
        name="github_dark",
        display_name="GitHub Dark",
        content_colors=ThemeColors(
            heading_color="#58a6ff",
            body_text_color="#c9d1d9",
            background_color="#0d1117",
            link_color="#58a6ff",
            blockquote_color="#8b949e",
            code_bg_color="#161b22",
            border_color="#30363d",
        ),
        ui_palette=UIPalette(
            window_color="#161b22",
            window_text_color="#c9d1d9",
            base_color="#0d1117",
            alternate_base_color="#21262d",
            text_color="#c9d1d9",
            button_color="#21262d",
            button_text_color="#c9d1d9",
            highlight_color="#388bfd",
            highlighted_text_color="#ffffff",
            secondary_highlight_color="#d29922",
        ),
        description="GitHub Dark theme",
        is_built_in=False,
        category=ThemeCategory.POPULAR,
    ))


_register_vtw_themes()
