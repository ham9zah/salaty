#!/usr/bin/env bash
# Salaty launcher — works from the source tree and an installed copy.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Snap can inject incompatible GTK/GDK libraries into child applications.
unset GTK_PATH GTK_EXE_PREFIX GDK_PIXBUF_MODULE_FILE GDK_PIXBUF_MODULEDIR
unset GIO_MODULE_DIR GTK_IM_MODULE_FILE GSETTINGS_SCHEMA_DIR LOCPATH

if [ -n "${WAYLAND_DISPLAY:-}" ]; then
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
else
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
fi

if [ -n "${SALATY_PYTHON:-}" ]; then
    PYTHON="$SALATY_PYTHON"
elif [ -f "$SCRIPT_DIR/.use-venv" ] && [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif [ -x /usr/bin/python3 ]; then
    PYTHON=/usr/bin/python3
else
    PYTHON=python3
fi

exec "$PYTHON" "$SCRIPT_DIR/salaty.py" "$@"
