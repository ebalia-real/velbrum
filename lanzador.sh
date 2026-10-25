#!@bash@
# velbrum: abre el navegador Velbrum (ver README.md): LibreWolf con
# los ajustes de privacidad de Mullvad Browser, que además instala extensiones
# de Chrome adaptándolas solo. El perfil está en ~/.local/share/velbrum/gecko.
set -euo pipefail

# Si lo abre Velbrum mismo (botón «Nueva ventana privada con Tor»), que no herede
# lo que Gecko deja en el entorno para sus propios reinicios.
unset XRE_PROFILE_PATH XRE_PROFILE_LOCAL_PATH XRE_PROFILE_NAME XRE_RESTARTED_BY_PROFILE_MANAGER MOZ_LAUNCHED_CHILD
# El botón «Velbrum» lo usa para abrir la ventana con Tor.
export VELBRUM_LANZADOR="@lanzador@"
# El actualizador (ver README.md, «Updates»): la versión de Velbrum, de dónde
# salen las versiones nuevas (vacío: no se buscan) y el ayudante que las instala.
export VELBRUM_VERSION="@versionVelbrum@" VELBRUM_REPO_ACTUALIZACIONES=@repoActualizaciones@ VELBRUM_ACTUALIZADOR="@actualizador@"

ayuda() {
  cat <<'FIN'
Uso: velbrum [opciones] [URL o archivo.crx...]

  --privada                 ventana privada
  --tor                     ventana privada con Tor: otra ventana de Velbrum, con
                            su propio perfil (no guarda nada) y su propio Tor,
                            que corre solo mientras esa ventana está abierta
  --tor-pais PAIS           país por el que sale la ventana con Tor: auto (el
                            más anónimo) o de, nl, us, se, at, fr, no, ch, ro,
                            fi, is, dk, lu. También desde el botón «Velbrum»
  --nueva-ventana           abrir en una ventana nueva
  --extension-chrome X      instala una extensión de Chrome: su ID de 32 letras,
                            la URL de la Chrome Web Store o de la tienda de Edge,
                            o un archivo .crx
  --actualizar-extensiones  busca versiones nuevas de las extensiones de Chrome
                            instaladas, cada una en su tienda (se activan al
                            volver a abrir Velbrum)
  --exigir-firmas           aceptar solo extensiones firmadas por Mozilla (las
                            de Chrome quedan desactivadas)
  --permitir-sin-firma      volver a aceptar extensiones de Chrome (sin firma,
                            siempre con el cartel de confirmación)
  --estado-firmas           muestra cuál de los dos está activo
  --sin-bordes              las páginas usan toda la ventana, sin los bordes de
                            privacidad (los sitios ven el tamaño exacto de la
                            ventana)
  --con-bordes              vuelven los bordes de privacidad (como Mullvad
                            Browser: tamaño de ventana redondeado)
  --estado-bordes           muestra si los bordes están puestos
  --reiniciar               espera a que se cierre Velbrum y lo vuelve a abrir
                            (la versión instalada); lo usa el botón «Reiniciar»
  --ayuda                   esta ayuda

Los archivos .crx que se abran con Velbrum se instalan como extensiones.
Cualquier otra opción se le pasa tal cual al navegador.
FIN
}

datos="${XDG_DATA_HOME:-$HOME/.local/share}/velbrum"
perfil="$datos/gecko"

# Velbrum antes se llamaba Bruma: si están los datos con el nombre viejo (y
# todavía no los nuevos), se mudan una vez, con todo (perfil, extensiones,
# ventana con Tor, ajustes). No se toca nada si esa versión sigue abierta.
viejo="${XDG_DATA_HOME:-$HOME/.local/share}/bruma"
if [ -d "$viejo" ] && [ ! -e "$datos" ]; then
  abierto_viejo=0
  if destino=$(readlink "$viejo/gecko/lock" 2>/dev/null) && [ -e "/proc/${destino##*+}" ] \
    && tr '\0' ' ' 2>/dev/null < "/proc/${destino##*+}/cmdline" | grep -qF -- "--profile $viejo/gecko"; then
    abierto_viejo=1
  fi
  if ((abierto_viejo)); then
    echo "velbrum: cerrá Bruma (la versión anterior) para mudar tus datos a Velbrum." >&2
    exit 1
  fi
  mv "$viejo" "$datos"
  rm -f "$HOME/.librewolf/native-messaging-hosts/bruma.extensiones.json"
