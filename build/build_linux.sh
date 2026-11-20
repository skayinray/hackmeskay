#!/usr/bin/env bash
# Сборка Linux: PyInstaller -> AppDir -> AppImage
# Требуется appimagetool в PATH (или переменная APPIMAGETOOL).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="python3"
"$PY" -m pip install -q -r requirements.txt
"$PY" -m PyInstaller --noconfirm --clean --onefile --console \
  --name hackmeskay --paths src --add-data "data:data" \
  --hidden-import aiohttp entrypoint.py

APPDIR="$ROOT/build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/hackmeskay"

cp dist/hackmeskay "$APPDIR/usr/bin/hackmeskay"
chmod +x "$APPDIR/usr/bin/hackmeskay"
cp -r data "$APPDIR/usr/share/hackmeskay/data"

cp build/hackmeskay.desktop "$APPDIR/hackmeskay.desktop"
cp build/hackmeskay.png "$APPDIR/hackmeskay.png" 2>/dev/null || true
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
# Портативный режим: данные рядом с AppImage (создаются при первом запуске).
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$HERE/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/usr/bin/hackmeskay" "$@"
EOF
chmod +x "$APPDIR/AppRun"

TOOL="${APPIMAGETOOL:-$ROOT/tools/squashfs-root/AppRun}"
if [ ! -x "$TOOL" ]; then
    TOOL="$ROOT/tools/appimagetool.AppImage"
fi
if [ ! -x "$TOOL" ]; then
    TOOL="appimagetool"
fi
"$TOOL" "$APPDIR" "$ROOT/dist/hackmeskay-x86_64.AppImage"

# Рядом с AppImage кладём только шаблоны — реальные saves/mods/config
# создаются движком при запуске и не затираются апдейтером.
for d in mods saves config; do mkdir -p "dist/$d"; done
cp -rn mods/example_mod "dist/mods/" 2>/dev/null || true
cp -n mods/mods.json "dist/mods/mods.json" 2>/dev/null || true

echo "Готово: dist/hackmeskay-x86_64.AppImage"
