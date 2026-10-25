"""Velbrum para Windows, macOS y Linux sin Nix: abre el navegador.

Hace lo mismo que lanzador.sh (el de NixOS) en los paquetes de portable/: la
carpeta de datos, los interruptores de firmas y bordes, el host de mensajería
nativa de las tiendas de Chrome y Edge, la ventana privada con Tor, los .crx y
la actualización diaria de las extensiones de Chrome. PyInstaller lo convierte
en un programa (velbrum, velbrum.exe) junto con extensiones_chrome.py.

Dónde quedan los datos (perfil, extensiones convertidas, Tor):
- versión portable (hay un archivo «portable» junto al programa, o junto a
  Velbrum.app en macOS): la carpeta «datos» de al lado, para llevarla en un
  pendrive;
- instalada: ~/.local/share/velbrum (Linux), %LOCALAPPDATA%\\Velbrum (Windows)
  o ~/Library/Application Support/Velbrum (macOS).
"""
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time

# En Windows el lanzador no tiene consola (PyInstaller --noconsole): sin esto,
# cualquier mensaje lo haría fallar.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

VERSION = "@versionVelbrum@"
REPO = "ebalia-real/velbrum"
WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"
LINUX = not WINDOWS and not MACOS
HOST = "velbrum.extensiones"
PAISES_TOR = "de nl us se at fr no ch ro fi is dk lu".split()
UN_DIA = 24 * 3600

AYUDA = """Uso: velbrum [opciones] [URL o archivo.crx...]

  --privada                 ventana privada
  --tor                     ventana privada con Tor (su propio perfil y su propio
                            Tor, que corre solo mientras esa ventana está abierta)
  --tor-pais PAIS           país de salida de la ventana con Tor: auto o
                            de, nl, us, se, at, fr, no, ch, ro, fi, is, dk, lu
  --nueva-ventana           abrir en una ventana nueva
  --extension-chrome X      instala una extensión de Chrome o Edge: su ID, la URL
                            de la tienda o un archivo .crx
  --actualizar-extensiones  busca versiones nuevas de las extensiones de Chrome
  --exigir-firmas           aceptar solo extensiones firmadas por Mozilla
  --permitir-sin-firma      volver a aceptar extensiones de Chrome
  --estado-firmas           muestra cuál de los dos está activo
  --sin-bordes / --con-bordes / --estado-bordes
                            bordes de privacidad (tamaño de ventana redondeado)
  --reiniciar               espera a que se cierre Velbrum y lo vuelve a abrir
  --ayuda                   esta ayuda

Cualquier otra opción se le pasa tal cual al navegador."""


# ── Rutas ──────────────────────────────────────────────────────────────────
def _programa():
    """La carpeta del lanzador."""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent


PROGRAMA = _programa()
LANZADOR = pathlib.Path(sys.executable).resolve() if getattr(sys, "frozen", False) else pathlib.Path(__file__).resolve()
if MACOS:
    # Velbrum.app/Contents/Resources/velbrum/lanzador/velbrum (lo abre el
    # script Contents/MacOS/velbrum): el navegador está en Contents/MacOS y lo
    # de Velbrum en Contents/Resources/velbrum.
    CONTENIDO = next((p for p in PROGRAMA.parents if p.name == "Contents"), PROGRAMA.parent)
    RECURSOS = CONTENIDO / "Resources" / "velbrum"
    NAVEGADOR = CONTENIDO / "MacOS" / "librewolf"
    RAIZ = CONTENIDO.parent.parent  # la carpeta que contiene Velbrum.app
    LANZADOR = CONTENIDO / "MacOS" / "velbrum"
else:
    RECURSOS = PROGRAMA
    NAVEGADOR = PROGRAMA / "navegador" / ("librewolf.exe" if WINDOWS else "librewolf")
    RAIZ = PROGRAMA
HOST_PROGRAMA = RECURSOS / "host" / ("velbrum-host.exe" if WINDOWS else "velbrum-host")
TOR = RECURSOS / "tor" / "tor" / ("tor.exe" if WINDOWS else "tor")
GEOIP = RECURSOS / "tor" / "data"
# Dentro de la carpeta del navegador: los procesos de las páginas (con sandbox)
# solo pueden leer fuentes de ahí y del sistema.
FUENTES = NAVEGADOR.parent / "fuentes"


