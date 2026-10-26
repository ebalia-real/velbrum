#!/usr/bin/env bash
# Firma las sumas (SHA256SUMS) de una versión que armó GitHub Actions, con la
# clave de Velbrum, y sube la firma (SHA256SUMS.sig) a esa versión. Sin la
# firma, el actualizador de los paquetes (marca/actualizador-velbrum.sys.mjs)
# no ofrece instalarla.
#
# Uso: portable/firmar-sumas.sh vAAAA.MM.DD[.N] [CLAVE]
# CLAVE: la clave privada de Velbrum (por omisión ~/.ssh/velbrum-firma).
# Necesita gh (con sesión iniciada), ssh-keygen, curl y python3.
#
# Antes de firmar revisa que cada línea sea de un paquete de esa versión y que
# las sumas coincidan con las que GitHub calculó al subir cada archivo.
set -euo pipefail
etiqueta=${1:?Uso: portable/firmar-sumas.sh vAAAA.MM.DD[.N] [CLAVE]}
clave=${2:-$HOME/.ssh/velbrum-firma}
aqui=$(cd "$(dirname "$0")/.." && pwd)
repo=ebalia-real/velbrum
version=${etiqueta#v}
[[ $etiqueta =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?$ ]] || { echo "etiqueta inválida: $etiqueta" >&2; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

gh release download "$etiqueta" --repo "$repo" -p SHA256SUMS -D "$tmp"
gh api "repos/$repo/releases/tags/$etiqueta" > "$tmp/version.json"
python3 -I - "$tmp/SHA256SUMS" "$tmp/version.json" "$version" <<'PY'
import json, re, sys
sumas, datos, version = open(sys.argv[1]).read().splitlines(), json.load(open(sys.argv[2])), sys.argv[3]
digest = {a["name"]: (a.get("digest") or "").removeprefix("sha256:") for a in datos["assets"]}
for linea in sumas:
    suma, nombre = re.fullmatch(r"([0-9a-f]{64})  (\S+)", linea).groups()
    if not nombre.startswith(f"velbrum-{version}-"):
        sys.exit(f"{nombre}: no es un paquete de la versión {version}")
    if nombre not in digest:
        sys.exit(f"{nombre}: no está en la versión publicada")
    if digest[nombre] and digest[nombre] != suma:
        sys.exit(f"{nombre}: la suma no coincide con la de GitHub")
    print(f"  {nombre}{'' if digest[nombre] else ' (GitHub no dio su suma)'}")
PY
echo "Firmando SHA256SUMS de Velbrum $version…"
ssh-keygen -q -Y sign -n velbrum-paquetes -f "$clave" "$tmp/SHA256SUMS"
ssh-keygen -Y verify -f "$aqui/firmas/claves-permitidas" -I velbrum-versiones -n velbrum-paquetes \
  -s "$tmp/SHA256SUMS.sig" < "$tmp/SHA256SUMS"
gh release upload "$etiqueta" --repo "$repo" --clobber "$tmp/SHA256SUMS.sig"
echo "Listo: SHA256SUMS.sig subida a $etiqueta."
