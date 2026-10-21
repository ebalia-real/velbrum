<p align="center">
  <img src="iconos/bruma.svg" width="128" height="128" alt="Logo de Bruma">
</p>

<h1 align="center">Bruma</h1>

<p align="center">
  <b>Un navegador privado para NixOS.</b><br>
  LibreWolf con la protección de Mullvad Browser, extensiones de Chrome y una ventana con Tor incluida.
</p>

<p align="center">
  <a href="LICENSE"><img alt="Licencia: MPL-2.0" src="https://img.shields.io/badge/licencia-MPL--2.0-8573ff"></a>
  <img alt="NixOS 26.05" src="https://img.shields.io/badge/NixOS-26.05-5277C3?logo=nixos&amp;logoColor=white">
  <img alt="Motor: Gecko 156" src="https://img.shields.io/badge/motor-Gecko%20156-FF7139?logo=firefoxbrowser&amp;logoColor=white">
  <img alt="Tor incluido" src="https://img.shields.io/badge/Tor-incluido-7D4698?logo=torproject&amp;logoColor=white">
  <img alt="Extensiones de Chrome" src="https://img.shields.io/badge/extensiones%20de%20Chrome-s%C3%AD-4285F4?logo=googlechrome&amp;logoColor=white">
</p>

<p align="center">
  <a href="README.md">English</a> · <b>Español</b>
</p>

<p align="center">
  <img src="docs/panel.png" width="820" alt="Bruma con su panel de ajustes abierto">
</p>

---

## Lo principal

| | |
|---|---|
| 🛡️ **Privacidad como Mullvad** | Bordes de privacidad, las mismas fuentes e idioma que Mullvad Browser, aislamiento por sitio, sin WebGL 2, *service workers* ni geolocalización… Medido lado a lado con Mullvad Browser: la misma huella salvo la versión de Firefox. |
| 🧅 **Tor con un clic** | *Nueva pestaña con Tor* en el menú ≡ o en cualquier enlace. Una ventana privada aparte, con su propio Tor, un circuito por sitio y país de salida a elección. |
| 🧩 **Extensiones de Firefox y de Chrome** | Un botón **Agregar a Bruma** en la Chrome Web Store y en la tienda de Edge, y cualquier archivo `.crx`. Se adaptan solas a Gecko, se verifica la firma del autor y se actualizan cada día. |
| ⚙️ **Botón «Bruma»** | Nivel de seguridad (Estándar, Más seguro, El más seguro), bordes de privacidad, siempre privado, modo liviano y solo extensiones firmadas, en la barra de herramientas. |
| 🔒 **DNS cifrado** | DNS por HTTPS solo con Quad9, con excepciones para tu red local. |
| 🪶 **Modo liviano** | Menos procesos y caché para computadoras con poca memoria; se activa solo con menos de 4 GB de RAM. |
| 🔄 **Actualizaciones con un clic** | Bruma busca versiones nuevas **firmadas** una vez por día y, si aceptas, las instala (contraseña de administrador) y reinicia con tus pestañas. Los parches de seguridad de Firefox llegan con cada actualización del sistema; no compila nada. |

> Bruma es un proyecto independiente: no está hecho ni respaldado por Mozilla,
> LibreWolf, Mullvad ni el Tor Project. Firefox, LibreWolf, Mullvad, Tor y Chrome
> son marcas de sus dueños.

## Instalación

Necesita NixOS en x86_64 con un nixpkgs que tenga `librewolf-unwrapped`,
`mullvad-browser` y `tor` (probado con NixOS 26.05).

1. Pon esta carpeta junto a tu `configuration.nix`:

   ```bash
   sudo git clone https://github.com/ebalia-real/bruma /etc/nixos/bruma
   ```

2. Importa el módulo en `configuration.nix`:

   ```nix
   imports = [ ./bruma/modulo.nix ];
   ```