fi
# Interruptor de firmas: si existe este archivo, Velbrum solo acepta extensiones
# firmadas por Mozilla. Con la opción del sistema velbrum.extensionesDeChrome =
# false, las firmas son obligatorias siempre.
marca_firmas="$datos/firmas-obligatorias"
# Bordes de privacidad (letterboxing, ver gecko/ajustes.cfg): si existe este
# archivo, Velbrum los saca.
marca_bordes="$datos/sin-bordes"
# «Siempre privado» (casilla del botón «Velbrum»): LibreWolf lo apaga en cada
# arranque, así que se le avisa a gecko/ajustes.cfg con una variable.
if [ -e "$datos/siempre-privado" ]; then export VELBRUM_SIEMPRE_PRIVADO=1; else unset VELBRUM_SIEMPRE_PRIVADO; fi

firmas_obligatorias() {
  [ "@extensionesDeChrome@" != 1 ] || [ -e "$marca_firmas" ]
}

avisar() {
  echo "velbrum: $1" >&2
  "@notifySend@" --app-name=Velbrum --icon=velbrum "Velbrum" "$1" 2>/dev/null || true
}

# ── Ventana con Tor: lo que se usa también al cambiar de país ───────────
# Países con suficientes nodos de salida de Tor (muchos países no tienen).
paises_tor="de nl us se at fr no ch ro fi is dk lu"
red_tor="$datos/tor-red"
sockets_tor="${XDG_RUNTIME_DIR:-$red_tor}/velbrum-tor"

