#!/usr/bin/env bash
# VideoTagWriter launcher — creates/validates venv, installs deps, runs app.

set -e

APP_NAME="VideoTagWriter"
ENTRY_POINT="src/main.py"
VENV_DIR="venv"
REQUIREMENTS="requirements.txt"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

venv_valid() {
    local cfg="$VENV_DIR/pyvenv.cfg"
    [[ -f "$cfg" ]] || return 1
    local python_home
    python_home=$(grep -E '^home\s*=' "$cfg" | cut -d= -f2- | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')
    [[ -n "$python_home" ]] || return 1
    [[ -x "$python_home/python3" || -x "$python_home/python" ]]
}

find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            if "$cmd" --version &>/dev/null; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

if [[ -d "$VENV_DIR" ]] && ! venv_valid; then
    echo "[$APP_NAME] Existing venv has a broken Python reference, recreating..."
    rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
    echo "[$APP_NAME] Creating virtual environment..."
    PYTHON_EXE=$(find_python) || {
        echo "Error: no working Python found. Install Python from https://python.org" >&2
        exit 1
    }
    echo "[$APP_NAME] Using Python: $PYTHON_EXE"
    "$PYTHON_EXE" -m venv "$VENV_DIR" || { echo "Error: Failed to create venv." >&2; exit 1; }
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate" || { echo "Error: cannot find venv activate script" >&2; exit 1; }

MARKER="$VENV_DIR/.deps_installed"
INSTALL_DEPS=false
if [[ ! -f "$MARKER" ]]; then
    INSTALL_DEPS=true
elif [[ "$REQUIREMENTS" -nt "$MARKER" ]]; then
    INSTALL_DEPS=true
fi

if $INSTALL_DEPS; then
    echo "[$APP_NAME] Installing dependencies..."
    python -m pip install --upgrade pip -q
    pip install -r "$REQUIREMENTS" -q
    touch "$MARKER"
fi

python "$ENTRY_POINT" "$@"
