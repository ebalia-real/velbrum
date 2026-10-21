"""Pruebas de seguridad del conversor de extensiones de Chrome de Bruma.

Uso: python3 -I pruebas/seguridad.py   (desde la carpeta de Bruma; necesita internet)

Baja un CRX real de la tienda de Chrome (Dark Reader) y comprueba que:
- la firma CRX3 del autor se verifica y da el ID correcto;
- un CRX modificado (un byte del zip, o el ID de la cabecera) se rechaza;
- se rechazan CRX2, zips sueltos y CRX de otra extensión que la pedida;
- los nombres peligrosos del zip («..», rutas absolutas…) y las «bombas zip»
  se rechazan;
- las consultas a la tienda no aceptan http ni redirecciones a http;
- el actualizador detecta permisos nuevos y no baja de versión;
- con el interruptor de firmas activado no se instala ni actualiza nada.
"""
import importlib.util
import io
import os
import pathlib
import struct
import sys
import tempfile
import urllib.request
import zipfile

AQUI = pathlib.Path(__file__).resolve().parent.parent
ID_DARK_READER = "eimadpbcbfnmbkopoojfekhnkhdbieeh"


def cargar_conversor():
    fuente = (AQUI / "host/extensiones_chrome.py").read_text(encoding="utf-8")
    fuente = fuente.replace("@versionChromium@", "154.0.0.0").replace("@compat@", str(AQUI / "host/compat"))
    modulo = importlib.util.module_from_spec(importlib.util.spec_from_loader("extensiones_chrome", loader=None))
    exec(compile(fuente, "extensiones_chrome.py", "exec"), modulo.__dict__)
    return modulo


ec = cargar_conversor()
resultados = []


def prueba(nombre):
    def decorador(funcion):
        try:
            funcion()
            resultados.append((True, nombre, ""))
        except Exception as error:  # noqa: BLE001 - se informa cualquier falla
            resultados.append((False, nombre, f"{type(error).__name__}: {error}"))
        return funcion

    return decorador


def debe_fallar(funcion, *args):
    try:
        funcion(*args)
    except ec.ErrorExtension:
        return
    raise AssertionError("se esperaba un rechazo y no lo hubo")


with urllib.request.urlopen(
    "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=154.0"
    f"&acceptformat=crx3&x=id%3D{ID_DARK_READER}%26installsource%3Dondemand%26uc",
    timeout=60,
) as r:
    CRX = r.read()


@prueba("CRX3 real: firma válida e ID correcto")
def _():
    id_, zip_ = ec.verificar_crx(CRX)
    assert id_ == ID_DARK_READER, id_
    assert zip_[:2] == b"PK"


@prueba("CRX real se convierte (ID firmado = pedido)")
def _():
    xpi, manifiesto, _, _ = ec.convertir(CRX, ID_DARK_READER)
    assert manifiesto["browser_specific_settings"]["gecko"]["id"] == ID_DARK_READER + ec.SUFIJO_ID


@prueba("CRX real con clave de 1024 bits (Tampermonkey): firma válida")
def _():
    id_tm = "dhdgffkkebhmkfjojejmpbldmpobfkfo"
    _, url, sha256 = ec.consultar(id_tm)
    assert ec.verificar_crx(ec.descargar(url, sha256, "chrome"))[0] == id_tm


@prueba("CRX de otra extensión que la pedida: rechazado")
def _():
    debe_fallar(ec.convertir, CRX, "a" * 32)


@prueba("un byte del zip cambiado: firma inválida")
def _():
    alterado = bytearray(CRX)
    alterado[-100] ^= 0x01
    debe_fallar(ec.verificar_crx, bytes(alterado))


@prueba("ID de la cabecera cambiado: rechazado")
def _():
    # Campo 10000 (signed_header_data, 18 bytes) → campo 1 (crx_id, 16 bytes).
    i = CRX.find(bytes.fromhex("82f104120a10"))
    assert i > 0, "no encontré el crx_id en la cabecera"
    alterado = bytearray(CRX)
    alterado[i + 6] ^= 0x01
    debe_fallar(ec.verificar_crx, bytes(alterado))


@prueba("zip suelto (sin firma): rechazado")
def _():
    debe_fallar(ec.verificar_crx, CRX[CRX.find(b"PK\x03\x04") :])


@prueba("CRX2: rechazado")
def _():
    debe_fallar(ec.verificar_crx, b"Cr24" + struct.pack("<III", 2, 0, 0) + b"PK\x03\x04")