tor_corriendo() {
  local pid
  pid=$(cat "$red_tor/tor.pid" 2>/dev/null) || return 1
  [[ $pid =~ ^[0-9]+$ ]] && [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$(readlink -f "@tor@")" ]
}

# Guarda el país (para los próximos arranques) y, si Tor está corriendo, se lo
# cambia ya y pide circuitos nuevos.
cambiar_pais() {
  local pais="${1:-}"
  pais=${pais,,}
  if [ "$pais" != auto ] && [[ " $paises_tor " != *" $pais "* || -z $pais ]]; then
    echo "velbrum: país no disponible: «$pais» (opciones: auto $paises_tor)" >&2
    return 1
  fi
  mkdir -p -m 700 "$datos"
  if [ "$pais" = auto ]; then rm -f "$datos/tor-pais"; else echo "$pais" > "$datos/tor-pais"; fi
  if tor_corriendo; then
    "@python@" -I "@libexec@/tor-pais.py" "$sockets_tor/control" "$red_tor/datos/control_auth_cookie" "$pais"
  fi
}

# ¿Hay una instancia de Velbrum abierta con este perfil? (Gecko deja en «lock»
# la IP y el PID de la instancia; se confirma que ese PID sea Velbrum con ese
# perfil.)
perfil_abierto() {
  local destino pid linea
  destino=$(readlink "$1/lock" 2>/dev/null) || return 1
  pid=${destino##*+}
  [[ $pid =~ ^[0-9]+$ ]] || return 1
  linea=$(tr '\0' ' ' 2>/dev/null < "/proc/$pid/cmdline") || return 1
  [[ $linea == *"--profile $1 "* ]]
}

convertir() {
  if firmas_obligatorias; then
    avisar "Velbrum está aceptando solo extensiones firmadas por Mozilla. Para instalar extensiones de Chrome: velbrum --permitir-sin-firma"
    return 1
  fi
  "@python@" -I "@libexec@/extensiones_chrome.py" instalar "$1"
}

exigir_firmas() {
  if [ "@extensionesDeChrome@" != 1 ]; then
    avisar "Las firmas ya son obligatorias (lo fija la configuración del sistema)."
    return 0
  fi
  mkdir -p -m 700 "$datos"
  touch "$marca_firmas"
  avisar "Desde la próxima vez que abras Velbrum, solo acepta extensiones firmadas por Mozilla; las de Chrome quedan desactivadas. Para volver: velbrum --permitir-sin-firma"
}

permitir_sin_firma() {
  if [ "@extensionesDeChrome@" != 1 ]; then
    avisar "La configuración del sistema exige firmas (velbrum.extensionesDeChrome = false en la configuración de NixOS)."
    return 1
  fi
  rm -f "$marca_firmas"
  avisar "Desde la próxima vez que abras Velbrum, vuelve a aceptar extensiones de Chrome (sin firma de Mozilla, siempre con el cartel de confirmación)."
}

quitar_bordes() {
  mkdir -p -m 700 "$datos"
  touch "$marca_bordes"
  avisar "Desde la próxima vez que abras Velbrum, las páginas usan toda la ventana, sin bordes. Los sitios ven el tamaño exacto de tu ventana, así que es más fácil distinguirte. Para volver: velbrum --con-bordes"
}

poner_bordes() {
  rm -f "$marca_bordes"
  avisar "Desde la próxima vez que abras Velbrum, vuelven los bordes de privacidad: los sitios ven un tamaño de ventana redondeado, como en Mullvad Browser."
}

privada=0
nueva=0
tor=0
reiniciar=0
extra=()
urls=()
while (($#)); do
  case "$1" in
    --privada) privada=1; shift ;;
    --tor) tor=1; shift ;;
    --reiniciar) reiniciar=1; shift ;;
    --tor-pais) cambiar_pais "${2:-}"; exit ;;
    --nueva-ventana) nueva=1; shift ;;
    --ayuda | -h | --help) ayuda; exit 0 ;;
    --extension-chrome) urls+=("$(convertir "${2:-}")") || exit 1; shift $(($# > 1 ? 2 : 1)) ;;
    --actualizar-extensiones)
      firmas_obligatorias && exit 0
      exec "@python@" -I "@libexec@/extensiones_chrome.py" actualizar ;;
    --exigir-firmas) exigir_firmas; exit ;;
    --permitir-sin-firma) permitir_sin_firma; exit ;;
    --estado-firmas)
      if firmas_obligatorias; then echo "Solo extensiones firmadas por Mozilla."
      else echo "Se aceptan extensiones de Chrome (sin firma, con el cartel de confirmación)."; fi
      exit 0 ;;
    --sin-bordes) quitar_bordes; exit ;;
    --con-bordes) poner_bordes; exit ;;
    --estado-bordes)
      if [ -e "$marca_bordes" ]; then echo "Sin bordes: las páginas usan toda la ventana."
      else echo "Con bordes de privacidad (tamaño de ventana redondeado)."; fi
      exit 0 ;;
    --) shift; urls+=("$@"); break ;;
    -*) extra+=("$1"); shift ;;
    *) urls+=("$1"); shift ;;
  esac
done

# Archivos .crx abiertos con Velbrum (por ejemplo desde el explorador de
# archivos): se adaptan y se abre su instalación.
for i in "${!urls[@]}"; do
  case "${urls[$i]}" in
    *.crx | *.CRX)
      if xpi=$(convertir "${urls[$i]}"); then urls[i]=$xpi; else unset 'urls[i]'; fi
      ;;
  esac
done
urls=("${urls[@]}")

# Como Firefox: el perfil (historial, cookies, contraseñas) solo lo puede leer
# tu usuario.
mkdir -p -m 700 "$datos" "$perfil"
chmod 700 "$datos" "$perfil"

