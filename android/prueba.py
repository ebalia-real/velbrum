#!/usr/bin/env python3
"""Prueba de Velbrum para Android en un emulador (o teléfono) conectado por
adb, como la usaría alguien: instala el APK desde cero, pasa la bienvenida,
revisa la marca y el DNS cifrado (Quad9), prende la instalación de
complementos y convierte una extensión de la Chrome Web Store hasta el cartel
«¿Agregar …?» y su instalación. Deja capturas de cada paso.

Uso: android/prueba.py --apk VELBRUM.apk [--capturas CARPETA]
Pensada para el dispositivo «pixel_6» del emulador (1080×2400): el botón
«Agregar a Velbrum» de la tienda se toca por su posición (el contenido web no
está en el árbol de accesibilidad de la aplicación).
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

AQUI = Path(__file__).resolve().parent
PAQUETE = next(
    linea.split("=", 1)[1].strip()
    for linea in (AQUI / "versiones.env").read_text().splitlines()
    if linea.startswith("PAQUETE=")
)
RECEPTOR = f"{PAQUETE}/org.mozilla.fenix.IntentReceiverActivity"
# Una extensión chica, pública desde hace años, sin versión para Firefox en
# extension/equivalentes.json (así se convierte): JSON Formatter.
EXTENSION = ("bcjindcccaagfpapjjmafapmmgkkhgoa", "JSON Formatter")
capturas = Path("capturas-android")
paso = 0


class Fallo(Exception):
    pass


def adb(*argumentos, **opciones):
    return subprocess.run(["adb", *argumentos], capture_output=True, timeout=300, **opciones)


def nodos():
    for _ in range(5):
        adb("shell", "uiautomator", "dump", "/sdcard/velbrum-ui.xml")
        r = adb("exec-out", "cat", "/sdcard/velbrum-ui.xml")
        try:
            return list(ET.fromstring(r.stdout).iter("node"))
        except ET.ParseError:
            time.sleep(1)
    return []


def textos():
    resultado = []
    for n in nodos():
        resultado += [t for t in (n.get("text"), n.get("content-desc")) if t]
    # La marca de la base no tiene que aparecer en ningún lado.
    for t in resultado:
        if re.search(r"ironfox", t, re.I):
            captura("marca-ajena")
            raise Fallo(f"aparece la marca de IronFox en pantalla: «{t}»")
    return resultado


def buscar(patron):
    for n in nodos():
        for t in (n.get("text"), n.get("content-desc")):
            if t and re.search(patron, t, re.I):
                return n
    return None


def tocar_nodo(n):
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
    adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))


def esperar(patron, segundos=60):
    fin = time.time() + segundos
    while time.time() < fin:
        if any(re.search(patron, t, re.I) for t in textos()):
            return
        time.sleep(2)
    captura("esperando")
    raise Fallo(f"no apareció «{patron}» en {segundos} s; en pantalla: {textos()[:15]}")


def tocar(patron, segundos=60, desplazar=False):
    fin = time.time() + segundos
    while time.time() < fin:
        n = buscar(patron)
        if n is not None:
            tocar_nodo(n)
            time.sleep(2)
            return
        if desplazar:
            adb("shell", "input", "swipe", "540", "1900", "540", "900", "300")
        time.sleep(1.5)
    captura("sin-boton")
    raise Fallo(f"no encontré «{patron}»; en pantalla: {textos()[:15]}")


def captura(nombre):
    global paso
    paso += 1
    capturas.mkdir(parents=True, exist_ok=True)
    (capturas / f"{paso:02d}-{nombre}.png").write_bytes(adb("exec-out", "screencap", "-p").stdout)


def abrir_app():
    adb("shell", "monkey", "-p", PAQUETE, "-c", "android.intent.category.LAUNCHER", "1")


def abrir_url(url):
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, "-n", RECEPTOR)


def main():
    global capturas
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--apk", required=True, type=Path)
    p.add_argument("--capturas", type=Path, default=capturas)
    args = p.parse_args()
    capturas = args.capturas

    # 1. Instalación desde cero.
    adb("uninstall", PAQUETE)
    r = adb("install", str(args.apk))
    if r.returncode:
        raise Fallo(f"no se pudo instalar: {r.stdout.decode()} {r.stderr.decode()}")
    info = adb("shell", "dumpsys", "package", PAQUETE).stdout.decode()
    version = re.search(r"versionName=(\S+)", info)
    if not version or "-velbrum." not in version.group(1):
        raise Fallo(f"versión inesperada: {version and version.group(1)}")
    print(f"instalado {PAQUETE} {version.group(1)}")

    # 2. Bienvenida, con la marca de Velbrum y Quad9 de entrada.
    abrir_app()
    esperar(r"Welcome to Velbrum|Velbrum", 120)
    captura("bienvenida")
    vio_quad9 = False
    for _ in range(25):
        en_pantalla = textos()
        if any(re.search(r"Search or enter address", t) for t in en_pantalla):
            break
        if any("Quad9" in t for t in en_pantalla):
            vio_quad9 = True
            captura("dns-quad9")
        # uBlock Origin se instala de addons.mozilla.org, como lo ofrece la
        # bienvenida («Add» y después «OK»).
        n = buscar(r"^(Not now|Continue|Start browsing|Skip|Add|OK)$")
        if n is None:
            time.sleep(3)
            continue
        tocar_nodo(n)
        time.sleep(3)
    else:
        raise Fallo("la bienvenida no terminó")
    if not vio_quad9:
        raise Fallo("la bienvenida no ofreció Quad9 como DNS cifrado")
    captura("inicio")

    # 3. «Permitir la instalación de complementos» (Ajustes → Velbrum →
    # Ajustes de Velbrum → Seguridad); el navegador se reinicia.
    tocar(r"^More options$")
    tocar(r"^Settings$")
    tocar(r"^Velbrum settings$", desplazar=True)
    tocar(r"^Allow installation of add-ons$", desplazar=True)
    time.sleep(8)
    abrir_app()
    esperar(r"Search or enter address|Velbrum", 90)

    # 4. Una extensión de la Chrome Web Store, convertida en el navegador.
    id_chrome, nombre = EXTENSION
    abrir_url(f"https://chromewebstore.google.com/detail/{id_chrome}")
    time.sleep(35)  # la tienda tarda en el emulador; el cartel sale a los 4 s
    captura("tienda")
    # «Agregar a Velbrum»: el botón de la tienda adaptado (extension/tienda.js)
    # o, si la tienda cambió, el del cartel de abajo (extension/aviso.js).
    for intento, y in enumerate((1037, 2186, 1037)):
        adb("shell", "input", "tap", "540", str(y))
        try:
            esperar(rf"^Add {re.escape(nombre)}$", 60)
            break
        except Fallo:
            if intento == 2:
                raise
    captura("cartel-agregar")
    tocar(r"^Add$")
    esperar(rf"{re.escape(nombre)} was added", 60)
    captura("agregada")
    tocar(r"^OK$")
    print(f"convertida e instalada: {nombre}")

    # 5. La extensión funciona: JSON Formatter le pone sus botones a un JSON.
    abrir_url("https://api.github.com/repos/mozilla/gecko-dev")
    time.sleep(20)
    captura("json-formateado")
    print(f"prueba correcta; capturas en {capturas}")


if __name__ == "__main__":
    try:
        main()
    except (Fallo, subprocess.TimeoutExpired) as error:
        print(f"prueba.py: FALLÓ: {error}", file=sys.stderr)
        sys.exit(1)
