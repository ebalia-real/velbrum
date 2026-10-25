#!/usr/bin/env bash
# Baja lo que usan los paquetes de portable/ y verifica sus firmas GPG:
# LibreWolf (firmado por LibreWolf Maintainers), el Tor Expert Bundle y, en
# Linux, Mullvad Browser por sus fuentes (los dos firmados por Tor Browser
# Developers). Las claves se piden por su huella completa.
#
# Uso: portable/bajar.sh linux|windows|macos x86_64|arm64 DESTINO
# Deja DESTINO/navegador.txt con la carpeta de LibreWolf (o LibreWolf.app),
# DESTINO/tor y, en Linux, DESTINO/mullvad.txt.
set -euo pipefail
sistema=$1 arq=$2
mkdir -p "$3"; destino=$(cd "$3" && pwd)
aqui=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=versiones.env
. "$aqui/versiones.env"

GNUPGHOME=$(mktemp -d); export GNUPGHOME
clave() { curl -sfL --retry 3 "https://keys.openpgp.org/vks/v1/by-fingerprint/$1" | gpg --batch --quiet --import; }
LIBREWOLF_CLAVE=662E3CDD6FE329002D0CA5BB40339DD82B12EF16  # LibreWolf Maintainers <gpg@librewolf.net>
TOR_CLAVE=EF6E286DDA85EA2A4BA7DE684E2C6E8793298290        # Tor Browser Developers (signing key)
clave $LIBREWOLF_CLAVE
clave $TOR_CLAVE
bajar() { curl -sfL --retry 3 -o "$2" "$1"; }
# verificar FIRMA ARCHIVO HUELLA: firma válida de esa clave (VALIDSIG termina con
# la huella de la clave principal).
verificar() {
  gpg --batch --status-fd 1 --verify "$1" "$2" 2>/dev/null | grep -q "^\[GNUPG:\] VALIDSIG .* $3\$" \
    || { echo "bajar.sh: FIRMA INVÁLIDA: $2" >&2; exit 1; }
  echo "firma correcta: $2"
}
# En Windows (Git Bash), las rutas que se escriben son para Python: C:/…
ruta() { if command -v cygpath >/dev/null; then cygpath -m "$1"; else echo "$1"; fi; }
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }

case "$sistema-$arq" in
  linux-x86_64) lw=librewolf-$LIBREWOLF-linux-x86_64-package.tar.xz; tor=tor-expert-bundle-linux-x86_64-$TOR.tar.gz ;;
  windows-x86_64) lw=librewolf-$LIBREWOLF-windows-x86_64-package.zip; tor=tor-expert-bundle-windows-x86_64-$TOR.tar.gz ;;
  macos-arm64) lw=librewolf-$LIBREWOLF-macos-arm64-package.dmg; tor=tor-expert-bundle-macos-aarch64-$TOR.tar.gz ;;
  macos-x86_64) lw=librewolf-$LIBREWOLF-macos-x86_64-package.dmg; tor=tor-expert-bundle-macos-x86_64-$TOR.tar.gz ;;
  *) echo "bajar.sh: sistema o arquitectura desconocidos: $sistema $arq" >&2; exit 2 ;;
esac
cd "$destino"

# LibreWolf
bajar "https://dl.librewolf.net/librewolf/$LIBREWOLF/$lw" "$lw"
bajar "https://dl.librewolf.net/librewolf/$LIBREWOLF/$lw.sig" "$lw.sig"
verificar "$lw.sig" "$lw" $LIBREWOLF_CLAVE
rm -rf navegador; mkdir navegador
case $sistema in
  linux) tar -xf "$lw" -C navegador ;;
  windows) python -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$lw" navegador ;;
  macos)
    hdiutil attach -nobrowse -readonly -mountpoint "$destino/dmg" "$lw" >/dev/null
    cp -R "$destino"/dmg/*.app navegador/
    hdiutil detach "$destino/dmg" >/dev/null ;;
esac
if [ "$sistema" = macos ]; then
  ruta "$(find "$destino/navegador" -maxdepth 1 -name "*.app" | head -1)" > navegador.txt
else
  ruta "$(dirname "$(find "$destino/navegador" -maxdepth 3 -name librewolf.cfg | head -1)")" > navegador.txt
fi
echo "LibreWolf: $(cat navegador.txt)"

# Tor Expert Bundle: la lista de sumas está firmada.
bajar "https://dist.torproject.org/torbrowser/$TOR/$tor" "$tor"
bajar "https://dist.torproject.org/torbrowser/$TOR/sha256sums-signed-build.txt" tor-sumas.txt
bajar "https://dist.torproject.org/torbrowser/$TOR/sha256sums-signed-build.txt.asc" tor-sumas.txt.asc
verificar tor-sumas.txt.asc tor-sumas.txt $TOR_CLAVE
grep -q "^$(sha256 "$tor")  $tor\$" tor-sumas.txt || { echo "bajar.sh: la suma de $tor no coincide" >&2; exit 1; }
echo "suma correcta: $tor"
rm -rf tor; mkdir tor; tar -xzf "$tor" -C tor

# Linux: las fuentes de Mullvad Browser.
if [ "$sistema" = linux ]; then
  mv=mullvad-browser-linux-x86_64-$MULLVAD.tar.xz
  bajar "https://cdn.mullvad.net/browser/$MULLVAD/$mv" "$mv"
  bajar "https://cdn.mullvad.net/browser/$MULLVAD/$mv.asc" "$mv.asc"
  verificar "$mv.asc" "$mv" $TOR_CLAVE
  rm -rf mullvad; mkdir mullvad; tar -xf "$mv" -C mullvad
  dirname "$(dirname "$(find "$destino/mullvad" -path "*/fonts/fonts.conf" | head -1)")" > mullvad.txt
  echo "Mullvad Browser: $(cat mullvad.txt)"
fi