# Los interruptores (firmas y bordes) se le pasan a Gecko como preferencias en
# user.js: líneas marcadas que Velbrum reescribe en cada arranque (el resto de
# user.js no se toca). Van siempre, con true o false, porque Gecko guarda en
# prefs.js el último valor y sacar la línea no alcanzaría para volver atrás.
userjs="$perfil/user.js"
[ -f "$userjs" ] && sed -i -e '/\/\/ velbrum: interruptor de firmas$/d' -e '/\/\/ velbrum: bordes$/d' "$userjs"
if firmas_obligatorias; then exigir=true; else exigir=false; fi
if [ -e "$marca_bordes" ]; then bordes=false; else bordes=true; fi
(
  umask 077
  echo "user_pref(\"xpinstall.signatures.required\", $exigir); // velbrum: interruptor de firmas" >> "$userjs"
  echo "user_pref(\"privacy.resistFingerprinting.letterboxing\", $bordes); // velbrum: bordes" >> "$userjs"
)
# LibreWolf busca los hosts de mensajería nativa en ~/.librewolf.
mkdir -p "$HOME/.librewolf/native-messaging-hosts"
ln -sfn "@manifiestoHost@" "$HOME/.librewolf/native-messaging-hosts/velbrum.extensiones.json"

# El paquete de idioma ya no va en el perfil (lo instala una política desde
# /var/lib/velbrum/idioma): se borra el sello que dejaban versiones anteriores.
rm -f "$perfil/velbrum-idioma.json"

# uBlock Origin: en los perfiles creados antes del 19/10/2026 guardó el índice
# de listas de LibreWolf y lo volvía a pedir a librewolf.dev cada 13 días. Si
# lo encuentra, borra los datos de uBlock Origin (lo mismo que su botón
# «Restablecer ajustes predeterminados…»): vuelve a arrancar con sus listas
# por defecto, de su propia fuente. Se revisa una sola vez por perfil y nunca
# con Velbrum abierto.
velbrum_abierto() {
  perfil_abierto "$perfil"
}
# --reiniciar (botón «Reiniciar» de Velbrum, por ejemplo después de una
# actualización): espera a que se cierre la instancia que lo pidió (hasta un
# minuto) y sigue como un arranque normal, con la versión instalada.
if ((reiniciar)); then
  for _ in $(seq 240); do
    velbrum_abierto || break
    sleep 0.25
  done
fi

