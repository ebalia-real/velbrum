"""Compila con PyInstaller el lanzador (portable/velbrum.py) y el host de
mensajería nativa (host/host-extensiones.py), con el conversor de extensiones
de Chrome (host/extensiones_chrome.py) adentro, para el sistema en que corre.

Uso: python3 portable/compilar.py SALIDA
Deja SALIDA/dist/velbrum y SALIDA/dist/velbrum-host (carpetas de PyInstaller).
Necesita PyInstaller y certifi (pip install pyinstaller certifi) y, en Windows
y macOS, los íconos de portable/recursos.sh en SALIDA/recursos.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent.parent
# Si no se puede consultar la versión actual de Chrome, esta (la tiendas
# aceptan versiones recientes).
CHROME_POR_DEFECTO = "150.0.7843.0"


def version_chrome():
    """La versión estable de Chrome: el conversor la manda al pedir extensiones."""
    url = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions?pageSize=1"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)["versions"][0]["version"]
    except (OSError, ValueError, KeyError, IndexError):
        print(f"compilar: no pude consultar la versión de Chrome; uso {CHROME_POR_DEFECTO}")
        return CHROME_POR_DEFECTO


def main(salida):
    salida = pathlib.Path(salida).resolve()
    fuentes = salida / "fuentes"
    shutil.rmtree(fuentes, ignore_errors=True)
    fuentes.mkdir(parents=True)
    version = (AQUI / "VERSION").read_text().strip()
    chrome = version_chrome()
    texto = (AQUI / "portable/velbrum.py").read_text(encoding="utf-8").replace("@versionVelbrum@", version)
    (fuentes / "velbrum.py").write_text(texto, encoding="utf-8")
    texto = (AQUI / "host/extensiones_chrome.py").read_text(encoding="utf-8").replace("@versionChromium@", chrome)
    (fuentes / "extensiones_chrome.py").write_text(texto, encoding="utf-8")
    texto = (AQUI / "host/host-extensiones.py").read_text(encoding="utf-8")
    (fuentes / "velbrum_host.py").write_text(texto, encoding="utf-8")

    icono = []
    if sys.platform == "win32":
        icono = ["--icon", str(salida / "recursos" / "velbrum.ico")]
    elif sys.platform == "darwin":
        icono = ["--icon", str(salida / "recursos" / "velbrum.icns")]
    comun = ["--noconfirm", "--clean", "--onedir", "--paths", str(fuentes),
             "--distpath", str(salida / "dist"), "--workpath", str(salida / "trabajo"),
             "--specpath", str(salida / "trabajo")]
    # El lanzador no abre una consola en Windows; el host sí la necesita (el
    # navegador le habla por la entrada y la salida estándar).
    ventana = ["--noconsole"] if sys.platform == "win32" else []
    # certifi: los certificados raíz de Mozilla para las descargas (las tiendas,
    # addons.mozilla.org), por si el sistema no los tiene donde los busca el
    # programa compilado.
    datos = ["--hidden-import", "extensiones_chrome", "--hidden-import", "certifi", "--collect-data", "certifi"]
    subprocess.run([sys.executable, "-m", "PyInstaller", *comun, *ventana, *icono, "--name", "velbrum",
                    *datos, str(fuentes / "velbrum.py")], check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", *comun, "--name", "velbrum-host",
                    *datos, str(fuentes / "velbrum_host.py")], check=True)
    print(f"compilar: Velbrum {version} (Chrome {chrome}) en {salida / 'dist'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "build")
