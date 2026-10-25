#!/usr/bin/env bash
# Paquetes de Velbrum para Linux a partir de la carpeta que arma
# portable/empaquetar.py: portable (.tar.gz), AppImage, .deb, .rpm y Arch.
#
# Uso: portable/linux/paquetes.sh CARPETA_VELBRUM RECURSOS SALIDA
# Necesita fpm (con rpm y bsdtar para .rpm y Arch) y appimagetool.
set -euo pipefail
aqui=$(cd "$(dirname "$0")" && pwd)
velbrum=$(cd "$1" && pwd) recursos=$(cd "$2" && pwd)
mkdir -p "$3"; salida=$(cd "$3" && pwd)
version=$(cat "$aqui/../../VERSION")
nombre="velbrum-$version-linux-x86_64"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Portable: los datos quedan en Velbrum/datos (el archivo «portable» lo indica).
cp -a "$velbrum" "$tmp/Velbrum"
touch "$tmp/Velbrum/portable"
cp "$aqui/LEEME-portable.txt" "$tmp/Velbrum/LEEME.txt"
tar -C "$tmp" -czf "$salida/$nombre-portable.tar.gz" Velbrum
rm -rf "$tmp/Velbrum"

# Lo que instalan los paquetes: /opt/velbrum, el comando, el menú y los íconos.
raiz=$tmp/raiz
mkdir -p "$raiz/opt" "$raiz/usr/bin" "$raiz/usr/share/applications"
cp -a "$velbrum" "$raiz/opt/velbrum"
ln -s /opt/velbrum/velbrum "$raiz/usr/bin/velbrum"
cp "$aqui/velbrum.desktop" "$aqui/velbrum-tor.desktop" "$raiz/usr/share/applications/"
for t in 16 24 32 48 64 96 128 256 512; do
  install -Dm644 "$recursos/hicolor/velbrum-$t.png" "$raiz/usr/share/icons/hicolor/${t}x${t}/apps/velbrum.png"
done
install -Dm644 "$recursos/hicolor/velbrum.svg" "$raiz/usr/share/icons/hicolor/scalable/apps/velbrum.svg"

comun=(-s dir -C "$raiz" -n velbrum -v "$version" --iteration 1 -a x86_64
  --license MPL-2.0 --url https://github.com/ebalia-real/velbrum --maintainer "Velbrum"
  --description "Navegador privado: LibreWolf con la privacidad de Mullvad Browser y extensiones de Chrome"
  --category web --after-install "$aqui/despues-de-instalar.sh" --after-remove "$aqui/despues-de-instalar.sh")
fpm "${comun[@]}" -t deb -p "$salida/$nombre.deb" -a amd64 \
  -d "libgtk-3-0t64 | libgtk-3-0" -d "libasound2t64 | libasound2" -d libx11-xcb1 -d libdbus-1-3 opt usr
fpm "${comun[@]}" -t rpm -p "$salida/$nombre.rpm" \
  -d gtk3 -d alsa-lib -d libX11-xcb -d dbus-libs opt usr
fpm "${comun[@]}" -t pacman -p "$salida/$nombre.pkg.tar.zst" \
  -d gtk3 -d alsa-lib -d libxcb -d dbus opt usr

# AppImage: un solo archivo, los datos en ~/.local/share/velbrum.
appdir=$tmp/Velbrum.AppDir
mkdir -p "$appdir/usr/lib"
cp -a "$velbrum" "$appdir/usr/lib/velbrum"
cp "$aqui/velbrum.desktop" "$appdir/velbrum.desktop"
cp "$recursos/hicolor/velbrum-256.png" "$appdir/velbrum.png"
cp "$aqui/AppRun" "$appdir/AppRun"
chmod 755 "$appdir/AppRun"
ARCH=x86_64 appimagetool --no-appstream ${APPIMAGE_RUNTIME:+--runtime-file "$APPIMAGE_RUNTIME"} "$appdir" "$salida/$nombre.AppImage"
ls -la "$salida"
