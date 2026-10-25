#!@python@ -I
"""Host de mensajería nativa «velbrum.extensiones» (ver README.md).

La extensión propia de Velbrum le pide instalar extensiones de Chrome:
- {"accion": "instalar-chrome", "id"}: la descarga de la Chrome Web Store;
- {"accion": "instalar-edge", "id"}: la descarga de la tienda de Edge;
- {"accion": "instalar-crx", "ruta"}: usa un .crx ya descargado.
En esos casos la adapta a Gecko (extensiones_chrome.py). Con
{"accion": "instalar-firefox", "id", "tienda"} no la adapta: baja de
addons.mozilla.org su versión oficial para Firefox (solo las de
equivalentes.json). Después abre la instalación en Velbrum, que muestra su
cartel «¿Agregar …?».
"""
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

VELBRUM = "@velbrum@"
if VELBRUM.startswith("@"):
    # Paquetes sin Nix (portable/): el lanzador avisa dónde está.
    VELBRUM = os.environ.get("VELBRUM_LANZADOR", "")
MAXIMO = 1024 * 1024
sys.path.insert(0, "@libexec@")
if sys.platform == "win32":
    # Los mensajes son binarios: sin traducir saltos de línea.
    import msvcrt

    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

import extensiones_chrome  # noqa: E402


def leer_mensaje():
    cabecera = sys.stdin.buffer.read(4)
    if len(cabecera) != 4:
        return None
    (largo,) = struct.unpack("@I", cabecera)
    if largo > MAXIMO:
        return None
    return json.loads(sys.stdin.buffer.read(largo).decode("utf-8"))


def responder(datos):
    cuerpo = json.dumps(datos).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("@I", len(cuerpo)) + cuerpo)
    sys.stdout.buffer.flush()


def entorno_limpio():
    # El navegador le deja al host su LD_LIBRARY_PATH, GTK_PATH y variables
    # MOZ_*; el lanzador arranca con el entorno de la sesión. En los paquetes
    # sin Nix, host y lanzador son programas de PyInstaller: el lanzador tiene
    # que arrancar como si lo abriera la sesión, no como hijo del host.
    quitar = ("LD_LIBRARY_PATH", "LD_PRELOAD", "GTK_PATH", "GDK_BACKEND", "LD_LIBRARY_PATH_ORIG")
    entorno = {
        clave: valor
        for clave, valor in os.environ.items()
        if clave not in quitar and not clave.startswith(("MOZ_", "GNOME_DESKTOP_STARTUP", "_PYI_", "_MEI"))
    }
    if "LD_LIBRARY_PATH_ORIG" in os.environ:
        entorno["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH_ORIG"]
    if getattr(sys, "frozen", False):
        entorno["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return entorno


def abrir_instalacion(ruta_xpi):
    """Le pasa el XPI a Velbrum (la ventana abierta), que pide confirmación."""
    subprocess.Popen(
        [VELBRUM, "--", Path(ruta_xpi).as_uri()],
        env=entorno_limpio(),
        cwd=os.path.expanduser("~"),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def atender(mensaje):
    if not isinstance(mensaje, dict):
        return {"ok": False, "error": "pedido inválido"}
    accion = mensaje.get("accion")
    tienda = None
    if accion == "instalar-firefox":
        origen, tienda = mensaje.get("id"), mensaje.get("tienda")
        if not isinstance(origen, str) or not re.fullmatch(r"[a-p]{32}", origen) or tienda not in ("chrome", "edge"):
            return {"ok": False, "error": "pedido inválido"}
        try:
            ruta_xpi, info = extensiones_chrome.preparar_firefox(origen, tienda)
        except extensiones_chrome.ErrorExtension as error:
            return {"ok": False, "error": str(error)}
        abrir_instalacion(ruta_xpi)
        return {"ok": True, **info}
    if accion in ("instalar-chrome", "instalar-edge"):
        origen = mensaje.get("id")
        if not isinstance(origen, str) or not re.fullmatch(r"[a-p]{32}", origen):
            return {"ok": False, "error": "ID de extensión inválido"}
        tienda = accion.removeprefix("instalar-")
    elif accion == "instalar-crx":
        origen = mensaje.get("ruta")
        if (
            not isinstance(origen, str)
            or not os.path.isabs(origen)
            or not origen.lower().endswith(".crx")
            or not os.path.isfile(origen)
        ):
            return {"ok": False, "error": "no encontré el archivo .crx descargado"}
    else:
        return {"ok": False, "error": "pedido inválido"}
    try:
        ruta_xpi, info = extensiones_chrome.preparar(origen, tienda)
    except extensiones_chrome.ErrorExtension as error:
        return {"ok": False, "error": str(error)}
    abrir_instalacion(ruta_xpi)
    return {"ok": True, **info}


def main():
    try:
        mensaje = leer_mensaje()
    except (ValueError, UnicodeDecodeError):
        mensaje = None
    responder(atender(mensaje))


if __name__ == "__main__":
    main()
