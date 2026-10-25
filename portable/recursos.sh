#!/usr/bin/env bash
# Gráficos de la marca para los paquetes de portable/ (lo mismo que arma
# default.nix en NixOS): íconos de las pestañas y las ventanas, «Acerca de»,
# íconos del menú, velbrum.ico (Windows) y velbrum.icns (macOS).
#
# Uso: portable/recursos.sh CARPETA_SALIDA
# Necesita rsvg-convert, ImageMagick (magick o convert) y png2icns (libicns).
set -euo pipefail
aqui=$(cd "$(dirname "$0")/.." && pwd)
salida=$1
logo=$aqui/iconos/velbrum.svg
chico=$aqui/iconos/velbrum-chico.svg
magick=$(command -v magick || command -v convert)
mkdir -p "$salida/branding" "$salida/ventana" "$salida/hicolor"

svg_para() { if [ "$1" -le 32 ]; then echo "$chico"; else echo "$logo"; fi; }

# Pestañas y ventanas (chrome/browser/content/branding y chrome/icons/default).
for t in 16 32 48 64 128; do
  rsvg-convert -w $t -h $t "$(svg_para $t)" -o "$salida/branding/icon$t.png"
  cp "$salida/branding/icon$t.png" "$salida/ventana/default$t.png"
done
for nombre in about-logo about-logo-private; do
  rsvg-convert -w 192 -h 192 "$logo" -o "$salida/branding/$nombre.png"
  rsvg-convert -w 384 -h 384 "$logo" -o "$salida/branding/$nombre@2x.png"
done
cp "$logo" "$salida/branding/about-logo.svg"
rsvg-convert -w 200 -h 200 "$logo" -o "$salida/logo200.png"
"$magick" -size 300x236 xc:none "$salida/logo200.png" -gravity center -composite "$salida/branding/about.png"
rm "$salida/logo200.png"

# Menú de aplicaciones (Linux) y extensión de Velbrum.
for t in 16 24 32 48 64 96 128 256 512; do
  rsvg-convert -w $t -h $t "$(svg_para $t)" -o "$salida/hicolor/velbrum-$t.png"
done
cp "$logo" "$salida/hicolor/velbrum.svg"

# Windows: un .ico con varios tamaños. macOS: un .icns.
"$magick" "$salida/hicolor/velbrum-16.png" "$salida/hicolor/velbrum-24.png" "$salida/hicolor/velbrum-32.png" \
  "$salida/hicolor/velbrum-48.png" "$salida/hicolor/velbrum-64.png" "$salida/hicolor/velbrum-128.png" \
  "$salida/hicolor/velbrum-256.png" "$salida/velbrum.ico"
png2icns "$salida/velbrum.icns" "$salida/hicolor/velbrum-16.png" "$salida/hicolor/velbrum-32.png" \
  "$salida/hicolor/velbrum-48.png" "$salida/hicolor/velbrum-128.png" "$salida/hicolor/velbrum-256.png" \
  "$salida/hicolor/velbrum-512.png" > /dev/null
echo "recursos listos en $salida"
