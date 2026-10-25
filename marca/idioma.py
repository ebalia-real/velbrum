"""Paquete de idioma de Velbrum (lo corre el servicio de sistema velbrum-idioma).

Mozilla publica un paquete de idioma por versión de Firefox, pero su marca dice
«Firefox». Este programa baja el de esta versión, le pone la marca de Velbrum
(marca/brand.ftl y brand.properties), le saca la firma de Mozilla (ya no
corresponde) y lo deja en una carpeta que solo root puede modificar
(/var/lib/velbrum/idioma). Desde ahí lo instala una política del navegador
(default.nix): Gecko no carga paquetes sueltos del perfil sin preguntar.

Uso: idioma.py CARPETA VERSION_FIREFOX CARPETA_MARCA IDIOMA...
Los IDIOMAS van en orden de preferencia (por ejemplo es-MX es es-ES): se deja
el primero que Mozilla tenga y se borran los demás. Termina con error si no
hay conexión, para que systemd lo reintente.
"""
import io
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
import zipfile

URL = "https://releases.mozilla.org/pub/firefox/releases/{version}/linux-x86_64/xpi/{idioma}.xpi"
RE_IDIOMA = re.compile(r"[a-z]{2,3}(-[A-Z]{2})?")
RE_VERSION = re.compile(r"[0-9]+(\.[0-9]+){1,3}")
MAXIMO = 32 * 1024 * 1024


class SinConexion(Exception):
    pass


def descargar(version, idioma):
    """El paquete, o None si Mozilla no tiene ese idioma; sin red, SinConexion."""
    try:
        with urllib.request.urlopen(URL.format(version=version, idioma=idioma), timeout=30) as respuesta:
            if not respuesta.geturl().startswith("https://"):
                raise SinConexion("redirección fuera de https")
            datos = respuesta.read(MAXIMO + 1)
    except urllib.error.HTTPError:
        return None
    except OSError as error:
        raise SinConexion from error
    if len(datos) > MAXIMO:
        raise SinConexion("paquete de idioma demasiado grande")
    return datos


def con_marca_velbrum(datos, idioma, marca):
    """El paquete de Mozilla sin su firma y con la marca de Velbrum."""
    reemplazos = {
        f"browser/localization/{idioma}/branding/brand.ftl": (marca / "brand.ftl").read_bytes(),
        f"browser/chrome/{idioma}/locale/branding/brand.properties": (marca / "brand.properties").read_bytes(),
    }
    salida = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(datos)) as origen, zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as nuevo:
        nombres = origen.namelist()
        if "manifest.json" not in nombres or f"langpack-{idioma}@firefox.mozilla.org" not in origen.read("manifest.json").decode():
            raise ValueError("no es el paquete de idioma esperado")
        for info in origen.infolist():
            if info.filename.startswith("META-INF/"):
                continue  # la firma de Mozilla ya no corresponde
            nuevo.writestr(info.filename, reemplazos.pop(info.filename, None) or origen.read(info))
        for nombre, contenido in reemplazos.items():
            nuevo.writestr(nombre, contenido)
    return salida.getvalue()


def escribir(destino, datos):
    temporal = destino.with_name(destino.name + ".nuevo")
    temporal.write_bytes(datos)
    temporal.chmod(0o644)
    os.replace(temporal, destino)


def main(carpeta, version, marca, *idiomas):
    carpeta, marca = pathlib.Path(carpeta), pathlib.Path(marca)
    if not RE_VERSION.fullmatch(version) or not all(RE_IDIOMA.fullmatch(i) for i in idiomas):
        sys.exit("idioma.py: versión o idioma inválidos")
    carpeta.mkdir(parents=True, exist_ok=True)
    elegido = None
    for idioma in idiomas:
        xpi, sello = carpeta / f"{idioma}.xpi", carpeta / f"{idioma}.version"
        if xpi.is_file() and sello.is_file() and sello.read_text().strip() == version:
            elegido = idioma
            break
        try:
            datos = descargar(version, idioma)
        except SinConexion as error:
            sys.exit(f"idioma.py: sin conexión con Mozilla ({error}); se reintenta más tarde")
        if datos is None:
            continue
        escribir(xpi, con_marca_velbrum(datos, idioma, marca))
        escribir(sello, f"{version}\n".encode())
        elegido = idioma
        print(f"idioma.py: paquete {idioma} para Firefox {version} listo")
        break
    for idioma in idiomas:
        if idioma != elegido:
            for sobra in (carpeta / f"{idioma}.xpi", carpeta / f"{idioma}.version"):
                sobra.unlink(missing_ok=True)
    if elegido is None:
        print(f"idioma.py: Mozilla no tiene paquete para {', '.join(idiomas)}; Velbrum queda en inglés")


if __name__ == "__main__":
    main(*sys.argv[1:])