3. Aplica la configuración:

   ```bash
   sudo nixos-rebuild switch
   ```

Opciones, también en `configuration.nix` (todas opcionales):

```nix
# Solo extensiones firmadas por Mozilla, fijo para todos (sin extensiones de Chrome).
bruma.extensionesDeChrome = false;
# Dominios que se resuelven con el DNS del sistema y no con el DNS cifrado: los de
# tu red local y, si usas una VPN con nombres propios, los de esa VPN.
bruma.dominiosLocales = [ "lan" "home" "home.arpa" "internal" "localdomain" ];
```

La interfaz sale en el idioma del sistema (`i18n.defaultLocale`); las páginas ven
`en-US`, como todos los usuarios de Mullvad y de Tor.

## Cómo se usa

<table>
  <tr>
    <td width="50%"><img src="docs/menu.png" alt="Menú ≡ con Nueva pestaña con Tor"></td>
    <td width="50%"><img src="docs/tor.png" alt="Ventana con Tor en check.torproject.org"></td>
  </tr>
  <tr>
    <td align="center"><sub>Menú ≡ → <i>Nueva pestaña con Tor</i></sub></td>
    <td align="center"><sub>La ventana con Tor, confirmada por check.torproject.org</sub></td>
  </tr>
</table>

- **Ábrelo** desde el menú de aplicaciones: **Bruma**. Con clic derecho en el
  ícono hay *Nueva ventana*, *Nueva ventana privada* y *Nueva ventana privada con
  Tor*.
- **Botón «Bruma»** (el símbolo de Bruma en la barra de herramientas): abre los
  ajustes propios de Bruma:
  - **Nivel de seguridad**: *Estándar*, *Más seguro* o *El más seguro*, como en
    Mullvad Browser;
  - **Bordes de privacidad**, que se quitan y se ponen al instante;
  - **Siempre privado, como Mullvad**: no guarda historial, cookies ni caché;
  - **Modo liviano** para computadoras con poca memoria;
  - **Solo extensiones firmadas por Mozilla**;
  - **Nueva pestaña con Tor**.
- **Tor desde el menú ≡**: *Nueva pestaña con Tor*, justo debajo de *Nueva
  ventana privada*; y en cualquier enlace, clic derecho → *Abrir enlace en una
  pestaña con Tor*.
- **Desde una terminal**: `bruma`, `bruma https://ejemplo.com`, `bruma --privada`,
  `bruma --tor`. `bruma --ayuda` muestra todas las opciones.

## Ventana con Tor

Una ventana de Bruma aparte que sale a internet por la red Tor: los sitios ven
una dirección de Tor en lugar de la tuya, y tu proveedor de internet solo ve que
usas Tor. Si la ventana con Tor ya está abierta, se agrega una pestaña ahí. No
puede ser una pestaña con Tor dentro de una ventana normal: compartiría cookies
y huella con tus otras pestañas.

- **Aparte de tu Bruma normal**: su propio perfil, siempre privado (al cerrarla
  no queda nada), sin tus cookies ni tu historial.
- **Su propio Tor**: arranca solo para esa ventana y se apaga cuando cierras la
  última; no queda un servicio corriendo ni gastando memoria. Escucha en un
  socket que solo tu usuario puede abrir. Bruma espera a que Tor se conecte (la
  primera vez puede tardar un minuto) y abre check.torproject.org para
  confirmarlo.
- **Un circuito por sitio**, como Tor Browser: cada sitio ve otra dirección de
  Tor, así no se pueden relacionar entre sí por la IP.
- **País de salida** (botón «Bruma» de esa ventana, o `bruma --tor-pais de`):
  *Automático* (el más anónimo) o Alemania, Países Bajos, Estados Unidos, Suecia,
  Austria, Francia, Noruega, Suiza, Rumania, Finlandia, Islandia, Dinamarca o
  Luxemburgo, los países con suficientes nodos de salida de Tor. Se aplica al
  instante y queda guardado. *Circuitos nuevos* cambia de dirección sin cambiar
  de país. Es lo más parecido a una VPN gratis por países y sin cuenta: en una
  VPN confías en una empresa; en Tor, en que tres nodos de voluntarios no se
  pongan de acuerdo. Elegir un país te hace un poco más fácil de distinguir que
  *Automático*, y Tor es más lento que una VPN.