def carpeta_datos():
    if (RAIZ / "portable").exists():
        return RAIZ / "datos"
    if WINDOWS:
        return pathlib.Path(os.environ.get("LOCALAPPDATA") or pathlib.Path.home() / "AppData" / "Local") / "Velbrum"
    if MACOS:
        return pathlib.Path.home() / "Library" / "Application Support" / "Velbrum"
    base = os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local" / "share"
    return pathlib.Path(base) / "velbrum"


DATOS = carpeta_datos()
PERFIL = DATOS / "gecko"
PERFIL_TOR = DATOS / "tor"
RED_TOR = DATOS / "tor-red"
MARCA_FIRMAS = DATOS / "firmas-obligatorias"
MARCA_BORDES = DATOS / "sin-bordes"


def privada(carpeta):
    carpeta.mkdir(parents=True, exist_ok=True)
    if not WINDOWS:
        carpeta.chmod(0o700)
    return carpeta


def avisar(texto):
    print(f"velbrum: {texto}", file=sys.stderr)
    try:
        if LINUX and shutil.which("notify-send"):
            subprocess.run(["notify-send", "--app-name=Velbrum", "--icon=velbrum", "Velbrum", texto], timeout=5, check=False)
        elif MACOS:
            texto_as = texto.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.run(["osascript", "-e", f'display notification "{texto_as}" with title "Velbrum"'], timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


# ── Conversor de extensiones de Chrome (el mismo que en NixOS) ─────────────
def conversor():
    import extensiones_chrome as ec

    ec.COMPAT = str(RECURSOS / "host" / "compat")
    ec.EQUIVALENTES = str(RECURSOS / "host" / "equivalentes.json")
    return ec


def convertir(origen):
    if MARCA_FIRMAS.exists():
        avisar("Velbrum está aceptando solo extensiones firmadas por Mozilla. Para instalar extensiones de Chrome: velbrum --permitir-sin-firma")
        return None
    ec = conversor()
    try:
        ruta, info = ec.preparar(origen)
    except ec.ErrorExtension as error:
        avisar(f"no se pudo instalar la extensión: {error}")
        return None
    print(f"{info['nombre']} {info['version']} convertida para Velbrum.", file=sys.stderr)
    for aviso in info["avisos"]:
        print(f"  ⚠ {aviso}", file=sys.stderr)
    return pathlib.Path(ruta).as_uri()


def actualizar_extensiones():
    if MARCA_FIRMAS.exists():
        return 0
    ec = conversor()
    cambios, pendientes = ec.actualizar()
    for cambio in cambios:
        print(f"Actualizada: {cambio}")
    for nombre, id_chrome, nuevos in pendientes:
        avisar(f"{nombre} necesita tu permiso para actualizarse ({', '.join(nuevos)}): velbrum --extension-chrome {id_chrome}")
    (DATOS / "extensiones-revisadas").write_text(str(int(time.time())))
    return 0


def actualizar_extensiones_si_toca():
    """Una vez por día, en segundo plano (en NixOS lo hace un temporizador)."""
    marca = DATOS / "extensiones-revisadas"
    try:
        if time.time() - int(marca.read_text().strip() or 0) < UN_DIA:
            return
    except (OSError, ValueError):
        pass
    marca.write_text(str(int(time.time())))
    if MARCA_FIRMAS.exists() or not (PERFIL / "extensions").is_dir():
        return
    comando = [str(LANZADOR), "--actualizar-extensiones"] if getattr(sys, "frozen", False) else [sys.executable, str(LANZADOR), "--actualizar-extensiones"]
    opciones = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "env": entorno()}
    if WINDOWS:
        opciones["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        opciones["start_new_session"] = True
    try:
        subprocess.Popen(comando, **opciones)
    except OSError:
        pass


# ── Host de mensajería nativa ──────────────────────────────────────────────
def registrar_host():
    manifiesto = json.dumps(
        {
            "name": HOST,
            "description": "Velbrum: instalar extensiones de Chrome",
            "path": str(HOST_PROGRAMA),
            "type": "stdio",
            "allowed_extensions": ["chrome@velbrum"],
        },
        indent=1,
    )
    if WINDOWS:
        import winreg

        ruta = DATOS / f"{HOST}.json"
        ruta.write_text(manifiesto, encoding="utf-8")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Mozilla\NativeMessagingHosts\{HOST}") as clave:
            winreg.SetValueEx(clave, "", 0, winreg.REG_SZ, str(ruta))
        return
    if MACOS:
        soporte = pathlib.Path.home() / "Library" / "Application Support"
        carpetas = [soporte / "LibreWolf" / "NativeMessagingHosts", soporte / "Mozilla" / "NativeMessagingHosts"]
    else:
        carpetas = [pathlib.Path.home() / ".librewolf" / "native-messaging-hosts"]
    for carpeta in carpetas:
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / f"{HOST}.json"
        try:
            if ruta.is_symlink() or not ruta.exists() or ruta.read_text(encoding="utf-8") != manifiesto:
                ruta.unlink(missing_ok=True)
                ruta.write_text(manifiesto, encoding="utf-8")
        except OSError as error:
            print(f"velbrum: no pude registrar el host en {carpeta}: {error}", file=sys.stderr)


# ── Extensión de las tiendas ───────────────────────────────────────────────
def actualizar_extension_propia():
    """La extensión de Velbrum se instala la primera vez como complemento de
    distribución; si una versión nueva de Velbrum trae otra, se reemplaza la
    copia del perfil (Gecko la toma al arrancar, como las de Chrome)."""
    if MACOS:
        nueva = CONTENIDO / "Resources" / "distribution" / "extensions" / "chrome@velbrum.xpi"
    else:
        nueva = NAVEGADOR.parent / "distribution" / "extensions" / "chrome@velbrum.xpi"
    instalada = PERFIL / "extensions" / "chrome@velbrum.xpi"
    try:
        if instalada.exists() and nueva.exists() and instalada.read_bytes() != nueva.read_bytes():
            if not perfil_abierto(PERFIL):
                shutil.copyfile(nueva, instalada)
    except OSError as error:
        print(f"velbrum: no pude actualizar la extensión de Velbrum: {error}", file=sys.stderr)


# ── Preferencias e interruptores ───────────────────────────────────────────
def escribir_interruptores():
    """Líneas marcadas de user.js que se reescriben en cada arranque (ver
    lanzador.sh): van siempre, con true o false."""
    userjs = PERFIL / "user.js"
    lineas = []
    if userjs.exists():
        lineas = [
            l for l in userjs.read_text(encoding="utf-8").splitlines()
            if not l.endswith(("// velbrum: interruptor de firmas", "// velbrum: bordes"))
        ]
    exigir = "true" if MARCA_FIRMAS.exists() else "false"
    bordes = "false" if MARCA_BORDES.exists() else "true"
    lineas.append(f'user_pref("xpinstall.signatures.required", {exigir}); // velbrum: interruptor de firmas')
    lineas.append(f'user_pref("privacy.resistFingerprinting.letterboxing", {bordes}); // velbrum: bordes')
    userjs.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def configuracion_fuentes():
    """Linux: solo las fuentes de Mullvad Browser (las mismas para todos)."""
    if not LINUX or not (FUENTES / "fonts.conf").exists():
        return None
    return str(FUENTES / "fonts.conf")


def entorno():
    env = dict(os.environ)
    for variable in ("XRE_PROFILE_PATH", "XRE_PROFILE_LOCAL_PATH", "XRE_PROFILE_NAME",
                     "XRE_RESTARTED_BY_PROFILE_MANAGER", "MOZ_LAUNCHED_CHILD", "PYINSTALLER_RESET_ENVIRONMENT"):
        env.pop(variable, None)
    # PyInstaller le pone al lanzador su propia carpeta de bibliotecas y
    # variables suyas: el navegador (y lo que abra, como el host) arranca con
    # el entorno de la sesión.
    for variable in [v for v in env if v.startswith(("_PYI_", "_MEI"))]:
        del env[variable]
    for variable in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        if f"{variable}_ORIG" in env:
            env[variable] = env.pop(f"{variable}_ORIG")
        else:
            env.pop(variable, None)
    env.update(
        VELBRUM_DATOS=str(DATOS),
        VELBRUM_LANZADOR=str(LANZADOR),
        VELBRUM_VERSION=VERSION,
        VELBRUM_REPO_ACTUALIZACIONES=REPO,
        VELBRUM_ACTUALIZADOR="",
    )
    if (DATOS / "siempre-privado").exists():
        env["VELBRUM_SIEMPRE_PRIVADO"] = "1"
    else:
        env.pop("VELBRUM_SIEMPRE_PRIVADO", None)
    fuentes = configuracion_fuentes()
    if fuentes:
        env["FONTCONFIG_FILE"] = fuentes
    return env


# ── ¿Hay una instancia abierta con este perfil? ────────────────────────────
def perfil_abierto(perfil):
    if WINDOWS:
        candado = perfil / "parent.lock"
        if not candado.exists():
            return False
        try:
            with open(candado, "a"):
                return False  # nadie lo tiene tomado
        except PermissionError:
            return True
        except OSError:
            return False
    import fcntl

    candado = perfil / ".parentlock"
    if not candado.exists():
        return False
    try:
        with open(candado, "a") as f:
            fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.lockf(f, fcntl.LOCK_UN)
            return False
    except OSError:
        return True


# ── Ventana privada con Tor ────────────────────────────────────────────────
def proceso_vivo(pid):
    if pid <= 0:
        return False
    if WINDOWS:
        import ctypes

        manejador = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not manejador:
            return False
        codigo = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(manejador, ctypes.byref(codigo))
        ctypes.windll.kernel32.CloseHandle(manejador)
        return codigo.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def carpeta_sockets():
    """Carpeta corta y privada para los sockets de Tor (no admiten rutas de más
    de ~100 caracteres). En Windows Tor usa puertos locales."""
    if WINDOWS:
        return None
    base = os.environ.get("XDG_RUNTIME_DIR") if LINUX else None
    carpeta = pathlib.Path(base) / "velbrum-tor" if base else pathlib.Path(tempfile.gettempdir()) / f"velbrum-tor-{os.getuid()}"
    if len(str(carpeta / "control")) > 100:
        carpeta = pathlib.Path("/tmp") / f"velbrum-tor-{os.getuid()}"
    privada(carpeta)
    if carpeta.stat().st_uid != os.getuid():
        raise SystemExit(f"velbrum: {carpeta} no es tuya")
    return carpeta


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def estado_tor():
    """{pid, socks, control} del Tor de Velbrum si está corriendo, o None."""
    try:
        estado = json.loads((RED_TOR / "estado.json").read_text())
    except (OSError, ValueError):
        return None
    try:
        pid = int((RED_TOR / "tor.pid").read_text().strip())
    except (OSError, ValueError):
        return None
    return estado if proceso_vivo(pid) and estado.get("pid") == pid else None


def hablar_con_tor(control, ordenes):
    """Manda órdenes al puerto de control (con la cookie que solo tu usuario lee)."""
    cookie = (RED_TOR / "datos" / "control_auth_cookie").read_bytes().hex()
    if control.startswith("unix:"):
        s = socket.socket(socket.AF_UNIX)
        s.settimeout(15)
        s.connect(control[5:])
    else:
        anfitrion, puerto = control.rsplit(":", 1)
        s = socket.create_connection((anfitrion, int(puerto)), timeout=15)
    with s:
        lector = s.makefile("rb")
        for orden in [f"AUTHENTICATE {cookie}", *ordenes, "QUIT"]:
            s.sendall(orden.encode() + b"\r\n")
            respuesta = lector.readline().decode(errors="replace").strip()
            if not respuesta.startswith("250"):
                raise SystemExit(f"velbrum: Tor respondió: {respuesta}")


def cambiar_pais(pais):
    pais = (pais or "").lower()
    if pais != "auto" and pais not in PAISES_TOR:
        print(f"velbrum: país no disponible: «{pais}» (opciones: auto {' '.join(PAISES_TOR)})", file=sys.stderr)
        return 1
    privada(DATOS)
    if pais == "auto":
        (DATOS / "tor-pais").unlink(missing_ok=True)
    else:
        (DATOS / "tor-pais").write_text(pais + "\n")
    estado = estado_tor()
    if estado:
        ordenes = ["RESETCONF ExitNodes StrictNodes"] if pais == "auto" else [f"SETCONF ExitNodes={{{pais}}} StrictNodes=1"]
        hablar_con_tor(estado["control"], ordenes + ["SIGNAL NEWNYM"])
    return 0


def iniciar_tor():
    privada(RED_TOR)
    sockets = carpeta_sockets()
    vacio = RED_TOR / "torrc-vacio"
    vacio.write_text("")
    (RED_TOR / "tor.log").unlink(missing_ok=True)
    if sockets:
        for nombre in ("socks", "control"):
            (sockets / nombre).unlink(missing_ok=True)
        socks, control = f"unix:{sockets / 'socks'}", f"unix:{sockets / 'control'}"
        socks_arg, control_arg = f"{socks} IsolateSOCKSAuth", control
    else:
        p_socks, p_control = puerto_libre(), puerto_libre()
        socks, control = f"127.0.0.1:{p_socks}", f"127.0.0.1:{p_control}"
        socks_arg, control_arg = f"{socks} IsolateSOCKSAuth", control
    pais = ""
    try:
        pais = (DATOS / "tor-pais").read_text().strip()
    except OSError:
        pass
    pais_args = ["--ExitNodes", f"{{{pais}}}", "--StrictNodes", "1"] if pais in PAISES_TOR else []
    comando = [
        str(TOR), "--ignore-missing-torrc", "-f", str(vacio), "--defaults-torrc", str(vacio),
        "--SocksPort", socks_arg, "--ControlPort", control_arg, "--CookieAuthentication", "1", *pais_args,
        "--GeoIPFile", str(GEOIP / "geoip"), "--GeoIPv6File", str(GEOIP / "geoip6"),
        "--DataDirectory", str(RED_TOR / "datos"), "--ClientOnly", "1", "--AvoidDiskWrites", "1",
        "--Log", f"notice file {RED_TOR / 'tor.log'}", "--PidFile", str(RED_TOR / "tor.pid"),
    ]
    # Tor trae sus bibliotecas (libevent, OpenSSL) en su misma carpeta.
    env = entorno()
    if LINUX:
        env["LD_LIBRARY_PATH"] = str(TOR.parent)
    elif MACOS:
        env["DYLD_LIBRARY_PATH"] = str(TOR.parent)
    opciones = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "env": env}
    if WINDOWS:
        opciones["creationflags"] = subprocess.CREATE_NO_WINDOW
    proceso = subprocess.Popen(comando, **opciones)
    (RED_TOR / "estado.json").write_text(json.dumps({"pid": proceso.pid, "socks": socks, "control": control}))
    return proceso


