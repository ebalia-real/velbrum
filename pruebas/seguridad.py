"""Pruebas de seguridad del conversor de extensiones de Chrome de Velbrum.

Uso: python3 -I pruebas/seguridad.py   (desde la carpeta de Velbrum; necesita internet)

Baja un CRX real de la tienda de Chrome (Dark Reader) y comprueba que:
- la firma CRX3 del autor se verifica y da el ID correcto;
- un CRX modificado (un byte del zip, o el ID de la cabecera) se rechaza;
- se rechazan CRX2, zips sueltos y CRX de otra extensión que la pedida;
- los nombres peligrosos del zip («..», rutas absolutas…) y las «bombas zip»
  se rechazan;
- las consultas a la tienda no aceptan http ni redirecciones a http;
- el actualizador detecta permisos nuevos y no baja de versión;
- el CSS de los scripts de contenido va en una capa (@layer), como en Chrome;
- con el interruptor de firmas activado no se instala ni actualiza nada;
- la tabla de versiones oficiales para Firefox (extension/equivalentes.json)
  está bien formada y la descarga de addons.mozilla.org solo acepta un XPI
  público, por https desde addons.mozilla.org y con el hash anunciado.
"""
import json
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
    fuente = fuente.replace("@equivalentes@", str(AQUI / "extension/equivalentes.json"))
    modulo = importlib.util.module_from_spec(importlib.util.spec_from_loader("extensiones_chrome", loader=None))
    exec(compile(fuente, "extensiones_chrome.py", "exec"), modulo.__dict__)
    return modulo


# Las pruebas no leen ni tocan los datos de Velbrum del usuario.
os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="velbrum-pruebas-")
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
        perfil = pathlib.Path(tmp, "velbrum/gecko")
        perfil.mkdir(parents=True)
        (perfil / "extensions.json").write_text(
            '{"addons": [{"id": "a@chrome.velbrum", "location": "app-profile", "foreignInstall": false},'
            ' {"id": "b@chrome.velbrum", "location": "app-profile", "foreignInstall": true}]}'
        )
        assert ec.instaladas_por_el_usuario() == {"a@chrome.velbrum"}


@prueba("compatibilidad: páginas, scripts de contenido y webRequest")
def _():
    m = {
        "manifest_version": 3,
        "permissions": ["webRequest", "webRequestAuthProvider"],
        "background": {"service_worker": "sw.js"},
        "content_scripts": [{"matches": ["<all_urls>"], "js": ["a.js"]},
                            {"matches": ["<all_urls>"], "js": ["b.js"], "world": "MAIN"}],
    }
    archivos = {"sw.js": b"", "popup.html": b"<html><head><title>x</title></head><body></body></html>",
                "a.js": b"", "b.js": b""}
    m, _ = ec.adaptar_manifiesto(m, ID_DARK_READER, archivos)
    assert m["content_scripts"][0]["js"] == ["velbrum-compat/contenido.js", "a.js"]
    assert m["content_scripts"][1]["js"] == ["b.js"]  # mundo de la página: sin la API de la extensión
    assert archivos["popup.html"].startswith(b'<html><head><script src="/velbrum-compat/pagina.js"></script>')
    assert "webRequestBlocking" in m["permissions"]
    # Lo agrega Velbrum: no cuenta como permiso nuevo al actualizar.
    assert ec.permisos_pedidos(m) == ec.permisos_pedidos({"permissions": ["webRequest", "webRequestAuthProvider"],
                                                         "content_scripts": m["content_scripts"]})


@prueba("compatibilidad: la página de fondo de MV2 no lleva pagina.js")
def _():
    m = {"manifest_version": 2, "background": {"page": "fondo.html"}}
    archivos = {"fondo.html": b"<head></head>", "opciones.html": b"<p>x</p>"}
    ec.adaptar_manifiesto(m, ID_DARK_READER, archivos)
    assert b"pagina.js" not in archivos["fondo.html"] and b"velbrum-compat/fondo.js" in archivos["fondo.html"]
    assert archivos["opciones.html"].startswith(b'<script src="/velbrum-compat/pagina.js"></script>')


@prueba("compatibilidad: el CSS de los scripts de contenido pierde ante el de la página")
def _():
    m = {"manifest_version": 3, "content_scripts": [{"matches": ["<all_urls>"], "js": ["a.js"],
                                                     "css": ["/estilos/modal.css", "otro.css", "falta.css"]}]}
    archivos = {"a.js": b"", "estilos/modal.css": b'@charset "utf-8";\nbody{height:100%}\n.x{background:url(../img/x.png)}',
                "otro.css": b'@import "base.css";\nbody{margin:0}'}
    m, _ = ec.adaptar_manifiesto(m, ID_DARK_READER, archivos)
    assert m["content_scripts"][0]["css"] == ["estilos/modal.velbrum-capa.css", "otro.css", "falta.css"]
    capa = archivos["estilos/modal.velbrum-capa.css"].decode()
    assert capa.startswith("@layer velbrum-extension {") and "@charset" not in capa and "url(../img/x.png)" in capa
    assert archivos["estilos/modal.css"].startswith(b"@charset")  # el original queda para las páginas propias