- **Todo bloqueado**: DNS por Tor, sin WebRTC ni HTTP/3, bordes de privacidad
  siempre puestos, sin la extensión de las tiendas (su conversor no pasa por
  Tor) y sin instalar extensiones.

> **No es Tor Browser.** Los sitios ven la huella de Bruma (Firefox 156 con
> *resistFingerprinting*), no la de Tor Browser, que es igual para millones de
> personas. Oculta tu IP, pero si necesitas anonimato de verdad (periodismo,
> riesgo real), usa Tor Browser. Algunos sitios bloquean Tor o piden captchas.

## Privacidad

Bruma parte de LibreWolf, que ya trae resistencia a la huella digital
(*resistFingerprinting*), protección estricta contra el rastreo, uBlock Origin,
modo solo HTTPS, Global Privacy Control, sin telemetría, sin Safe Browsing de
Google, sin gestor de contraseñas ni DRM, y borra cookies y caché al cerrar.

Y le suma lo que Mullvad Browser hace y LibreWolf no:

| Qué | Para qué |
|---|---|
| Bordes de privacidad (*letterboxing*) | El área de la página se redondea a tamaños comunes (por ejemplo 1200×600 en vez de 1323×683); los bordes que ves son lo que sobra. El tamaño exacto de tu ventana, que ayuda a identificarte, no llega a los sitios. |
| Páginas en inglés | Los sitios ven `en-US`, como todos los usuarios de Mullvad y de Tor; la interfaz de Bruma sigue en tu idioma. |
| Las fuentes de Mullvad Browser | Las páginas solo ven las fuentes que trae Mullvad Browser, con la misma fuente para cada idioma, no las de tu computadora. |
| DNS cifrado (Quad9) | Tu proveedor de internet no ve qué sitios visitas. Quad9 también bloquea dominios de malware. |
| Aislamiento por sitio | Cookies, caché, conexiones y almacenamiento separados por sitio, como en Tor y Mullvad. |
| Menos superficie de ataque | Sin *service workers*, notificaciones push, MIDI, geolocalización, WebGL 2 ni SharedArrayBuffer. |
| WebRTC solo por servidores intermedios | La otra punta de una llamada no ve tu IP, y no se filtran direcciones locales ni de una VPN. |
| Huella | Cuota de almacenamiento fija, sin colores ni acento del sistema, sin identificadores de sesión TLS. |
| Sin conexiones solas a Mozilla | Sin push, sin plugins de video (Widevine/OpenH264), sin ajustes remotos de la protección contra huella. |
| Proxy que no se puede saltear | Con la ventana con Tor o una VPN, ni las extensiones ni una caída del proxy hacen que se conecte directo. |
| **Nivel de seguridad** | *Estándar*: todo funciona. *Más seguro*: sin el compilador rápido de JavaScript ni WebAssembly, sin algunas fuentes y símbolos matemáticos, audio y video con un clic. *El más seguro*: además sin JavaScript, SVG, WebGL ni fuentes descargadas. Como en Mullvad, pero con preferencias de Gecko en lugar de NoScript. |
| **Siempre privado** (opcional) | Lo que Mullvad hace siempre: no se guarda historial, cookies ni caché en el disco. |

Donde Bruma es más estricto que Mullvad: la protección contra rastreo de Firefox
sigue activa (Mullvad la apaga), la revocación de certificados (CRLite) también,
y WebGL pide permiso en cada sitio, como en LibreWolf.

<details>
<summary><b>Resultados de las pruebas</b></summary>

