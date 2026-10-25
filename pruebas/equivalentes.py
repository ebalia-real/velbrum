"""Verifica extension/equivalentes.json contra las tiendas (necesita internet).

Uso: python3 -I pruebas/equivalentes.py   (desde la carpeta de Velbrum)

Para cada fila comprueba que:
- addons.mozilla.org tenga el complemento (API pública v5), público, para
  Firefox, compatible con la versión de Velbrum y con un XPI con hash;
- la tienda de Chrome y la de Edge tengan las extensiones de esos ID;
- los tres nombres se parezcan (para no apuntar a la extensión equivocada).
Correrlo antes de agregar filas y de vez en cuando: AMO puede retirar una.
"""
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent.parent
VERSION_FIREFOX = 156  # la de LibreWolf en Velbrum (ver README.md)
NAVEGADOR = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def pedir(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def palabras(texto):
    return {p for p in re.findall(r"[a-z0-9]+", texto.lower()) if len(p) > 2}


def parecido(nombre, otro):
    clave = palabras(nombre) or {nombre.lower()}
    return bool(clave & palabras(otro)) or nombre.lower().replace(" ", "") in otro.lower().replace(" ", "")


def revisar(fila):
    problemas = []
    nombre = fila["nombre"]
    try:
        amo = json.loads(pedir(f"https://addons.mozilla.org/api/v5/addons/addon/{fila['amo']}/?lang=en-US"))
        version = amo["current_version"]
        minima = (version.get("compatibility") or {}).get("firefox", {}).get("min", "999")
        if amo.get("status") != "public" or amo.get("is_disabled"):
            problemas.append("AMO: no es público")
        if int(minima.split(".")[0]) > VERSION_FIREFOX:
            problemas.append(f"AMO: pide Firefox {minima}")
        if not version["file"]["hash"].startswith("sha256:"):
            problemas.append("AMO: sin hash sha256")
        titulo = amo["name"] if isinstance(amo["name"], str) else next(iter(amo["name"].values()), "")
        if not parecido(nombre, titulo):
            problemas.append(f"AMO: se llama «{titulo}»")
    except (OSError, ValueError, KeyError) as error:
        problemas.append(f"AMO: {error}")
    try:
        titulo = re.search(r"<title>([^<]*)", pedir(f"https://chromewebstore.google.com/detail/{fila['chrome']}"))
        titulo = titulo.group(1).removesuffix(" - Chrome Web Store") if titulo else ""
        if titulo in ("", "Chrome Web Store") or not parecido(nombre, titulo):
            problemas.append(f"Chrome: «{titulo or 'no está'}»")
    except OSError as error:
        problemas.append(f"Chrome: {error}")
    if "edge" in fila:
        try:
            edge = json.loads(pedir(f"https://microsoftedge.microsoft.com/addons/getproductdetailsbycrxid/{fila['edge']}"))
            if not parecido(nombre, edge.get("name", "")):
                problemas.append(f"Edge: «{edge.get('name')}»")
        except (OSError, ValueError) as error:
            problemas.append(f"Edge: {error}")
    return problemas


def main():
    tabla = json.loads((AQUI / "extension/equivalentes.json").read_text(encoding="utf-8"))
    fallas = 0
    for fila in tabla:
        problemas = revisar(fila)
        fallas += bool(problemas)
        print(("✔" if not problemas else "✘"), fila["nombre"], "→", fila["amo"], ("" if not problemas else "· " + "; ".join(problemas)))
    print(f"\n{len(tabla) - fallas} de {len(tabla)} filas verificadas")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
