#!/bin/sh
# Instala una versión de Velbrum que el navegador ya bajó y verificó
# (marca/actualizador-velbrum.sys.mjs): lo corre Velbrum al cerrarse, desde
# <datos>/actualizacion. Para Linux (portable y AppImage) y macOS.
#
# Uso: aplicar.sh MODO PID NUEVA DESTINO RELANZAR
#   MODO carpeta  DESTINO es la carpeta del Velbrum portable: se reemplaza todo
#                 menos «datos» y «portable»;
#        app      DESTINO es Velbrum.app (macOS);
#        archivo  DESTINO es el AppImage.
#   PID       el proceso de Velbrum: se espera a que termine.
#   NUEVA     la versión nueva (carpeta, app o archivo).
#   RELANZAR  1 para volver a abrir Velbrum al terminar.
#
# Si algo falla, se vuelve a dejar la versión anterior. Cómo terminó queda en
# «resultado» («ok» o «error: …»), que lee Velbrum al abrir; los detalles, en
# registro.txt.
set -u
modo=$1 pid=$2 nueva=$3 destino=$4 relanzar=$5
aqui=$(cd "$(dirname "$0")" && pwd)
vieja=$aqui/vieja
exec >>"$aqui/registro.txt" 2>&1 </dev/null
echo "$(date -u +%FT%TZ) $modo: $nueva → $destino"

terminar() {
  echo "$1" > "$aqui/resultado"
  echo "$(date -u +%FT%TZ) $1"
  if [ "$relanzar" = 1 ]; then
    case $modo in
      carpeta) nohup "$destino/velbrum" >/dev/null 2>&1 & ;;
      archivo) nohup "$destino" >/dev/null 2>&1 & ;;
      app) nohup "$destino/Contents/MacOS/velbrum" >/dev/null 2>&1 & ;;
    esac
  fi
  exit 0
}

# Hasta 10 minutos para que Velbrum se cierre.
n=0
while kill -0 "$pid" 2>/dev/null; do
  n=$((n + 1))
  [ $n -lt 1200 ] || terminar "error: Velbrum no se cerró"
  sleep 0.5
done

case $modo in
  carpeta)
    rm -rf "$vieja" && mkdir "$vieja" || terminar "error: no pude preparar $vieja"
    volver() {
      # Lo nuevo que ya se movió vuelve a su lugar y lo viejo, a la carpeta.
      for x in "$destino"/*; do
        n=${x##*/}
        case $n in datos|portable) continue ;; esac
        [ -e "$x" ] && mv "$x" "$nueva/"
      done
      for x in "$vieja"/*; do
        [ -e "$x" ] && mv "$x" "$destino/"
      done
    }
    for x in "$destino"/*; do
      n=${x##*/}
      case $n in datos|portable) continue ;; esac
      mv "$x" "$vieja/" || { volver; terminar "error: no pude mover $x"; }
    done
    for x in "$nueva"/*; do
      n=${x##*/}
      case $n in datos|portable) continue ;; esac
      mv "$x" "$destino/" || { volver; terminar "error: no pude instalar $n"; }
    done
    ;;
  app)
    rm -rf "$vieja.app"
    mv "$destino" "$vieja.app" || terminar "error: no pude mover $destino"
    if ! mv "$nueva" "$destino"; then
      rm -rf "$destino"
      mv "$vieja.app" "$destino"
      terminar "error: no pude instalar la versión nueva en $destino"
    fi
    ;;
  archivo)
    # Se copia al lado y se renombra: el reemplazo es de una sola vez.
    if ! { cp "$nueva" "$destino.nuevo" && chmod 755 "$destino.nuevo" && mv -f "$destino.nuevo" "$destino"; }; then
      rm -f "$destino.nuevo"
      terminar "error: no pude reemplazar $destino"
    fi
    ;;
  *) terminar "error: modo desconocido: $modo" ;;
esac

rm -rf "$vieja" "$vieja.app" "$aqui/nueva" "$nueva"
terminar ok