Medido con Bruma abierto normalmente (las herramientas de automatización apagan
parte de la protección), con la interfaz en español y las páginas en inglés:

- **EFF Cover Your Tracks**: «protección fuerte contra el rastreo web»; bloquea
  anuncios de rastreo y rastreadores invisibles; huella del canvas aleatoria.
- **BrowserLeaks WebRTC**: sin fugas, no se ve ninguna IP local (ni la de una
  VPN).
- **BrowserLeaks JavaScript**: zona horaria UTC (`Atlantic/Reykjavik`), `en-US`,
  sin *client hints*, Global Privacy Control activo.
- **BrowserLeaks Canvas**: la huella del canvas cambia en cada sesión.
- **CreepJS**: pantalla de 1200×900 (la de los bordes, no la real), solo 7
  fuentes detectables (las de Mullvad), canvas con ruido, WebGL bloqueado hasta
  que lo permitas.
- **ipleak.net**: los sitios ven los servidores DNS de Quad9, no los de tu
  proveedor.
- **Lado a lado con Mullvad Browser 15.0.23** (la misma página de prueba en los
  dos): iguales idioma, zona horaria, cantidad de núcleos, tamaño de pantalla y
  ventana, densidad de píxeles, fuentes visibles, medidas de las fuentes, huella
  de audio, GPC, visor de PDF y cuota de almacenamiento, y ninguno expone
  *service workers*, geolocalización, MIDI, SharedArrayBuffer, WebGL 2 ni llaves
  de acceso. De las 246 preferencias de privacidad en las que Bruma difería de
  Mullvad, solo quedan las que son a propósito. Diferencias que quedan, propias
  de Firefox 156 frente al 140 de Mullvad (ninguna preferencia las cambia): la
  versión de Firefox, los puntos táctiles (5 contra 0) y el formato de
  `Accept-Language` (`q=0.9` contra `q=0.5`).
- **Ventana con Tor**: check.torproject.org dice «Congratulations. This browser
  is configured to use Tor»; tres sitios distintos salieron por tres direcciones
  de Tor distintas; WebRTC no existe en las páginas; proxy, DNS y modo privado
  quedan bloqueados; al elegir un país, la salida pasó a ese país (Alemania,
  Países Bajos, Estados Unidos, según el directorio de Tor); Tor se apaga al
  cerrar la última ventana con Tor.

Cover Your Tracks igual dice «huella casi única»: le pasa a cualquier navegador
con *resistFingerprinting* (también a Mullvad y a Tor), porque poca gente en su
base de datos comparte esos valores.

</details>

## Extensiones de Chrome y de Edge

