#!@bash@
# velbrum-actualizar: instala la versión nueva de Velbrum (ver README.md,
# «Updates»). La corre el botón «Instalar y reiniciar» de Velbrum con pkexec,
# que pide la contraseña de administrador:
#
#   velbrum-actualizar instalar    baja la versión nueva, verifica su firma,
#                                actualiza la carpeta de Velbrum y hace el rebuild
#   velbrum-actualizar verificar   solo baja y verifica la versión nueva, sin
#                                cambiar nada (no necesita ser root)
#
# Seguridad:
# - Solo se instala una etiqueta vAAAA.MM.DD firmada con una clave de
#   firmas/claves-permitidas, y se verifica con la copia de ese archivo que
#   está en el paquete instalado (el store de Nix, solo lectura), no con la
#   que trae la descarga. El programa que verifica se fija por línea de
#   comandos: la configuración del repositorio no lo puede cambiar.
# - Todo lo de git corre con el usuario dueño de la carpeta, no como root, y
#   sin ganchos: lo que haya en el repositorio (.git/config, hooks) no corre
#   con permisos de administrador. Como root solo corre el rebuild.
# - Si la carpeta tiene cambios locales o no se puede avanzar sin mezclar, no
#   se toca nada.
set -euo pipefail
export PATH=/run/current-system/sw/bin:/run/wrappers/bin
umask 022

# (Los valores vienen de default.nix ya entre comillas.)
carpeta=@carpeta@
repositorio=@repositorio@
comando_rebuild=@comando@
instalada="@version@"
claves="@clavesPermitidas@"
modo="${1:-}"
registro=/var/log/velbrum-actualizar.log

decir() {
  echo "velbrum-actualizar: $*" >&2
  if [ "$(id -u)" = 0 ]; then echo "$(date -u +%FT%TZ) $*" >> "$registro"; fi
}
fallar() {
  decir "ERROR: $*"
  exit 1
}

case "$modo" in
  instalar) [ "$(id -u)" = 0 ] || fallar "«instalar» tiene que correr como root (pkexec)." ;;
  verificar) ;;
  *) echo "Uso: velbrum-actualizar instalar|verificar" >&2; exit 2 ;;
esac
[ -d "$carpeta/.git" ] || fallar "$carpeta no es un repositorio git (ver «Updates» en README.md)."

dueno=$(stat -c %U "$carpeta")
# git con el dueño de la carpeta, sin ganchos y con la carpeta marcada como
# segura (si corre como otro usuario, git la rechazaría).
git_dueno() {
  local comando=(git -C "$carpeta" -c core.hooksPath=/dev/null -c safe.directory="$carpeta" "$@")
  if [ "$(id -u)" = 0 ] && [ "$dueno" != root ]; then
    runuser -u "$dueno" -- "${comando[@]}"
  elif [ "$(id -un)" = "$dueno" ]; then
    "${comando[@]}"
  else
    fallar "La carpeta $carpeta es de $dueno: corré esto como ese usuario o como root."
  fi
}

# AAAA.MM.DD[.N] → comparable («2026.10.21.2» > «2026.10.21»).
mas_nueva() {
  [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ]
}

decir "versión instalada: $instalada; buscando en https://github.com/$repositorio"
git_dueno fetch --quiet --no-tags "https://github.com/$repositorio.git" '+refs/tags/v*:refs/tags/v*' \
  || fallar "no se pudo bajar la lista de versiones (¿hay internet?)."
etiqueta=$(git_dueno tag --list 'v[0-9]*' --sort=-v:refname | grep -E '^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?$' | head -1 || true)
[ -n "$etiqueta" ] || fallar "no hay versiones publicadas."
nueva=${etiqueta#v}
if ! mas_nueva "$nueva" "$instalada"; then
  decir "Velbrum ya está al día ($instalada)."
  exit 0
fi

git_dueno -c gpg.format=ssh -c gpg.ssh.program="@sshKeygen@" -c gpg.ssh.allowedSignersFile="$claves" \
  verify-tag "$etiqueta" 2>/dev/null || fallar "la versión $nueva no tiene una firma válida de Velbrum: no se instala."
[ "$(git_dueno show "$etiqueta:VERSION" | tr -d '[:space:]')" = "$nueva" ] \
  || fallar "la versión $nueva no coincide con su archivo VERSION: no se instala."
decir "versión $nueva: firma verificada."

if [ "$modo" = verificar ]; then
  echo "$nueva"
  exit 0
fi

[ -z "$(git_dueno status --porcelain)" ] || fallar "$carpeta tiene cambios sin guardar: actualizala a mano."
destino=$(git_dueno rev-parse "$etiqueta^{commit}")
git_dueno merge --quiet --ff-only "$destino" \
  || fallar "$carpeta tiene commits propios que no están en la versión $nueva: actualizala a mano."
[ "$(git_dueno rev-parse HEAD)" = "$destino" ] && [ -z "$(git_dueno status --porcelain)" ] \
  || fallar "la carpeta no quedó exactamente en la versión $nueva."

decir "instalando la versión $nueva (rebuild del sistema)…"
read -r -a rebuild <<< "$comando_rebuild"
if "${rebuild[@]}" >> "$registro" 2>&1; then
  decir "Velbrum $nueva instalada."
else
  fallar "el rebuild falló (detalles en $registro). El sistema sigue con la versión anterior."
fi
