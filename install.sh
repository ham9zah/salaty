#!/usr/bin/env bash
# Salaty user-local installer for Linux
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
# Terminals launched by a Snap IDE may inject a private XDG data directory.
# Desktop files installed there are invisible to the host desktop.
if [ -n "${SNAP:-}" ]; then
    DATA_HOME="$HOME/.local/share"
fi
INSTALL_DIR="$DATA_HOME/salaty"
BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="$DATA_HOME/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
ICONS_ROOT="$DATA_HOME/icons/hicolor"
PYTHON_BIN="${PYTHON_BIN:-python3}"

info() { printf '\033[1;36m%s\033[0m\n' "$1"; }
ok()   { printf '\033[1;32m%s\033[0m\n' "$1"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$1"; }
fail() { printf '\033[1;31m%s\033[0m\n' "$1" >&2; exit 1; }

printf '══════════════════════════════════════\n'
printf '  تثبيت صلاتي – مواقيت الصلاة\n'
printf '══════════════════════════════════════\n\n'

command -v "$PYTHON_BIN" >/dev/null 2>&1 ||
    fail "Python 3 غير موجود. ثبّت python3 ثم أعد المحاولة."

"$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' ||
    fail "يتطلب صلاتي Python 3.9 أو أحدث."

for required in salaty.py run.sh requirements.txt; do
    [ -f "$SOURCE_DIR/$required" ] ||
        fail "ملف مطلوب غير موجود: $required"
done

info "نسخ ملفات التطبيق إلى $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rm -rf "$INSTALL_DIR/assets" "$INSTALL_DIR/fonts" "$INSTALL_DIR/sounds"
cp -R "$SOURCE_DIR/assets" "$SOURCE_DIR/fonts" "$SOURCE_DIR/sounds" "$INSTALL_DIR/"
install -m 755 "$SOURCE_DIR/salaty.py" "$SOURCE_DIR/run.sh" "$INSTALL_DIR/"
install -m 644 "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/"
[ -f "$SOURCE_DIR/LICENSE" ] && install -m 644 "$SOURCE_DIR/LICENSE" "$INSTALL_DIR/"
[ -f "$SOURCE_DIR/THIRD_PARTY_NOTICES.md" ] &&
    install -m 644 "$SOURCE_DIR/THIRD_PARTY_NOTICES.md" "$INSTALL_DIR/"

if "$PYTHON_BIN" -c 'import PyQt6' >/dev/null 2>&1; then
    info "استخدام PyQt6 المثبتة في النظام"
    rm -f "$INSTALL_DIR/.use-venv"
else
    info "إنشاء بيئة Python معزولة وتثبيت PyQt6"
    if [ ! -x "$INSTALL_DIR/.venv/bin/python" ]; then
        "$PYTHON_BIN" -m venv "$INSTALL_DIR/.venv" 2>/dev/null ||
            fail "تعذّر إنشاء البيئة. ثبّت python3-venv ثم أعد المحاولة."
    fi
    "$INSTALL_DIR/.venv/bin/python" -m pip install \
        --disable-pip-version-check -r "$INSTALL_DIR/requirements.txt"
    touch "$INSTALL_DIR/.use-venv"
fi

info "إضافة أمر التشغيل وقائمة التطبيقات والتشغيل التلقائي"
mkdir -p "$BIN_DIR" "$APPLICATIONS_DIR" "$AUTOSTART_DIR"
cat > "$BIN_DIR/salaty" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/run.sh" "\$@"
EOF
chmod 755 "$BIN_DIR/salaty"

for size in 32 48 64 128 256 512; do
    target="$ICONS_ROOT/${size}x${size}/apps"
    mkdir -p "$target"
    install -m 644 "$SOURCE_DIR/assets/icons/salaty-${size}.png" \
        "$target/salaty.png"
done

cat > "$APPLICATIONS_DIR/salaty.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=صلاتي
Name[en]=Salaty
Comment=مواقيت الصلاة والتنبيهات
Comment[en]=Prayer times and notifications
Exec=$BIN_DIR/salaty
Icon=salaty
Terminal=false
Categories=Utility;Clock;
Keywords=prayer;salat;adhan;islam;صلاة;مواقيت;أذان;
StartupNotify=true
StartupWMClass=Salaty
EOF

cat > "$AUTOSTART_DIR/salaty.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=صلاتي
Name[en]=Salaty
Comment=تشغيل صلاتي في الخلفية عند تسجيل الدخول
Comment[en]=Start Salaty in the background when signing in
Exec=$BIN_DIR/salaty --background
Icon=salaty
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
gtk-update-icon-cache -f -t "$ICONS_ROOT" >/dev/null 2>&1 || true

if ! command -v gst-play-1.0 >/dev/null 2>&1 &&
   ! command -v pw-play >/dev/null 2>&1 &&
   ! command -v canberra-gtk-play >/dev/null 2>&1 &&
   ! command -v aplay >/dev/null 2>&1; then
    warn "لم يُعثر على مشغّل صوت. سيعمل التطبيق، لكن أصوات الأذان تحتاج GStreamer أو PipeWire."
fi

printf '\n'
ok "اكتمل تثبيت صلاتي بنجاح."
printf 'ابحث عن «صلاتي» في قائمة البرامج، أو شغّله بالأمر: salaty\n'
printf 'سيبدأ صلاتي تلقائياً في الخلفية عند تسجيل الدخول القادم.\n'
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "أضف $BIN_DIR إلى PATH لتشغيل الأمر salaty من الطرفية."
fi