- En la [Chrome Web Store](https://chromewebstore.google.com) y en la
  [tienda de Edge](https://microsoftedge.microsoft.com/addons), el botón de la
  tienda dice **Agregar a Bruma**: haz clic y confirma en el cartel de
  instalación de Firefox. Los avisos de «cámbiate a Chrome/Edge» desaparecen.
- **Cualquier archivo `.crx`** que descargues: al terminar la descarga, Bruma
  muestra una notificación; haz clic en ella y confirma. Un `.crx` abierto desde
  el explorador de archivos se instala igual.
- **Desde una terminal**: `bruma --extension-chrome <ID, URL de la tienda o archivo.crx>`.
- **Se actualizan cada día** desde la tienda de la que vino cada una; nunca a una
  versión anterior, y nunca con permisos nuevos sin preguntarte.

Las extensiones de Chrome y de Firefox usan casi la misma API (WebExtensions).
Bruma descarga la extensión, verifica la firma del autor (CRX3, como Chrome), la
adapta y la instala: el *service worker* de fondo de Chrome pasa a ser una página
de fondo de Gecko, se emulan las API que faltan (`chrome.offscreen`,
`chrome.sidePanel`, `runtime.getContexts`, `storage.managed`…) y se quita del
manifiesto lo que Gecko rechaza. Probado con Dark Reader, Google Translate,
uBlock Origin Lite, Tampermonkey, Bitwarden, Return YouTube Dislike, Xbox New Tab
y Block Microsoft Login Popup.

Mozilla no puede firmar extensiones de Chrome, así que Bruma acepta extensiones
sin firma, siempre con el cartel de confirmación de Firefox. Para aceptar **solo
extensiones firmadas por Mozilla**, marca esa casilla en el botón «Bruma» (las
extensiones de Chrome se desactivan, no se borran) o usa
`bruma.extensionesDeChrome = false` para fijarlo en todo el sistema.

<details>
<summary><b>Seguridad del conversor de extensiones</b></summary>

- **Nada se instala sin tu confirmación.** Lo que aparezca suelto en el perfil,
  en `~/.mozilla/extensions` o en carpetas del sistema queda desactivado hasta
  que lo apruebes, y esa regla está bloqueada.
- **Pedidos de instalación**: solo se aceptan desde las páginas de las dos
  tiendas (marco principal) y solo después de un clic real tuyo; un script de la
  página no puede hacer clic por ti.
- **Host nativo**: solo la extensión de Bruma puede hablarle; valida los ID y
  las rutas, y nunca usa una terminal.
- **Descargas**: HTTPS a los servidores de cada tienda, el hash que anuncia la
  tienda, la firma CRX3 del autor y que el ID firmado sea el pedido. Rechaza
  archivos enormes, bombas zip y rutas que se salen de la extensión (`..`, rutas
  absolutas).
- **Permisos de archivos**: el perfil y las extensiones convertidas quedan en
  carpetas que solo tu usuario puede leer (700).
- **Lo que no cubre**: como en cualquier navegador, un programa que ya corre con
  tu usuario puede modificar tu perfil; con las firmas exigidas, Firefox pide la
  firma de Mozilla también en ese caso.

Para repetir las pruebas de seguridad del conversor (necesita internet), desde
la carpeta de Bruma:

```bash
python3 -I pruebas/seguridad.py
```

</details>

## Modo liviano

Para computadoras con poca memoria: marca *Modo liviano* en el botón «Bruma»; se
activa solo con menos de 4 GB de RAM. Usa menos procesos y caché, no guarda en
memoria las páginas anteriores y descarga las pestañas que no usas cuando falta
memoria. El aislamiento de sitios (Fission) sigue activo: es una protección de
seguridad importante.

Medido con un perfil ya usado (PSS de todos los procesos): unos 710–980 MB con
dos pestañas livianas y cerca de 1,6 GB con seis pesadas (YouTube, Reddit,
sitios de noticias). Con 2 GB de RAM funciona bien con pocas pestañas (mejor con
un escritorio liviano como XFCE o LXQt); con 1 GB ningún navegador moderno anda
cómodo.

## Actualizaciones

- **Versiones nuevas de Bruma**: una vez por día Bruma busca una versión nueva
  en GitHub. Si la hay, una barra ofrece **Instalar y reiniciar** o **Ahora
  no**. Instalar pide la contraseña de administrador; el ayudante
  `bruma-actualizar` baja la versión, comprueba que esté **firmada con la clave
  de Bruma** (la clave pública sale del paquete instalado, no de la descarga),
  lleva la carpeta de Bruma a esa versión y actualiza el sistema. Después,
  **Reiniciar ahora** vuelve a abrir Bruma en la versión nueva con tus
  pestañas. Botón «Bruma» → *Buscar actualizaciones* busca en el momento.
- **Después de tus propias actualizaciones** (por ejemplo `nix flake update`
  para los parches de seguridad de Firefox), Bruma nota la versión nueva y
  ofrece reiniciar.
- **Requisitos**: la carpeta de Bruma es un clon de git (como en
  [Instalación](#instalación)) sin cambios locales. El comando por defecto es
  `nixos-rebuild switch`, que en sistemas con flakes usa `/etc/nixos`.
- **Opciones**:

  ```nix
  bruma.actualizador.buscar = false;                       # no conectarse a GitHub
  bruma.actualizador.repositorio = "ebalia-real/bruma";    # de dónde salen las versiones
  bruma.actualizador.carpeta = "/etc/nixos/bruma";         # el clon de git que se actualiza
  bruma.actualizador.comando = "/run/current-system/sw/bin/nixos-rebuild switch";
  ```

- **Seguridad**: solo se instalan etiquetas `vAAAA.MM.DD` firmadas con una clave
  de `firmas/claves-permitidas`, y la etiqueta tiene que coincidir con su
  archivo `VERSION`. Git corre con el dueño de la carpeta, nunca como root, y sin
  ganchos, así nada de lo que haya en el repositorio corre con permisos de
  administrador; como root solo corre la actualización del sistema. Si la
  carpeta tiene cambios locales, no se toca nada. Registro:
  `/var/log/bruma-actualizar.log`.

<details>
<summary><b>Publicar una versión (para quien mantiene Bruma)</b></summary>

1. Sube el número de `VERSION` (por ejemplo `2026.10.22`, o `2026.10.22.1` para
   una segunda versión ese día) y haz commit.
2. Crea una etiqueta firmada con la clave de versiones (la de
   `firmas/claves-permitidas`):

   ```bash
   git -c gpg.format=ssh -c user.signingkey=~/.ssh/bruma-firma.pub tag -s v2026.10.22 -m "Bruma 2026.10.22"
   ```

3. Sube el commit y la etiqueta: `git push origin main v2026.10.22`.

</details>

## Lo que Bruma no puede ocultar

Ningún navegador es totalmente privado. Bruma protege lo que pasa dentro del
navegador, pero:

- **Tu IP se ve** en las ventanas normales (y con ella tu proveedor y tu ciudad
  aproximada). Para ocultarla: la ventana con Tor, una VPN o Tor Browser.
- **Cuentas**: si inicias sesión en un sitio, ese sitio sabe que eres tú.
- **Extensiones**: cada extensión cambia tu huella, y una con acceso a todos los
  sitios puede leer las páginas que abres.
- **Conexiones automáticas**: los servicios de Mozilla que LibreWolf mantiene
  (listas de bloqueo, revocación de certificados, actualizaciones de
  complementos); una vez al día, GitHub para buscar una versión nueva de Bruma
  (ve tu IP; `bruma.actualizador.buscar = false` lo apaga); y una vez al día,
  la tienda de Chrome o de Edge para buscar versiones nuevas de tus extensiones
  de Chrome (ven tu IP y los ID de esas extensiones; con las firmas exigidas esa
  búsqueda no se hace).
- **Huella**: coincide con la de Mullvad Browser salvo la versión de Firefox y
  dos detalles que dependen de ella; alcanza para que un sitio sepa que no usas
  Mullvad ni Tor Browser, y los usuarios de Bruma son pocos.
- **En tu computadora** queda el historial (las cookies y la caché se borran al
  cerrar), salvo con *Siempre privado*. Las ventanas privadas y la ventana con
  Tor no guardan nada.

## Ajustes finos

En `about:config`:

| Para… | Cambia |
|---|---|
| Ver las páginas en tu idioma (te hace más fácil de distinguir) | `privacy.spoof_english` → `1` |
| Usar WebGL sin que pregunte | `librewolf.webgl.prompt` → `false` |
| Usar llaves de acceso (*passkeys*) | `security.webauth.webauthn` → `true` |
| Arreglar llamadas que no conectan | `media.peerconnection.ice.relay_only` → `false` |
| Usar aplicaciones web sin conexión (*service workers*) | `dom.serviceWorkers.enabled` → `true` |
| Arreglar inicios de sesión entre sitios | `privacy.firstparty.isolate` → `false` |

Los ajustes personales permanentes van en un archivo `user.js` en
`~/.local/share/bruma/gecko/`.

<details>
<summary><b>Marca e idioma</b></summary>

Bruma usa el motor de LibreWolf, pero LibreWolf no aparece dentro del
navegador: el logo, los íconos, la página de nueva pestaña, *Acerca de Bruma*,
los ajustes, el menú de ayuda y `about:support` dicen Bruma. Se hace al
compilar, reemplazando archivos dentro de los `omni.ja` de LibreWolf
(`marca/textos.py` y `marca/codigo.py`). Tampoco contacta los servidores de
LibreWolf: uBlock Origin baja su índice de listas de sus propias fuentes.

Los paquetes de idioma de Mozilla dicen «Firefox», así que el servicio de
sistema `bruma-idioma` baja el de tu idioma y versión, le pone la marca Bruma y
lo deja en `/var/lib/bruma/idioma` (solo root puede modificarlo); una política
del navegador lo instala desde ahí. Sin internet, Bruma abre en inglés y el
servicio reintenta cada 10 minutos.

Si una actualización de LibreWolf cambia algo de lo que esto usa, la compilación
muestra un aviso (`AVISO`) sin cortar la actualización del sistema.

</details>

<details>
<summary><b>Dónde está cada cosa</b></summary>

| Qué | Dónde |
|---|---|
| Perfil (historial, extensiones, ajustes) | `~/.local/share/bruma/gecko/` |
| Extensiones de Chrome y Edge convertidas | `~/.local/share/bruma/extensiones-chrome/` |
| Perfil de la ventana con Tor (siempre privado) | `~/.local/share/bruma/tor/` |
| Datos y registro de Tor | `~/.local/share/bruma/tor-red/` |
| Sockets de Tor (SOCKS y control) | `/run/user/<uid>/bruma-tor/` (solo tu usuario) |

| Archivo | Qué hace |
|---|---|
| `modulo.nix` | Módulo NixOS: instala Bruma, el servicio del idioma, el temporizador de actualización de extensiones y el refresco del menú de GNOME. |
| `default.nix` | El paquete: LibreWolf + ajustes, fuentes de Mullvad, la extensión y el lanzador de Bruma. |
| `gecko/ajustes.cfg` | Los ajustes de Mullvad Browser que se suman a los de LibreWolf. |
| `lanzador.sh` | El comando `bruma` (con la ventana con Tor). |
| `extension/` | La extensión de Bruma: los botones de las tiendas y la instalación de `.crx`. |
| `host/` | Host nativo y conversor de extensiones de Chrome, capa de compatibilidad, cambio de país de Tor, y el actualizador (`actualizar.sh` y su acción de polkit). |
| `VERSION`, `firmas/` | La versión de Bruma y las claves públicas que pueden firmar versiones. |
| `marca/` | La marca, el botón «Bruma» (`ajustes-bruma.sys.mjs`) y los scripts que los aplican. |
| `iconos/` | El logo: un globo (la web) que se desarma en jirones de niebla. |
| `pruebas/seguridad.py` | Pruebas de seguridad del conversor de extensiones. |

</details>

## Preguntas frecuentes

**¿Por qué no usar Mullvad Browser directamente?** Su protección depende de que
todos sus usuarios sean idénticos, y cualquier extensión la rompe. Además, en
nixpkgs suele ir atrasado en parches de seguridad.

**¿Por qué no un motor Chromium?** No existe un motor que mezcle Gecko y
Chromium. Bruma usa un solo motor (Gecko) y adapta las extensiones de Chrome, que
casi siempre funcionan.

**¿Es totalmente anónimo?** Ningún navegador lo es. Mira
[Lo que Bruma no puede ocultar](#lo-que-bruma-no-puede-ocultar).

## Licencia

Bruma se publica bajo la [Mozilla Public License 2.0](LICENSE) (MPL-2.0), la
misma familia de licencias que Firefox y LibreWolf.
