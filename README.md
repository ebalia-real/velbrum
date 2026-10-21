# Bruma

Navegador privado propio. Es **LibreWolf** (Firefox sin telemetría y con
protección estricta contra el rastreo) con **los ajustes de privacidad de
Mullvad Browser**, y además **instala extensiones de Chrome**: las adapta solo
a su motor, así que en un mismo navegador usás extensiones de Firefox y de
Chrome, en todas las pestañas.

No compila nada: usa el LibreWolf que ya viene compilado en el caché de NixOS
y le agrega configuración. Cuando actualizás NixOS (`nix flake update`),
Bruma recibe los parches de seguridad de LibreWolf y de Firefox.

> Bruma es un proyecto independiente: no está hecho ni respaldado por Mozilla,
> LibreWolf, Mullvad ni el Tor Project. Firefox, LibreWolf, Mullvad, Tor y
> Chrome son marcas de sus dueños.

## Instalación (NixOS)

Necesita NixOS en x86_64 con un nixpkgs que traiga `librewolf-unwrapped`,
`mullvad-browser` y `tor` (probado con NixOS 26.05).

1. Copiá esta carpeta junto a tu `configuration.nix` (por ejemplo
   `/etc/nixos/bruma`):

   ```bash
   sudo git clone https://github.com/ebalia-real/bruma /etc/nixos/bruma
   ```

2. Importá el módulo en `configuration.nix`:

   ```nix
   imports = [ ./bruma/modulo.nix ];
   ```

3. Aplicá la configuración:

   ```bash
   sudo nixos-rebuild switch
   ```

Opciones (todas opcionales, en `configuration.nix`):

```nix
# Solo extensiones firmadas por Mozilla, fijo para todos (sin la parte de Chrome).
bruma.extensionesDeChrome = false;
# Dominios que van por el DNS del sistema y no por el DNS cifrado: los de tu
# red local y, si usás una VPN con nombres propios, los de esa VPN.
bruma.dominiosLocales = [ "lan" "home" "home.arpa" "internal" "localdomain" ];
```

La interfaz sale en el idioma del sistema (`i18n.defaultLocale`).

## Cómo se usa

- Abrilo desde el menú de aplicaciones: **Bruma**. Con clic derecho en el ícono hay
  «Nueva ventana», «Nueva ventana privada» y «Nueva ventana privada con Tor».
- **Botón «Bruma»** (el símbolo de Bruma en la barra de herramientas, junto a
  las extensiones): abre los ajustes propios de Bruma, que quedan guardados:
  - **Nivel de seguridad**: Estándar, Más seguro o El más seguro, como en
    Mullvad Browser (ver «Privacidad»);
  - **Bordes de privacidad** (ver «Privacidad»);
  - **Siempre privado, como Mullvad**: no guarda historial, cookies ni caché;
  - **Modo liviano** (poca memoria, ver «Modo liviano»);
  - **Solo extensiones firmadas por Mozilla** (ver «Exigir firmas»);
  - **Nueva pestaña con Tor** (ver «Ventana privada con Tor»).

  Si lo sacás de la barra, vuelve desde «Personalizar barra de herramientas».
- **Tor desde el menú ≡**: «Nueva pestaña con Tor», debajo de «Nueva ventana
  privada»; y con clic derecho en un enlace, «Abrir enlace en una pestaña con
  Tor».
- Desde la terminal: `bruma`, `bruma https://ejemplo.com`, `bruma --privada`,
  `bruma --tor`. `bruma --ayuda` muestra todas las opciones.
- Para que sea tu navegador predeterminado: Configuración de GNOME →
  Aplicaciones → Aplicaciones predeterminadas → Web → Bruma.

## Extensiones