def esperar_tor(proceso):
    """Hasta 90 segundos para que Tor termine de conectarse."""
    for _ in range(180):
        try:
            if "Bootstrapped 100%" in (RED_TOR / "tor.log").read_text(errors="replace"):
                return True
        except OSError:
            pass
        if proceso is not None and proceso.poll() is not None:
            return False
        if proceso is None and not estado_tor():
            return False
        time.sleep(0.5)
    return False


def abrir_con_tor(urls, extra):
    if not TOR.exists():
        avisar("Este paquete de Velbrum no trae Tor.")
        return 1
    privada(PERFIL_TOR)
    proceso = None
    estado = estado_tor()
    if not estado:
        proceso = iniciar_tor()
        avisar("Conectando a Tor… (la primera vez puede tardar un minuto)")
        estado = json.loads((RED_TOR / "estado.json").read_text())
    if not esperar_tor(proceso):
        avisar(f"No se pudo iniciar Tor (detalles en {RED_TOR / 'tor.log'}).")
        if proceso:
            proceso.terminate()
        return 1
    if not urls:
        urls = ["about:newtab"] if perfil_abierto(PERFIL_TOR) else ["https://check.torproject.org/"]
    env = entorno()
    env["VELBRUM_TOR"] = "1"
    if estado["socks"].startswith("unix:"):
        env["VELBRUM_TOR_SOCKET"] = estado["socks"][5:]
    else:
        env["VELBRUM_TOR_PUERTO"] = estado["socks"].rsplit(":", 1)[1]
    clase = ["--name", "velbrum-tor", "--class", "velbrum-tor"] if LINUX else []
    codigo = subprocess.call([str(NAVEGADOR), *clase, "--profile", str(PERFIL_TOR), *extra, *urls], env=env)
    # El Tor que arrancó este lanzador se apaga cuando no queda ninguna ventana
    # con Tor (si esta se sumó a una instancia que ya estaba, se la espera).
    if proceso:
        time.sleep(2)
        while perfil_abierto(PERFIL_TOR):
            time.sleep(3)
        proceso.terminate()
        try:
            proceso.wait(10)
        except subprocess.TimeoutExpired:
            proceso.kill()
    return codigo