@prueba("firmas exigidas (velbrum --exigir-firmas): no instala ni actualiza")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_DATA_HOME"] = tmp
        pathlib.Path(tmp, "velbrum").mkdir()
        pathlib.Path(tmp, "velbrum/firmas-obligatorias").touch()
        debe_fallar(ec.preparar, ID_DARK_READER)
        assert ec.actualizar() == ([], [])
        pathlib.Path(tmp, "velbrum/firmas-obligatorias").unlink()
        assert not ec.firmas_obligatorias()


@prueba("versiones para Firefox: la tabla está bien formada")
def _():
    tabla = json.loads((AQUI / "extension/equivalentes.json").read_text(encoding="utf-8"))
    vistos = set()
    for fila in tabla:
        assert set(fila) <= {"nombre", "amo", "chrome", "edge"} and fila["nombre"], fila
        assert ec.RE_SLUG.fullmatch(fila["amo"]), fila
        for tienda in ("chrome", "edge"):
            if tienda in fila:
                assert ec.RE_ID.fullmatch(fila[tienda]) and (tienda, fila[tienda]) not in vistos, fila
                vistos.add((tienda, fila[tienda]))
                assert ec.equivalente(fila[tienda], tienda) == fila
    assert ec.equivalente(ID_DARK_READER, "chrome")["amo"] == "darkreader"
    assert ec.equivalente(ID_DARK_READER, "edge") is None  # cada tienda con sus ID
    assert ec.equivalente("a" * 32, "chrome") is None
    debe_fallar(ec.preparar_firefox, "a" * 32, "chrome")


def respuesta_amo(**cambios):
    datos = {"name": "X", "status": "public", "is_disabled": False,
             "current_version": {"version": "1.0", "compatibility": {"firefox": {"min": "128.0", "max": "*"}},
                                 "file": {"url": "https://addons.mozilla.org/firefox/downloads/file/1/x.xpi",
                                          "hash": "sha256:" + "0" * 64}}}
    for clave, valor in cambios.items():
        if clave in ("url", "hash"):
            datos["current_version"]["file"][clave] = valor
        elif clave == "compatibility":
            datos["current_version"][clave] = valor
        else:
            datos[clave] = valor
    return json.dumps(datos).encode()


@prueba("versiones para Firefox: solo XPI públicos, por https, de addons.mozilla.org")
def _():
    assert ec.archivo_amo(respuesta_amo())[1:] == ("https://addons.mozilla.org/firefox/downloads/file/1/x.xpi", "0" * 64)
    debe_fallar(ec.archivo_amo, respuesta_amo(url="http://addons.mozilla.org/x.xpi"))
    debe_fallar(ec.archivo_amo, respuesta_amo(url="https://addons.mozilla.org.ejemplo.com/x.xpi"))
    debe_fallar(ec.archivo_amo, respuesta_amo(url="https://ejemplo.com/x.xpi"))
    debe_fallar(ec.archivo_amo, respuesta_amo(hash="md5:" + "0" * 32))
    debe_fallar(ec.archivo_amo, respuesta_amo(hash="sha256:corto"))
    debe_fallar(ec.archivo_amo, respuesta_amo(status="disabled"))
    debe_fallar(ec.archivo_amo, respuesta_amo(is_disabled=True))
    debe_fallar(ec.archivo_amo, respuesta_amo(compatibility={"android": {"min": "120.0"}}))
    debe_fallar(ec.archivo_amo, b"<html>no es JSON</html>")


@prueba("versiones para Firefox: Dark Reader real, con el hash verificado y las firmas exigidas")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_DATA_HOME"] = tmp
        pathlib.Path(tmp, "velbrum").mkdir()
        pathlib.Path(tmp, "velbrum/firmas-obligatorias").touch()  # firmada por Mozilla: se permite
        ruta, info = ec.preparar_firefox(ID_DARK_READER, "chrome")
        assert info["amo"] == "darkreader" and info["version"], info
        bueno = pathlib.Path(ruta).read_bytes()
        with zipfile.ZipFile(ruta) as xpi:
            nombres = xpi.namelist()
            assert "manifest.json" in nombres and any(n.startswith("META-INF/") for n in nombres)
        # Un XPI distinto del anunciado se rechaza.
        original = ec.pedir
        ec.pedir = lambda url, *a, **k: original(url, *a, **k) if "/api/" in url else b"PK otro archivo"
        try:
            debe_fallar(ec.preparar_firefox, ID_DARK_READER, "chrome")
        finally:
            ec.pedir = original
        assert pathlib.Path(ruta).read_bytes() == bueno  # el que ya estaba no se pisó


fallas = 0
for ok, nombre, detalle in resultados:
    print(("✔" if ok else "✘"), nombre, ("" if ok else f"→ {detalle}"))
    fallas += not ok
print(f"\n{len(resultados) - fallas} de {len(resultados)} pruebas pasaron")
sys.exit(1 if fallas else 0)
