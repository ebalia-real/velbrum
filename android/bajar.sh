#!/usr/bin/env bash
# Baja los APK oficiales de IronFox que usa Velbrum para Android y verifica
# que estén firmados con el certificado de IronFox (versiones.env). IronFox no
# publica firmas GPG: la firma del APK (esquema v2/v3, cubre todo el archivo)
# con un certificado fijado acá cumple ese papel. La suma sha512 que publica
# se comprueba también.
#
# Uso: android/bajar.sh DESTINO [ABI...]   (por defecto arm64-v8a armeabi-v7a x86_64)
# Necesita apksigner (build-tools de Android) en el PATH.
set -euo pipefail
mkdir -p "$1"; destino=$(cd "$1" && pwd); shift
abis=("$@"); [ ${#abis[@]} -gt 0 ] || abis=(arm64-v8a armeabi-v7a x86_64)
aqui=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=versiones.env
. "$aqui/versiones.env"

base="https://releases.ironfoxoss.org/ironfox/releases/$IRONFOX"
for abi in "${abis[@]}"; do
  case $abi in arm64-v8a|armeabi-v7a|x86_64) ;; *) echo "bajar.sh: ABI desconocida: $abi" >&2; exit 2 ;; esac
  apk=ironfox-$IRONFOX-$abi.apk
  curl -sfL --retry 3 -o "$destino/$apk" "$base/$abi/$apk"
  curl -sfL --retry 3 -o "$destino/$apk.sha512" "$base/$abi/$apk-sha512sum.txt"
  suma=$(sha512sum "$destino/$apk" | cut -d' ' -f1)
  grep -q "^$suma" "$destino/$apk.sha512" || { echo "bajar.sh: la suma de $apk no coincide" >&2; exit 1; }
  # Exactamente un firmante, y que sea IronFox.
  certificados=$(apksigner verify --print-certs "$destino/$apk" | sed -n 's/^Signer #[0-9]* certificate SHA-256 digest: //p')
  if [ "$certificados" != "$IRONFOX_CERTIFICADO" ]; then
    echo "bajar.sh: FIRMA INVÁLIDA: $apk no está firmado por IronFox ($certificados)" >&2
    exit 1
  fi
  echo "firma correcta: $apk"
done
