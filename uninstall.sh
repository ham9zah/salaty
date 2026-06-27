#!/usr/bin/env bash
# Remove the user-local Salaty installation. User settings are preserved.
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
if [ -n "${SNAP:-}" ]; then
    DATA_HOME="$HOME/.local/share"
fi
INSTALL_DIR="$DATA_HOME/salaty"
APPLICATIONS_DIR="$DATA_HOME/applications"
ICONS_ROOT="$DATA_HOME/icons/hicolor"

rm -rf "$INSTALL_DIR"
rm -f "$HOME/.local/bin/salaty" "$APPLICATIONS_DIR/salaty.desktop"
rm -f "$HOME/.config/autostart/salaty.desktop"
for size in 32 48 64 128 256 512; do
    rm -f "$ICONS_ROOT/${size}x${size}/apps/salaty.png"
done

update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
gtk-update-icon-cache -f -t "$ICONS_ROOT" >/dev/null 2>&1 || true

printf 'تمت إزالة صلاتي. بقيت إعداداتك في ~/.config/salaty\n'