@prueba("cabecera cortada o basura: rechazada")
def _():
    debe_fallar(ec.verificar_crx, b"Cr24" + struct.pack("<II", 3, 10**6) + b"\x00" * 20)
    debe_fallar(ec.verificar_crx, b"Cr24" + struct.pack("<II", 3, 4) + b"\xff\xff\xff\xff" + b"PK")


@prueba("nombres peligrosos en el zip: rechazados")
def _():
    for nombre in ("../salir.js", "a/../../salir.js", "/etc/passwd", "a\\b.js", "a\x00b.js", ".."):
        assert ec.nombre_seguro(nombre) is None, nombre
        datos = io.BytesIO()
        with zipfile.ZipFile(datos, "w") as z:
            z.writestr(zipfile.ZipInfo(nombre if "\x00" not in nombre else "a_b.js"), b"x")
            if "\x00" in nombre:
                continue
        if "\x00" not in nombre:
            debe_fallar(ec.leer_zip_seguro, zipfile.ZipFile(io.BytesIO(datos.getvalue())))
    assert ec.nombre_seguro("js/a.js") == "js/a.js"
    assert ec.nombre_seguro("./js/a.js") == "js/a.js"


@prueba("«bomba zip»: rechazada")
def _():
    datos = io.BytesIO()
    with zipfile.ZipFile(datos, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("grande.js", b"\x00" * (ec.MAXIMO_DESCOMPRIMIDO + 1))
    debe_fallar(ec.leer_zip_seguro, zipfile.ZipFile(io.BytesIO(datos.getvalue())))


@prueba("consultas: http rechazado")
def _():
    debe_fallar(ec.pedir, "http://clients2.google.com/service/update2/crx", "prueba", True)
    debe_fallar(ec.pedir, "file:///etc/passwd", "prueba", False)


@prueba("redirección de https a http: rechazada")
def _():
    # httpbin redirige a la dirección que se le pida.
    debe_fallar(ec.pedir, "https://httpbin.org/redirect-to?url=http%3A%2F%2Fexample.com%2F", "prueba", True)


@prueba("actualizador: permisos nuevos detectados")
def _():
    viejo = {"permissions": ["storage"], "content_scripts": [{"matches": ["https://a.com/*"]}]}
    nuevo = {"permissions": ["storage", "cookies"], "host_permissions": ["<all_urls>"],
             "content_scripts": [{"matches": ["https://a.com/*"]}]}
    assert ec.permisos_pedidos(nuevo) - ec.permisos_pedidos(viejo) == {"cookies", "<all_urls>"}
    assert not ec.permisos_pedidos(viejo) - ec.permisos_pedidos(nuevo)


@prueba("actualizador: compara versiones bien (no baja de versión)")
def _():
    assert ec.version_tupla("4.9.133") > ec.version_tupla("4.9.100")
    assert not ec.version_tupla("4.9.10") > ec.version_tupla("4.9.100")
    assert ec.version_tupla("2026.1018.2229") > ec.version_tupla("2026.1012.1545")


@prueba("actualizador: ignora lo que no instalaste vos")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_DATA_HOME"] = tmp
        perfil = pathlib.Path(tmp, "bruma/gecko")
        perfil.mkdir(parents=True)
        (perfil / "extensions.json").write_text(
            '{"addons": [{"id": "a@chrome.bruma", "location": "app-profile", "foreignInstall": false},'
            ' {"id": "b@chrome.bruma", "location": "app-profile", "foreignInstall": true}]}'
        )
        assert ec.instaladas_por_el_usuario() == {"a@chrome.bruma"}


@prueba("firmas exigidas (bruma --exigir-firmas): no instala ni actualiza")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_DATA_HOME"] = tmp
        pathlib.Path(tmp, "bruma").mkdir()
        pathlib.Path(tmp, "bruma/firmas-obligatorias").touch()
        debe_fallar(ec.preparar, ID_DARK_READER)
        assert ec.actualizar() == ([], [])
        pathlib.Path(tmp, "bruma/firmas-obligatorias").unlink()
        assert not ec.firmas_obligatorias()


fallas = 0
for ok, nombre, detalle in resultados:
    print(("✔" if ok else "✘"), nombre, ("" if ok else f"→ {detalle}"))
    fallas += not ok
print(f"\n{len(resultados) - fallas} de {len(resultados)} pruebas pasaron")
sys.exit(1 if fallas else 0)