# ── Principal ──────────────────────────────────────────────────────────────
def main(argv):
    privada(DATOS)
    privada(PERFIL)
    abrir_privada = nueva = tor = reiniciar = False
    extra, urls = [], []
    i = 0
    while i < len(argv):
        a = argv[i]
        siguiente = argv[i + 1] if i + 1 < len(argv) else ""
        if a == "--privada":
            abrir_privada = True
        elif a == "--tor":
            tor = True
        elif a == "--reiniciar":
            reiniciar = True
        elif a == "--nueva-ventana":
            nueva = True
        elif a == "--tor-pais":
            return cambiar_pais(siguiente)
        elif a in ("--ayuda", "-h", "--help"):
            print(AYUDA)
            return 0
        elif a == "--extension-chrome":
            xpi = convertir(siguiente)
            if not xpi:
                return 1
            urls.append(xpi)
            i += 1
        elif a == "--actualizar-extensiones":
            return actualizar_extensiones()
        elif a == "--exigir-firmas":
            MARCA_FIRMAS.touch()
            avisar("Desde la próxima vez que abras Velbrum, solo acepta extensiones firmadas por Mozilla.")
            return 0
        elif a == "--permitir-sin-firma":
            MARCA_FIRMAS.unlink(missing_ok=True)
            avisar("Desde la próxima vez que abras Velbrum, vuelve a aceptar extensiones de Chrome (con el cartel de confirmación).")
            return 0
        elif a == "--estado-firmas":
            print("Solo extensiones firmadas por Mozilla." if MARCA_FIRMAS.exists()
                  else "Se aceptan extensiones de Chrome (sin firma, con el cartel de confirmación).")
            return 0
        elif a == "--sin-bordes":
            MARCA_BORDES.touch()
            return 0
        elif a == "--con-bordes":
            MARCA_BORDES.unlink(missing_ok=True)
            return 0
        elif a == "--estado-bordes":
            print("Sin bordes." if MARCA_BORDES.exists() else "Con bordes de privacidad.")
            return 0
        elif a == "--":
            urls += argv[i + 1:]
            break
        elif a.startswith("-"):
            extra.append(a)
        else:
            urls.append(a)
        i += 1

    # Archivos .crx abiertos con Velbrum: se adaptan y se abre su instalación.
    urls = [convertir(u) if u.lower().endswith(".crx") else u for u in urls]
    urls = [u for u in urls if u]

    escribir_interruptores()
    actualizar_extension_propia()
    try:
        registrar_host()
    except OSError as error:
        print(f"velbrum: no pude registrar el host de extensiones: {error}", file=sys.stderr)

    if reiniciar:
        for _ in range(240):
            if not perfil_abierto(PERFIL):
                break
            time.sleep(0.25)

    if tor:
        return abrir_con_tor(urls, extra)

    actualizar_extensiones_si_toca()
    args = (["--name", "velbrum", "--class", "velbrum"] if LINUX else []) + ["--profile", str(PERFIL)]
    if abrir_privada:
        args.append("--private-window")
        if urls:
            args.append(urls.pop(0))
    elif nueva:
        args.append("--new-window")
    comando = [str(NAVEGADOR), *args, *extra, *urls]
    if WINDOWS:
        subprocess.Popen(comando, env=entorno(), close_fds=True)
        return 0
    os.execve(str(NAVEGADOR), comando, entorno())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
