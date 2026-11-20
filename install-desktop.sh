#!/usr/bin/env bash
# Install (or remove) Video Tag Writer in the Linux System Menu and on PATH.
# User-level install — no sudo. Tested on LMDE / Cinnamon.
#   ./install-desktop.sh              install menu entry + `vtw` command
#   ./install-desktop.sh --uninstall  remove both

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DESKTOP="$PROJECT_DIR/assets/VTW.desktop"
APPS_DIR="$HOME/.local/share/applications"
DEST_DESKTOP="$APPS_DIR/vtw.desktop"
BIN_DIR="$HOME/.local/bin"
DEST_BIN="$BIN_DIR/vtw"

uninstall() {
    rm -f "$DEST_DESKTOP"
    [[ -L "$DEST_BIN" ]] && rm -f "$DEST_BIN"
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
    echo "Removed $DEST_DESKTOP and $DEST_BIN"
    exit 0
}

[[ "${1:-}" == "--uninstall" ]] && uninstall

[[ -f "$SRC_DESKTOP" ]] || { echo "Missing $SRC_DESKTOP" >&2; exit 1; }

chmod +x "$PROJECT_DIR/run.sh"
mkdir -p "$APPS_DIR" "$BIN_DIR"

# System Menu entry: rewrite the hard-coded paths to this checkout's location.
sed "s|/home/juren/Projects/video-tag-writer|$PROJECT_DIR|g" "$SRC_DESKTOP" > "$DEST_DESKTOP"
chmod 644 "$DEST_DESKTOP"

command -v desktop-file-validate >/dev/null 2>&1 && desktop-file-validate "$DEST_DESKTOP" || true
update-desktop-database "$APPS_DIR" 2>/dev/null || true
gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor/" 2>/dev/null || true

# PATH command: ~/.local/bin/vtw -> run.sh
if [[ -e "$DEST_BIN" && ! -L "$DEST_BIN" ]]; then
    echo "Warning: $DEST_BIN exists and is not a symlink; left unchanged." >&2
else
    ln -sfn "$PROJECT_DIR/run.sh" "$DEST_BIN"
    echo "Linked $DEST_BIN -> $PROJECT_DIR/run.sh"
fi
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Note: $BIN_DIR is not on your PATH; add it in ~/.profile." ;;
esac

echo "Installed $DEST_DESKTOP"
echo "Video Tag Writer should now appear in the System Menu (Sound & Video / Accessories)."
echo "Run it from a terminal with: vtw [file]"
echo "If the menu entry does not show immediately, restart Cinnamon (Ctrl+Alt+Esc) or log out and back in."
