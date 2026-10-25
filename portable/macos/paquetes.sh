#!/usr/bin/env bash
# Paquetes de Velbrum para macOS a partir de Velbrum.app (portable/empaquetar.py):
# un .dmg para instalar (arrastrar a Aplicaciones) y un .zip portable.
#
# Uso: portable/macos/paquetes.sh Velbrum.app ARQUITECTURA SALIDA
# ARQUITECTURA: arm64 (Apple Silicon) o x86_64 (Intel).
#
# Sin una cuenta de desarrollador de Apple no se puede firmar ni notarizar:
# la app lleva una firma «ad hoc» (en Apple Silicon no corre nada sin firma) y
# la primera vez hay que abrirla con clic derecho → Abrir (ver LEEME).
set -euo pipefail
aqui=$(cd "$(dirname "$0")" && pwd)
app=$(cd "$1" && pwd) arq=$2
mkdir -p "$3"; salida=$(cd "$3" && pwd)
version=$(cat "$aqui/../../VERSION")
nombre="velbrum-$version-macos-$arq"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

xattr -cr "$app"
codesign --force --deep --sign - "$app"
codesign --verify --deep "$app"

# Instalador: el .dmg con Velbrum.app y un acceso a Aplicaciones.
mkdir "$tmp/dmg"
cp -R "$app" "$tmp/dmg/Velbrum.app"
ln -s /Applications "$tmp/dmg/Aplicaciones"
cp "$aqui/LEEME.txt" "$tmp/dmg/LEEME.txt"
hdiutil create -volname "Velbrum $version" -srcfolder "$tmp/dmg" -ov -format UDZO "$salida/$nombre.dmg"

# Portable: los datos quedan en la carpeta «datos», al lado de la app.
mkdir "$tmp/Velbrum Portable"
cp -R "$app" "$tmp/Velbrum Portable/Velbrum.app"
touch "$tmp/Velbrum Portable/portable"
cp "$aqui/LEEME.txt" "$tmp/Velbrum Portable/LEEME.txt"
(cd "$tmp" && ditto -c -k --sequesterRsrc --keepParent "Velbrum Portable" "$salida/$nombre-portable.zip")
ls -la "$salida"