revisado_ubo="$datos/ubo-sin-librewolf"
if [ ! -e "$revisado_ubo" ] && ! velbrum_abierto; then
  uuid=$(grep -o 'uBlock0@raymondhill.net\\":\\"[0-9a-f-]*' "$perfil/prefs.js" 2>/dev/null | grep -o '[0-9a-f-]*$' || true)
  if [[ $uuid =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    ubo=("$perfil/storage/default/moz-extension+++$uuid" "$perfil/storage/default/moz-extension+++$uuid^userContextId=4294967295")
    if grep -rqa "librewolf.dev" "${ubo[@]}" 2>/dev/null; then
      rm -rf -- "${ubo[@]}"
      echo "velbrum: uBlock Origin vuelve a sus ajustes predeterminados (ya no usa librewolf.dev)" >&2
    fi
  fi
  touch "$revisado_ubo"
fi

# Solo las fuentes de Mullvad Browser (ver gecko/ajustes.cfg).
export FONTCONFIG_FILE="@fuentes@"

# Ventana privada con Tor: otra instancia de Velbrum, con su propio perfil
# (~/.local/share/velbrum/tor, siempre privado) y su propio Tor (datos en
# ~/.local/share/velbrum/tor-red), que escucha en un socket en
# $XDG_RUNTIME_DIR/velbrum-tor (carpeta corta y privada de tu usuario: los
# sockets no admiten rutas largas) y corre solo mientras esa instancia está
# abierta. Lo que no se puede cambiar adentro está en gecko/ajustes.cfg
# (VELBRUM_TOR).
abrir_con_tor() {
  local red="$red_tor" perfil_tor="$datos/tor" sockets="$sockets_tor" socket pid_tor="" estado pais
  local pais_args=()
  mkdir -p -m 700 "$red" "$perfil_tor" "$sockets"
  chmod 700 "$red" "$perfil_tor" "$sockets"
  socket="$sockets/socks"
  if ((${#socket} > 100)); then
    avisar "No se puede abrir la ventana con Tor: la ruta del socket es muy larga ($socket)."
    exit 1
  fi
  if ! tor_corriendo; then
    rm -f "$socket" "$sockets/control" "$red/tor.log"
    pais=$(cat "$datos/tor-pais" 2>/dev/null || true)
    if [ -n "$pais" ] && [[ " $paises_tor " == *" $pais "* ]]; then
      pais_args=(--ExitNodes "{$pais}" --StrictNodes 1)
    fi
    # Puerto de control solo para cambiar de país (tor-pais.py): socket
    # privado y cookie que solo tu usuario puede leer.
    "@tor@" --ignore-missing-torrc -f /dev/null --defaults-torrc /dev/null \
      --SocksPort "unix:$socket IsolateSOCKSAuth" \
      --ControlPort "unix:$sockets/control" --CookieAuthentication 1 "${pais_args[@]}" \
      --GeoIPFile "@torGeoip@/share/tor/geoip" --GeoIPv6File "@torGeoip@/share/tor/geoip6" \
      --DataDirectory "$red/datos" --ClientOnly 1 --AvoidDiskWrites 1 \
      --Log "notice file $red/tor.log" --PidFile "$red/tor.pid" > /dev/null 2>&1 &
    pid_tor=$!
    avisar "Conectando a Tor… (la primera vez puede tardar un minuto)"
  fi
  # Se espera a que Tor termine de conectarse (también si lo arrancó otro
  # clic que todavía está esperando), hasta 90 segundos.
  for _ in $(seq 180); do
    grep -q "Bootstrapped 100%" "$red/tor.log" 2>/dev/null && break
    # (El Tor recién lanzado se vigila por su proceso: todavía no escribió el
    # archivo con su PID.)
    if { [ -n "$pid_tor" ] && ! kill -0 "$pid_tor" 2>/dev/null; } || { [ -z "$pid_tor" ] && ! tor_corriendo; }; then
      avisar "No se pudo iniciar Tor (detalles en $red/tor.log)."
      exit 1
    fi
    sleep 0.5
  done
  # Sin dirección: la primera ventana muestra la comprobación de Tor; si ya
  # hay una abierta, se agrega una pestaña nueva.
  if ! ((${#urls[@]})); then
    if perfil_abierto "$perfil_tor"; then urls=("about:newtab"); else urls=("https://check.torproject.org/"); fi
  fi
  set +e
  VELBRUM_TOR=1 VELBRUM_TOR_SOCKET="$socket" "@gecko@" --name velbrum-tor --class velbrum-tor \
    --profile "$perfil_tor" "${extra[@]}" "${urls[@]}"
  estado=$?
  # El Tor que arrancó este lanzador se apaga cuando no queda ninguna ventana
  # con Tor: si esta ventana se sumó a una instancia que ya estaba (por
  # ejemplo, con dos clics seguidos), se espera a que esa se cierre.
  if [ -n "$pid_tor" ]; then
    sleep 2
    while perfil_abierto "$perfil_tor"; do sleep 3; done
    kill "$pid_tor" 2>/dev/null
  fi
  exit $estado
}
if ((tor)); then
  abrir_con_tor
fi

args=(--name velbrum --class velbrum --profile "$perfil")
if ((privada)); then
  args+=(--private-window)
  if ((${#urls[@]})); then
    args+=("${urls[0]}")
    urls=("${urls[@]:1}")
  fi
elif ((nueva)); then
  args+=(--new-window)
fi
exec "@gecko@" "${args[@]}" "${extra[@]}" "${urls[@]}"