**De Firefox**: como en cualquier Firefox, desde
[addons.mozilla.org](https://addons.mozilla.org).

**De Chrome y de Edge**, de forma automática (Edge usa el mismo formato de
extensiones que Chrome):

- En la [Chrome Web Store](https://chromewebstore.google.com), el botón de la
  tienda dice **«Agregar a Bruma»**: tocalo y confirmá en el cartel
  «¿Agregar …?» del navegador. El aviso «Cambia a Chrome» de la tienda
  desaparece solo.
- En la [tienda de Edge](https://microsoftedge.microsoft.com/addons), igual: el
  botón «Get» («Obtener») de cada extensión dice **«Agregar a Bruma»**, en su
  página y en las listas. Desaparecen el cartel «necesitarás el nuevo Microsoft
  Edge» y el aviso «Incompatible con tu explorador». Sirve para las extensiones
  que solo están ahí (por ejemplo, las de Microsoft como Xbox New Tab).
- **Cualquier archivo `.crx`** que descargues de cualquier sitio: al terminar
  la descarga, Bruma te avisa con una notificación; tocala y confirmá en el
  cartel. (Así un sitio no puede hacerte aparecer el cartel sin que lo pidas.)
- Un `.crx` que abras desde el explorador de archivos se instala igual.
- Desde la terminal: `bruma --extension-chrome <ID, URL de cualquiera de las dos tiendas o archivo.crx>`.
  Con un ID solo, Bruma la busca primero en la tienda de Chrome y después en
  la de Edge.

Las extensiones **se actualizan solas una vez por día** (un temporizador de
systemd busca versiones nuevas), cada una en la tienda de la que vino: Bruma lo
anota al instalarla. La versión nueva se activa la próxima vez que abrís Bruma.
Para buscar en el momento: `bruma --actualizar-extensiones`. Solo actualiza las
que instalaste vos, nunca vuelve a una versión anterior, y si la versión nueva
pide permisos nuevos no la instala sola (Firefox te preguntaría): te avisa con
una notificación para que la actualices con `bruma --extension-chrome <ID>` y
veas el cartel.

Las consultas a las tiendas van siempre por https; los archivos, por https
cuando se puede (la tienda de Edge da direcciones http: Bruma las pide por
https y, si tiene que usar http, exige el hash que la tienda mandó por https).
Además, Bruma verifica la **firma del autor** de cada `.crx` (CRX3, como
Chrome) y que sea de la extensión que pediste: un archivo modificado, de otra
extensión o sin firma se rechaza.

### Cómo funciona la conversión

Las extensiones de Chrome y de Firefox usan casi la misma API (WebExtensions).
Bruma descarga la extensión, la adapta y la instala sin firma: Mozilla no puede
firmar extensiones de Chrome, así que Bruma acepta extensiones sin firma, pero
solo instaladas con el cartel de confirmación. Lo que aparezca suelto en la
carpeta del perfil (por ejemplo, puesto ahí por otro programa) queda
desactivado hasta que lo apruebes. Si no querés extensiones sin firma, mirá
«Exigir firmas (opcional)» más abajo. Lo que adapta:

- El *service worker* de fondo de Chrome pasa a ser una página de fondo de
  Gecko, con los scripts que importa (también los fragmentos de webpack y los
  que importa con rutas guardadas en variables).
- Emula APIs que Gecko no tiene: `chrome.offscreen` (con un marco oculto),
  `chrome.sidePanel` (con la barra lateral), `runtime.getContexts`,
  `storage.managed`, `sender.origin`, `notifications.getPermissionLevel`.
- Cambia `chrome-extension://` por `moz-extension://` y saca del manifiesto
  lo que Gecko rechaza. El buscador que agregue una extensión se adapta a lo
  que Gecko exige (nombre y URL sin los comodines propios de Chrome).
- El permiso **`userScripts`** (Tampermonkey, Violentmonkey…), que Chrome
  activa en la configuración de la extensión, en Gecko lo confirmás vos: al
  instalarla se abre una página con un botón «Permitir»; en el cartel que
  aparece **marcá la casilla** y tocá «Permitir».

Probado con Dark Reader, Google Translate, uBlock Origin Lite, Tampermonkey,
Bitwarden y Return YouTube Dislike (de la tienda de Chrome), y con Xbox New Tab
y Block Microsoft Login Popup (que solo están en la de Edge), incluida su
actualización diaria. Si una extensión usa algo de Chrome que
Gecko no tiene (por ejemplo `chrome.tabCapture` o `chrome.tts`), Bruma lo avisa
al instalarla: esa parte puede no funcionar.

### Exigir firmas (opcional)

Por defecto Bruma acepta extensiones sin firma de Mozilla (las de Chrome no
pueden tenerla), siempre con el cartel de confirmación. Si preferís que acepte
**solo extensiones firmadas por Mozilla**, como Firefox, hay dos formas:

**Interruptor (cuando quieras, sin rebuild):** botón «Bruma» de la barra de
herramientas → casilla «Solo extensiones firmadas por Mozilla». Se aplica al
instante: las extensiones de Chrome que tengas quedan desactivadas (no se
borran), no se pueden instalar nuevas (los botones de las tiendas y los `.crx`
te avisan que está activado) y el actualizador diario no hace nada. Al
destildarla, las extensiones de Chrome se reactivan solas. Es por usuario: se
guarda en `~/.local/share/bruma/firmas-obligatorias`. También desde la
terminal (se aplica al volver a abrir Bruma):

```bash
bruma --exigir-firmas
```

y `bruma --permitir-sin-firma` para volver; `bruma --estado-firmas` dice cuál
está activo.

**Fijo para todo el sistema:** agregá esto en tu configuración de NixOS
(`configuration.nix` o el archivo donde importás `modulo.nix`) y hacé el
rebuild:

```nix
bruma.extensionesDeChrome = false;
```

Así la firma queda bloqueada (no se puede cambiar ni con el interruptor ni
desde `about:config`), desaparece la parte de Chrome (extensión de las
tiendas, `.crx`, actualizador, acciones del menú) y las extensiones de Chrome
que ya tengas quedan desactivadas. Para volver, borrá la línea. El idioma
sigue funcionando igual en los dos casos.

## Seguridad

- **Nada se instala sin tu confirmación.** Las extensiones sin firma solo
  entran con el cartel «¿Agregar …?»; lo que aparezca suelto en la carpeta del
  perfil, en `~/.mozilla/extensions` o en carpetas del sistema queda
  desactivado hasta que lo apruebes, y esa regla está bloqueada (ni un
  `user.js` la cambia).
- **Pedidos de instalación.** La extensión de Bruma solo acepta pedidos de las
  páginas de las dos tiendas (y del marco principal), y solo después de un clic
  tuyo de verdad (un script de la página no puede «hacer clic» por vos). Los
  `.crx` descargados esperan a que toques la notificación. Siempre termina en el
  cartel de Firefox.
- **Host nativo** (el programa que baja y convierte): solo le puede hablar la
  extensión de Bruma (`allowed_extensions`), valida los IDs (32 letras a–p) y
  las rutas, y no usa la terminal para nada.
- **Lo que se baja:** https a los servidores de cada tienda, hash anunciado por
  la tienda, firma del autor (CRX3) y que el ID firmado sea el pedido. También
  rechaza archivos enormes, «bombas zip» y nombres de archivo que salgan de la
  extensión (`..`, rutas absolutas).
- **Actualizaciones:** solo de lo que instalaste vos, nunca a una versión
  anterior y nunca con permisos nuevos sin preguntarte.
- **Permisos de archivos:** el perfil y las extensiones convertidas quedan en
  carpetas que solo tu usuario puede leer (700), como hace Firefox.
- **Lo que no cubre:** como en cualquier navegador, un programa que ya corre
  con tu usuario puede modificar tu perfil. Mientras Bruma acepte extensiones
  sin firma, eso incluye reemplazar el archivo de una extensión que ya
  instalaste; con las firmas exigidas (interruptor u opción del sistema, más
  arriba) Firefox exige la firma de Mozilla también en ese caso.

Para repetir las pruebas de seguridad del conversor (necesita internet):

```bash
python3 -I pruebas/seguridad.py   # desde la carpeta de Bruma
```

## Privacidad

Bruma parte de LibreWolf, que ya trae: resistencia a la huella digital
(*resistFingerprinting*), protección estricta contra el rastreo (cookies
aisladas por sitio, bloqueo de rastreadores, limpieza de parámetros como
`fbclid` o `gclid` en los enlaces), uBlock Origin, modo solo-HTTPS, Global
Privacy Control, sin telemetría, sin Safe Browsing de Google, sin gestor de
contraseñas ni DRM, y borra cookies y caché al cerrar (el historial queda).

Y le suma lo de Mullvad Browser que LibreWolf no tiene:

| Qué | Para qué |
|---|---|
| Bordes de privacidad (*letterboxing*) | El área de la página se redondea a tamaños comunes (por ejemplo 1200×600 en vez de 1323×683): los bordes que ves alrededor son lo que sobra. Así el tamaño exacto de tu ventana, que junto con otros datos te identifica, no llega a los sitios. Se sacan y se ponen desde el botón «Bruma» (casilla «Bordes de privacidad»), al instante, o con `bruma --sin-bordes` / `bruma --con-bordes`. |
| Páginas en inglés | Las páginas ven `en-US`, como los demás usuarios de Mullvad/Tor; la interfaz de Bruma sigue en español. |
| Las fuentes de Mullvad Browser | Las páginas solo ven las 146 fuentes que trae Mullvad Browser (las mismas para todos), no las de tu PC. |
| DNS cifrado (Quad9) | Tu proveedor de internet no ve qué sitios visitás. Quad9 también bloquea dominios de malware. Los dominios de la red local (y los que agregues en `bruma.dominiosLocales`) van por el DNS del sistema. |
| WebRTC sin IPs locales | Ni las IPs de la red local ni las de una VPN se exponen, aunque des permiso de cámara o micrófono. |

Y también lo que Mullvad Browser 15 cambia por su cuenta (comparado
preferencia por preferencia con su paquete, en `gecko/ajustes.cfg`):

| Qué | Para qué |
|---|---|
| Aislamiento estricto por sitio (*first-party isolation*) | Cookies, caché, conexiones y almacenamiento separados por sitio, como en Tor y Mullvad. (Las cookies de terceros quedan separadas por sitio en lugar de bloqueadas como en Mullvad: el mismo aislamiento, con menos sitios rotos.) |
| Menos superficie de ataque y rastreo | Sin *service workers*, notificaciones push, MIDI, geolocalización, WebGL 2 ni SharedArrayBuffer. |
| WebRTC solo por servidores intermedios | La otra punta de una llamada no ve tu IP. |
| Huella | Almacenamiento disponible fijo, sin colores ni acento del sistema, sin identificadores de sesión TLS, y la misma fuente que Mullvad para cada idioma. |
| Sin conexiones solas a Mozilla | Sin push, sin plugins de video (Widevine/OpenH264) ni ajustes remotos de la protección contra huella. Las traducciones quedan (Mullvad las apaga): traducen en tu PC y solo bajan el modelo del idioma cuando las usás. |
| Proxy que no se saltea | Con la ventana con Tor o una VPN, ni las extensiones ni una caída del proxy hacen que se conecte directo. |
| Llaves de acceso (*passkeys*) apagadas | Identifican tu equipo; para usarlas, ver «Ajustes». |
| **Nivel de seguridad** (botón «Bruma») | *Estándar*: todo funciona. *Más seguro*: sin el compilador rápido de JavaScript ni WebAssembly, sin algunas fuentes y símbolos matemáticos, audio y video con un clic. *El más seguro*: además sin JavaScript, SVG, WebGL ni fuentes descargadas. Como en Mullvad, pero con preferencias de Gecko en lugar de NoScript. |
| **Siempre privado** (opcional, botón «Bruma») | Lo que Mullvad hace siempre: no queda historial, cookies ni caché en el disco. Las extensiones necesitan permiso para ventanas privadas (en Complementos). |

Lo que Bruma deja más estricto que Mullvad: la protección contra rastreo de
Firefox (Mullvad la apaga), la revocación de certificados (CRLite) y WebGL,
que como en LibreWolf cada sitio te pide permiso para usar (los mapas y
juegos lo necesitan); Mullvad lo deja siempre activo.

### Resultados de los tests (19 y 20/10/2026)

Medidos con Bruma abierto normalmente (sin herramientas de automatización, que
desactivan parte de la protección), con la interfaz en español y las páginas
en inglés:

- **EFF Cover Your Tracks**: «protección fuerte contra el rastreo web»;
  bloquea anuncios de rastreo y rastreadores invisibles; huella canvas
  «aleatoria».
- **BrowserLeaks WebRTC**: sin fuga, no se ve ninguna IP local (tampoco la de
  una VPN).
- **BrowserLeaks JavaScript**: zona horaria UTC (`Atlantic/Reykjavik`),
  idioma `en-US`, sin *client hints*, Global Privacy Control activo.
- **BrowserLeaks Canvas**: la huella del canvas cambia en cada sesión.
- **CreepJS**: pantalla 1200×900 (la del letterboxing, no la real), solo 7
  fuentes detectables (las de Mullvad), canvas con ruido, WebGL bloqueado hasta
  que lo permitas.
- **ipleak.net**: los DNS que ven los sitios son los de Quad9, no los del
  proveedor de internet.
- **Comparación con Mullvad Browser 15.0.23 en la misma PC** (20/10/2026,
  con los ajustes de Mullvad sumados; la misma página de prueba en los dos):
  iguales idioma, zona horaria, núcleos (4), pantalla y ventana, densidad de
  píxeles, fuentes visibles, medidas de las fuentes de cada tipo, huella de
  audio, GPC, visor de PDF, cuota de almacenamiento, y sin service workers,
  geolocalización, MIDI, SharedArrayBuffer, WebGL 2 ni llaves de acceso.
  Además, de las 246 preferencias de privacidad en que Bruma difería de
  Mullvad, quedan solo las que son a propósito (marca, actualizaciones, DNS de
  Quad9, y lo que Bruma deja más estricto). Diferencias que quedan, propias de
  Firefox 156 frente al 140 de Mullvad (ninguna preferencia las cambia):
  - versión de Firefox: Bruma usa la 156 (al día con los parches de
    seguridad), Mullvad la 140 ESR;
  - puntos táctiles: 5 en Bruma, 0 en Mullvad;
  - `Accept-Language`: `en-US,en;q=0.9` contra `q=0.5` en Mullvad;
  - WebGL: Bruma pregunta por sitio antes de activarlo (más estricto), Mullvad
    lo deja activo con datos genéricos.
- **Ventana con Tor** (20/10/2026): check.torproject.org dice «Congratulations.
  This browser is configured to use Tor»; cada sitio salió por otra IP de Tor
  (check.torproject.org, api.ipify.org e icanhazip.com, tres IPs distintas);
  WebRTC no existe en las páginas; proxy, DNS y modo privado bloqueados; al
  elegir país, la IP de salida pasó a ser de ese país (Alemania, Países Bajos,
  Estados Unidos, según el directorio de Tor); al cerrar la ventana, Tor se
  apaga.

Cover Your Tracks igual dice «huella casi única»: le pasa a cualquier navegador
con *resistFingerprinting* (también a Mullvad y a Tor), porque casi nadie en su
base de datos usa esos valores. Lo que importa es que la huella sea la misma
para todos los usuarios de navegadores así y que no salga de tu equipo real.
Bruma se parece a los demás usuarios de LibreWolf/Firefox 156 con
*resistFingerprinting*, no a los de Mullvad Browser.

### Ventana privada con Tor

Se abre desde el menú ≡ → «Nueva pestaña con Tor», el botón «Bruma», con
clic derecho en un enlace («Abrir enlace en una pestaña con Tor»), con clic
derecho en el ícono de Bruma («Nueva ventana privada con Tor») o con
`bruma --tor`. Si la ventana con Tor ya está abierta, se agrega una pestaña
ahí. Es otra ventana de Bruma (se reconoce por la línea violeta debajo de la
barra) que sale a internet por la red Tor: los sitios ven una IP de Tor, no
la tuya, y tu proveedor solo ve que usás Tor. No puede ser una pestaña con
Tor adentro de una ventana normal: compartiría cookies y huella con el resto
de las pestañas y se te podría reconocer.

- **Aparte de tu Bruma normal:** otro perfil (`~/.local/share/bruma/tor`),
  siempre privado (al cerrar no queda nada), sin tus cookies ni tu historial.
- **Su propio Tor:** Bruma arranca un Tor solo para esa ventana y lo apaga al
  cerrarla (no queda un servicio corriendo ni gastando memoria). Escucha en un
  socket que solo tu usuario puede usar. Bruma espera a que Tor termine de
  conectarse («Conectando a Tor…», la primera vez puede tardar un minuto) y
  abre https://check.torproject.org para confirmar. Tor sigue mientras haya
  alguna ventana con Tor abierta (aunque hayas hecho varios clics) y se apaga
  cuando cerrás la última.
- **Un circuito por sitio**, como Tor Browser: cada sitio sale por otra IP de
  Tor, así no se pueden relacionar entre sí por la IP.
- **País de salida** (botón «Bruma» de esa ventana, o `bruma --tor-pais de`):
  «Automático» (el más anónimo) o Alemania, Países Bajos, Estados Unidos,
  Suecia, Austria, Francia, Noruega, Suiza, Rumania, Finlandia, Islandia,
  Dinamarca o Luxemburgo: los países con suficientes nodos de salida de Tor
  (muchos países no tienen ninguno). Se aplica al instante (circuitos
  nuevos y recarga la pestaña) y queda guardado. «Circuitos nuevos» cambia de
  IP sin cambiar de país. Es lo más parecido a una VPN gratis por países, sin
  cuenta: la diferencia es que en una VPN confiás en una empresa y en Tor, en
  que tres nodos de voluntarios no se pongan de acuerdo. Elegir un país te
  hace un poco más fácil de distinguir que «Automático», y es más lento que
  una VPN.
- **Todo por Tor y bloqueado:** DNS por Tor, sin WebRTC ni HTTP/3, bordes de
  privacidad siempre puestos, sin la extensión de las tiendas de Chrome (su
  conversor no pasa por Tor) y sin instalar extensiones. Se puede elegir el
  nivel de seguridad desde el botón «Bruma».

**No es Tor Browser:** los sitios ven la huella de Bruma (Firefox 156 con
*resistFingerprinting*), no la de Tor Browser, que es igual para millones de
personas. Oculta tu IP, pero si necesitás anonimato de verdad (periodismo,
riesgo real), usá Tor Browser. Algunos sitios bloquean Tor o piden captchas.

### Modo liviano

Para PCs con poca memoria: desde el botón «Bruma» (casilla «Modo liviano»), y
se prende solo en PCs con menos de 4 GB. Usa menos procesos y caché, no
guarda en memoria las páginas anteriores, y descarga las pestañas que no usás
(después de 5 minutos) cuando a la PC le falta memoria. El aislamiento de
sitios (Fission) queda: es una protección de seguridad importante y apagarlo
no mostró un ahorro claro.

Medido (20/10/2026, perfil ya usado, memoria real PSS de todos los procesos):
con 2 pestañas livianas Bruma usa entre 710 y 980 MB, y con 6 pestañas pesadas
(YouTube, Reddit, BBC…) unos 1,6 GB. El modo liviano baja la cantidad de
procesos (de 13 a 10) pero en reposo la diferencia queda dentro del ruido de
la medición (±70 MB); donde ayuda es cuando la memoria se acaba, liberando
pestañas en lugar de trabar la PC. En la práctica: con 2 GB se usa bien con
pocas pestañas (mejor con un escritorio liviano como XFCE o LXQt en lugar de
GNOME, que ya ocupa cerca de 1 GB); con 1 GB, ningún navegador moderno anda
cómodo.

### Lo que Bruma no puede ocultar

Ningún navegador es totalmente privado. Bruma protege lo que pasa adentro del
navegador, pero:

- **Tu IP se ve** en las ventanas normales. Los sitios ven tu IP (y con ella
  tu proveedor y tu ciudad aproximada) y tu proveedor ve a qué servidores te
  conectás, aunque no vea las consultas DNS. Para ocultarla: la ventana privada con Tor,
  una VPN (por ejemplo Mullvad VPN) o Tor Browser.
- **Cuentas.** Si iniciás sesión (Google, Microsoft, redes sociales), ese
  sitio sabe que sos vos.
- **Extensiones.** Cada extensión que instalás cambia tu huella y, si tiene
  acceso a todos los sitios (como Dark Reader), puede leer las páginas que
  abrís. Bruma verifica que el archivo sea del autor, no lo que hace.
- **Servidores que contacta solo:** los de Mozilla que LibreWolf deja activos
  (listas de bloqueo, revocación de certificados, actualizaciones de
  complementos) y, una vez por día, la tienda de Chrome o la de Edge para
  buscar versiones nuevas de tus extensiones de Chrome (ven tu IP y los IDs
  de esas extensiones). Con las firmas exigidas, el actualizador no se
  conecta.
- **Huella.** Medida, es igual a la de Mullvad Browser salvo la versión de
  Firefox y dos detalles que dependen de ella; pero eso alcanza para que un
  sitio sepa que no sos Mullvad ni Tor Browser, y los usuarios de Bruma son
  pocos. «Que no se detecte nada» no es posible con ningún navegador: siempre
  se ve algo (tu IP, que usás Tor, o tu huella).
- **En tu PC** queda el historial (las cookies y la caché se borran al
  cerrar), salvo con «Siempre privado». Las ventanas privadas y la de Tor no
  guardan nada.

## Ajustes

- Para ver las páginas en español: en `about:config`, poné
  `privacy.spoof_english` en `1` y elegí los idiomas en Ajustes. Te hace más
  fácil de distinguir.
- Para que WebGL funcione sin preguntar: `librewolf.webgl.prompt` en `false`.
- Para guardar contraseñas, mantener cookies de un sitio, etc.: en Ajustes,
  como en Firefox.
- Si un sitio no anda por las protecciones de Mullvad, en `about:config`:
  llaves de acceso (*passkeys*) → `security.webauth.webauthn` en `true`;
  llamadas que no conectan → `media.peerconnection.ice.relay_only` en `false`;
  sitios que necesitan *service workers* (aplicaciones web sin conexión) →
  `dom.serviceWorkers.enabled` en `true`; inicios de sesión entre sitios que
  fallan → `privacy.firstparty.isolate` en `false`. Cada uno te hace un poco
  más fácil de distinguir.
- Ajustes propios permanentes: un archivo `user.js` en
  `~/.local/share/bruma/gecko/`.

## Marca e idioma

Bruma usa el motor de LibreWolf, pero adentro del navegador no aparece
LibreWolf: el logo, los íconos, la nueva pestaña, «Acerca de Bruma», Ajustes,
el menú Ayuda (sin el acceso a LibreWolf) y `about:support` dicen Bruma. Se
hace al compilar, reemplazando archivos dentro de los `omni.ja` de LibreWolf
(`marca/textos.py` y `marca/codigo.py`). La barra de pestañas no deja el
espacio vacío de 40 px que Firefox pone antes de la primera pestaña en las
ventanas sin maximizar: la pestaña queda alineada con el borde y con el botón
«atrás» (la ventana se arrastra desde la parte vacía de la barra). Tampoco se contacta a los servidores
de LibreWolf: uBlock Origin baja su índice de listas de su propia fuente
(GitHub y sus espejos), no de librewolf.dev (comprobado con un perfil nuevo:
ninguna conexión a librewolf.dev).

En los perfiles creados antes del 19/10/2026, uBlock Origin había guardado el
índice de LibreWolf y lo volvía a pedir a librewolf.dev cada 13 días. Bruma lo
arregla solo, una vez por perfil: al abrirlo (con Bruma cerrado), si encuentra
librewolf.dev en los datos de uBlock Origin los borra, lo mismo que su botón
«Restablecer ajustes predeterminados…», y uBlock Origin vuelve a arrancar con
sus listas por defecto, de su propia fuente. Solo se pierden los ajustes
propios de uBlock Origin (listas elegidas, sitios permitidos); el resto del
perfil no se toca. Queda anotado en `~/.local/share/bruma/ubo-sin-librewolf`.

La interfaz va en el idioma del sistema (`i18n.defaultLocale`, por ejemplo
`es_ES.UTF-8` → paquete es-ES). Mozilla publica un paquete de idioma por versión, pero su marca dice
«Firefox»: el servicio de sistema `bruma-idioma` baja el de tu idioma y
versión, le pone la marca «Bruma» y lo deja en `/var/lib/bruma/idioma`, una
carpeta que solo root puede modificar; desde ahí lo instala una política del
navegador. Corre al arrancar la PC y en cada rebuild que traiga una versión
nueva; sin internet, Bruma abre en inglés y el servicio reintenta cada 10
minutos. (LibreWolf borraba los paquetes de idioma en cada arranque; Bruma le
saca eso.)

Si una actualización de LibreWolf cambia algo de esto, la compilación lo
avisa con «AVISO» en el registro, sin cortar el rebuild.

Después de cada rebuild, el menú de GNOME se actualiza solo (acciones y
textos de Bruma): el módulo crea y borra un archivo vacío en
`~/.local/share/applications`, que hace que GNOME vuelva a leer el menú. Si
alguna vez cambia el ícono y GNOME muestra uno genérico, cerrá sesión y volvé a
entrar: los íconos nuevos no los relee mientras la sesión está abierta.

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Perfil (historial, extensiones, ajustes) | `~/.local/share/bruma/gecko/` |
| Extensiones de Chrome y Edge convertidas | `~/.local/share/bruma/extensiones-chrome/` |
| Host de mensajería nativa | `~/.librewolf/native-messaging-hosts/bruma.extensiones.json` (lo crea el lanzador) |
| Ventana con Tor: perfil (siempre privado) | `~/.local/share/bruma/tor/` |
| Ventana con Tor: datos de Tor y su registro | `~/.local/share/bruma/tor-red/` (el país elegido, en `~/.local/share/bruma/tor-pais`) |
| Ventana con Tor: sockets (SOCKS y control) | `/run/user/<tu uid>/bruma-tor/` (solo tu usuario) |

Archivos de esta carpeta:

| Archivo | Qué hace |
|---|---|
| `modulo.nix` | Módulo NixOS: instala Bruma, el servicio del idioma, el temporizador de actualización de extensiones y el refresco del menú de GNOME. |
| `default.nix` | El paquete: LibreWolf + ajustes, fuentes de Mullvad, extensión propia, lanzador. |
| `gecko/ajustes.cfg` | Los ajustes de Mullvad que se suman a los de LibreWolf. |
| `lanzador.sh` | El comando `bruma`. |
| `extension/` | Extensión propia de Bruma: botones de las tiendas de Chrome (`tienda.js`) y de Edge (`edge.js`), lo que comparten (`aviso.js`) e instalación de `.crx`. |
| `host/host-extensiones.py` | Recibe los pedidos de la extensión y abre la instalación. |
| `host/extensiones_chrome.py` | Descarga (de la tienda de Chrome o de Edge), convierte y actualiza las extensiones. |
| `host/compat/` | Capa de compatibilidad que va dentro de cada extensión convertida. |
| `host/tor-pais.py` | Le cambia el país de salida al Tor de la ventana con Tor (por su socket de control). |
| `iconos/bruma.svg` | El logo: un globo (la web) que se desarma en jirones de niebla. |
| `iconos/bruma-chico.svg` | El logo simplificado para 16–32 px (pestañas, barra de tareas). |
| `marca/` | La marca de Bruma: nombre (`nombre.svg`, `brand.ftl`), ícono de Ajustes, el botón «Bruma» con sus ajustes (`ajustes-bruma.sys.mjs`) y los scripts que la aplican a LibreWolf y al paquete de idioma. |
| `pruebas/seguridad.py` | Pruebas de seguridad del conversor (firma CRX3, archivos peligrosos, redirecciones, actualizador, interruptor de firmas). |

## Por qué no Mullvad Browser ni un motor Chromium

- **Mullvad Browser no está abandonado** (sacó la 15.0.25 el 14/10/2026), pero
  su protección depende de que todos sus usuarios sean idénticos: cualquier
  extensión la rompe. Además, en nixpkgs suele ir atrasado en parches.
- **Un motor que mezcle Gecko y Chromium no existe.** Bruma usa un solo motor
  (Gecko) y adapta las extensiones de Chrome, que casi siempre funcionan.

## Licencia

Bruma se publica bajo la [Mozilla Public License 2.0](LICENSE) (MPL-2.0), la
misma familia de licencias que Firefox y LibreWolf.
