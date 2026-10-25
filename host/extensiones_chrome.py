"""Extensiones de Chrome en Velbrum, que usa el motor Gecko (ver README.md).

Descarga una extensión de la tienda de Chrome o de la de Edge (las dos usan el
formato de Chromium), la convierte en un complemento de Gecko (XPI sin firma)
y la guarda en ~/.local/share/velbrum/extensiones-chrome/. También actualiza las
ya instaladas, cada una desde la tienda de la que vino: deja la versión nueva
en el perfil de Gecko y el navegador la toma en el próximo arranque.

Uso: extensiones_chrome.py instalar ID|URL|ARCHIVO.crx   (imprime la URL file:// del XPI)
     extensiones_chrome.py actualizar
     extensiones_chrome.py listar

Con un ID solo, se busca primero en la tienda de Chrome y después en la de Edge.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import pathlib
import re
import shutil
import ssl
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

VERSION_CHROMIUM = "@versionChromium@"
COMPAT = "@compat@"  # carpeta con compat/fondo.js
# Tabla de extensiones de las tiendas con versión oficial para Firefox
# (extension/equivalentes.json; la extensión de Velbrum usa la misma).
EQUIVALENTES = "@equivalentes@"
# En NixOS, default.nix pone esas rutas. En los paquetes para Windows, macOS y
# Linux sin Nix (portable/), compat/ y equivalentes.json van junto al programa.
_BASE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else globals().get("__file__", ".")))
if COMPAT.startswith("@"):
    COMPAT = os.path.join(_BASE, "compat")
if EQUIVALENTES.startswith("@"):
    EQUIVALENTES = os.path.join(_BASE, "equivalentes.json")
SUFIJO_ID = "@chrome.velbrum"
# Versión de la capa de compatibilidad (compat/): cuando cambia, `actualizar`
# vuelve a convertir las extensiones instaladas aunque no tengan versión nueva.
VERSION_COMPAT = 3
ARCHIVOS_COMPAT = ("fondo.js", "pagina.js", "contenido.js", "permisos.html", "permisos.js")
# Antes de llamarse Velbrum el navegador se llamaba Bruma: las extensiones que
# ya estaban instaladas conservan su ID y su carpeta interna (ver sufijo_para).
SUFIJOS_ANTERIORES = ("@chrome.bruma",)
SUFIJOS = (SUFIJO_ID,) + SUFIJOS_ANTERIORES
ORIGENES = ("velbrum-compat/origen.json", "bruma-compat/origen.json")
URL_TIENDA = "https://clients2.google.com/service/update2/crx"
URL_EDGE = "https://edge.microsoft.com/extensionwebstorebase/v1/crx"
# La tienda de Edge indica sus CRX con direcciones http:// de su CDN, cuyo
# certificado solo vale para este nombre: se piden por https acá.
CDN_EDGE = "msedgeextensions.sf.tlu.dl.delivery.mp.microsoft.com"
TIENDAS = {"chrome": "la tienda de Chrome", "edge": "la tienda de Edge"}
# Gecko consulta las actualizaciones en la URL del complemento; esta no
# responde, así que no le cuenta a nadie qué extensiones usás (las
# actualizaciones las hace `actualizar`).
URL_SIN_ACTUALIZACIONES = "https://localhost/velbrum/sin-actualizaciones.json"
RE_ID = re.compile(r"(?<![a-z])([a-p]{32})(?![a-z])")
# Servidores a los que se pregunta por versiones (siempre por https).
SERVIDORES_CONSULTA = {"clients2.google.com", "edge.microsoft.com"}
# Versiones oficiales para Firefox: la API pública de addons.mozilla.org.
SERVIDOR_AMO = "addons.mozilla.org"
API_AMO = f"https://{SERVIDOR_AMO}/api/v5/addons/addon/"
RE_SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,99}")
# Límites contra archivos enormes o «bombas zip».
MAXIMO_DESCARGA = 256 * 1024 * 1024
MAXIMO_DESCOMPRIMIDO = 512 * 1024 * 1024
MAXIMO_ARCHIVOS = 20000

# Permisos de Chrome que Gecko no tiene. Se sacan del manifiesto (si no,
# Gecko avisa) y se informa al instalar.
SIN_EQUIVALENTE = {
    "background", "certificateProvider", "contentSettings", "debugger",
    "declarativeContent", "desktopCapture", "documentScan", "enterprise.deviceAttributes",
    "enterprise.hardwarePlatform", "enterprise.networkingAttributes", "enterprise.platformKeys",
    "favicon", "fileBrowserHandler", "fileSystemProvider", "fontSettings", "gcm", "loginState",
    "platformKeys", "power", "printerProvider", "printing", "printingMetrics", "processes",
    "readingList", "system.cpu", "system.display", "system.memory", "system.storage",
    "tabCapture", "transientBackground", "tts", "ttsEngine", "vpnProvider", "wallpaper",
    "webAuthenticationProxy", "accessibilityFeatures.modify", "accessibilityFeatures.read",
    "audio", "identity.email",
}
EMULADOS = {"offscreen", "sidePanel"}
# Permisos que Chrome concede al instalar y Gecko solo acepta como opcionales:
# Velbrum los pide con un botón (compat/permisos.html).
SOLO_OPCIONALES = {"userScripts"}
# Claves del manifiesto de Chrome que Gecko no entiende o rechaza.
CLAVES_DE_CHROME = {
    "key", "update_url", "minimum_chrome_version", "differential_fingerprint", "oauth2",
    "externally_connectable", "import", "export", "current_locale", "event_rules",
    "file_browser_handlers", "file_system_provider_capabilities", "input_components",
    "nacl_modules", "platforms", "requirements", "tts_engine", "automation", "offline_enabled",
    "replacement_web_app", "trial_tokens", "cross_origin_embedder_policy",
    "cross_origin_opener_policy", "file_handlers", "side_panel", "sandbox",
}
# APIs que una extensión puede usar sin pedir permiso en el manifiesto.
APIS_SIN_EQUIVALENTE = (
    "tabCapture", "desktopCapture", "debugger", "tts", "ttsEngine", "gcm", "instanceID",
    "readingList", "printing", "system", "enterprise", "fontSettings", "power", "processes",
    "wallpaper", "loginState", "platformKeys", "documentScan", "declarativeContent", "contentSettings",
)
RE_API = re.compile(r"\bchrome\.(" + "|".join(APIS_SIN_EQUIVALENTE) + r")\.")
# CSS de los scripts de contenido: ver css_en_capa.
CAPA_CSS = "velbrum-extension"
RE_CSS_NO_ENVOLVIBLE = re.compile(rb"@(import|namespace)\b", re.I)
RE_IMPORT_SCRIPTS = re.compile(r"\bimportScripts\s*\(([^)]*)\)")
RE_TEXTO = re.compile(r"""(['"])((?:\\.|(?!\1).)*)\1""")


class ErrorExtension(Exception):
    pass


# ── Rutas ──────────────────────────────────────────────────────────────────
def carpeta_datos():
    # Los paquetes sin Nix (portable/) dicen dónde están los datos: junto al
    # programa en la versión portable, o la carpeta de datos de cada sistema.
    if os.environ.get("VELBRUM_DATOS"):
        return os.environ["VELBRUM_DATOS"]
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "velbrum")


def firmas_obligatorias():
    """El interruptor de firmas (velbrum --exigir-firmas / --permitir-sin-firma)."""
    return os.path.exists(os.path.join(carpeta_datos(), "firmas-obligatorias"))


def carpeta_xpi():
    ruta = os.path.join(carpeta_datos(), "extensiones-chrome")
    os.makedirs(ruta, mode=0o700, exist_ok=True)
    os.chmod(ruta, 0o700)
    return ruta


def sufijo_para(id_chrome):
    """El sufijo del ID en Gecko: el de antes del cambio de nombre si esa
    extensión ya estaba instalada así (para que se actualice en lugar de
    instalarse dos veces), si no el actual."""
    carpeta = carpeta_extensiones_perfil()
    for sufijo in SUFIJOS_ANTERIORES:
        if os.path.exists(os.path.join(carpeta, id_chrome + sufijo + ".xpi")):
            return sufijo
    return SUFIJO_ID


def carpeta_extensiones_perfil():
    return os.path.join(carpeta_datos(), "gecko", "extensions")


def id_desde(texto):
    """Acepta el ID de 32 letras o la URL de la extensión en la tienda."""
    ruta = urllib.parse.urlsplit(texto.strip()).path or texto
    candidatos = RE_ID.findall(ruta) or RE_ID.findall(texto)
    if not candidatos:
        raise ErrorExtension(f"no encontré un ID de extensión de Chrome en «{texto}»")
    return candidatos[-1]


def tienda_desde(texto):
    """«edge» o «chrome» si `texto` es una URL de esa tienda; si no, None."""
    servidor = urllib.parse.urlsplit(texto.strip()).hostname or ""
    if servidor == "microsoftedge.microsoft.com":
        return "edge"
    if servidor in ("chromewebstore.google.com", "chrome.google.com"):
        return "chrome"
    return None


# ── Tiendas de Chrome y de Edge ────────────────────────────────────────────
class _SoloRedireccionesSeguras(urllib.request.HTTPRedirectHandler):
    """Sigue redirecciones solo a http/https; con `solo_https`, solo a https."""

    def __init__(self, solo_https):
        self.solo_https = solo_https

    def redirect_request(self, pedido, fp, codigo, mensaje, cabeceras, nueva):
        esquema = urllib.parse.urlsplit(nueva).scheme
        if esquema not in (("https",) if self.solo_https else ("http", "https")):
            raise urllib.error.URLError(f"redirección no permitida a {esquema}://")
        return super().redirect_request(pedido, fp, codigo, mensaje, cabeceras, nueva)


def _contexto_tls():
    """Verificación de certificados con los del sistema y, en los paquetes sin
    Nix (PyInstaller), también con los de certifi: el programa compilado en
    una distro busca los del sistema donde los pone esa distro, y en otras
    (y en macOS) no los encontraría."""
    contexto = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        return contexto
    contexto.load_verify_locations(certifi.where())
    return contexto


def pedir(url, donde="la tienda de Chrome", solo_https=True):
    """Descarga `url` (como máximo MAXIMO_DESCARGA bytes). Con `solo_https`,
    no acepta http ni redirecciones a http."""
    esquema = urllib.parse.urlsplit(url).scheme
    if esquema != "https" and (solo_https or esquema != "http"):
        raise ErrorExtension(f"dirección no permitida para {donde}: {url}")
    mayor = VERSION_CHROMIUM.split(".")[0]
    pedido = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{mayor}.0.0.0 Safari/537.36"
        },
    )
    abridor = urllib.request.build_opener(_SoloRedireccionesSeguras(solo_https),
                                          urllib.request.HTTPSHandler(context=_contexto_tls()))
    try:
        with abridor.open(pedido, timeout=90) as respuesta:
            datos = respuesta.read(MAXIMO_DESCARGA + 1)
    except OSError as error:
        raise ErrorExtension(f"no pude conectarme con {donde}: {error}") from error
    if len(datos) > MAXIMO_DESCARGA:
        raise ErrorExtension(f"lo que mandó {donde} es demasiado grande")
    return datos


def consultar(id_chrome, version="0.0.0.0", tienda="chrome"):
    """Devuelve (versión, url, sha256) de la última versión en la tienda, o None
    si no hay nada nuevo (o la tienda no la tiene). Las dos tiendas responden
    con el mismo protocolo de actualizaciones de Chromium."""
    x = urllib.parse.quote(f"id={id_chrome}&v={version}&uc")
    if tienda == "edge":
        url = f"{URL_EDGE}?prodversion={VERSION_CHROMIUM}&prod=chromiumcrx&prodchannel=&x={x}"
    else:
        url = f"{URL_TIENDA}?prodversion={VERSION_CHROMIUM}&acceptformat=crx3&x={x}"
    if urllib.parse.urlsplit(url).hostname not in SERVIDORES_CONSULTA:
        raise ErrorExtension(f"servidor no permitido para {TIENDAS[tienda]}")
    xml = pedir(url, TIENDAS[tienda], solo_https=True)
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as error:
        raise ErrorExtension(f"{TIENDAS[tienda]} respondió algo inesperado") from error
    for nodo in raiz.iter():
        if nodo.tag.endswith("updatecheck"):
            if nodo.get("status") == "ok" and nodo.get("codebase"):
                return nodo.get("version"), nodo.get("codebase"), nodo.get("hash_sha256")
            return None
    return None


def descargar(url, sha256, tienda):
    """Baja el CRX que indicó la tienda y comprueba que sea el que anunció (el
    hash llega por https junto con la dirección)."""
    intentos = [url]
    partes = urllib.parse.urlsplit(url)
    if partes.scheme == "http":
        servidor = CDN_EDGE if partes.hostname.endswith(".tlu.dl.delivery.mp.microsoft.com") else partes.netloc
        intentos.insert(0, partes._replace(scheme="https", netloc=servidor).geturl())
        if not sha256:
            del intentos[1:]  # sin hash no hay cómo verificar lo que llega por http
    for intento in intentos:
        try:
            # Por http solo si hay hash (llegó por https); igual después se
            # verifica la firma del autor (verificar_crx).
            datos = pedir(intento, TIENDAS[tienda], solo_https=not sha256)
            break
        except ErrorExtension as error:
            fallo = error
    else:
        raise fallo
    if sha256 and hashlib.sha256(datos).hexdigest() != sha256.lower():
        raise ErrorExtension(f"lo que bajé de {TIENDAS[tienda]} no es lo que anunció (el hash no coincide)")
    return datos


# ── Versiones oficiales para Firefox (addons.mozilla.org) ──────────────────
def equivalente(id_chrome, tienda="chrome"):
    """La fila de equivalentes.json de una extensión de la tienda de Chrome o
    de Edge que tiene versión oficial para Firefox, o None."""
    try:
        with open(EQUIVALENTES, encoding="utf-8") as f:
            tabla = json.load(f)
    except (OSError, ValueError):
        return None
    for fila in tabla if isinstance(tabla, list) else []:
        if (
            isinstance(fila, dict)
            and tienda in TIENDAS
            and fila.get(tienda) == id_chrome
            and RE_SLUG.fullmatch(str(fila.get("amo", "")))
        ):
            return fila
    return None


def archivo_amo(respuesta):
    """De la respuesta de la API de AMO, (versión, url, sha256) del XPI
    que firmó Mozilla. Rechaza lo que no sea un complemento público para
    Firefox, servido por https desde addons.mozilla.org."""
    try:
        datos = json.loads(respuesta)
        version = datos["current_version"]
        archivo = version["file"]
        url, hash_ = archivo["url"], archivo["hash"]
        compatible = "firefox" in (version.get("compatibility") or {})
        publico = datos.get("status") == "public" and not datos.get("is_disabled")
    except (ValueError, KeyError, TypeError) as error:
        raise ErrorExtension("addons.mozilla.org respondió algo inesperado") from error
    if not publico or not compatible:
        raise ErrorExtension("la versión para Firefox ya no está disponible en addons.mozilla.org")
    partes = urllib.parse.urlsplit(str(url))
    if partes.scheme != "https" or partes.hostname != SERVIDOR_AMO:
        raise ErrorExtension(f"addons.mozilla.org indicó una dirección no permitida: {url}")
    algoritmo, _, sha256 = str(hash_).partition(":")
    if algoritmo != "sha256" or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ErrorExtension("addons.mozilla.org no indicó el hash del archivo")
    return str(version.get("version", "")), url, sha256


def preparar_firefox(id_chrome, tienda):
    """Baja de addons.mozilla.org la versión oficial para Firefox de una
    extensión de la tienda de Chrome o de Edge; devuelve la ruta del XPI y un
    resumen. Mozilla la firmó, así que se puede instalar también con las
    firmas exigidas (Gecko verifica esa firma al instalarla)."""
    fila = equivalente(id_chrome, tienda)
    if not fila:
        raise ErrorExtension(f"la extensión {id_chrome} no tiene una versión para Firefox conocida")
    slug = fila["amo"]
    version, url, sha256 = archivo_amo(pedir(f"{API_AMO}{slug}/", SERVIDOR_AMO))
    xpi = pedir(url, SERVIDOR_AMO)
    if hashlib.sha256(xpi).hexdigest() != sha256:
        raise ErrorExtension("lo que bajé de addons.mozilla.org no es lo que anunció (el hash no coincide)")
    carpeta = os.path.join(carpeta_datos(), "extensiones-firefox")
    os.makedirs(carpeta, mode=0o700, exist_ok=True)
    ruta = os.path.join(carpeta, slug + ".xpi")
    escribir_atomico(ruta, xpi)
    return ruta, {"id_chrome": id_chrome, "tienda": tienda, "amo": slug,
                  "nombre": fila.get("nombre") or slug, "version": version, "avisos": []}


def _varint(datos, i):
    valor = desplazamiento = 0
    while True:
        byte = datos[i]
        i += 1
        valor |= (byte & 0x7F) << desplazamiento
        if not byte & 0x80:
            return valor, i
        desplazamiento += 7


def _campos_protobuf(datos):
    """Campos «length-delimited» de un mensaje protobuf (sin dependencias)."""
    i = 0
    while i < len(datos):
        clave, i = _varint(datos, i)
        campo, tipo = clave >> 3, clave & 7
        if tipo == 0:
            _, i = _varint(datos, i)
        elif tipo == 1:
            i += 8
        elif tipo == 5:
            i += 4
        elif tipo == 2:
            largo, i = _varint(datos, i)
            yield campo, datos[i : i + largo]
            i += largo
        else:
            return


def a_letras(digest):
    return "".join(chr(ord("a") + int(c, 16)) for c in digest[:16].hex())


def id_de_archivo(datos):
    """El ID de Chrome de un .crx, verificado con la firma del autor."""
    return verificar_crx(datos)[0]


def manifiesto_de_archivo(datos):
    try:
        with zipfile.ZipFile(io.BytesIO(crx_a_zip(datos))) as z:
            manifiesto = json_tolerante(z.read("manifest.json").decode("utf-8", "replace"))
    except (KeyError, ValueError, zipfile.BadZipFile, ErrorExtension):
        return {}
    return manifiesto if isinstance(manifiesto, dict) else {}


def tienda_de_archivo(datos):
    """La tienda de la que salió un .crx, según su dirección de actualización.
    Los que no son de Edge se buscan en la de Chrome."""
    url = manifiesto_de_archivo(datos).get("update_url")
    servidor = urllib.parse.urlsplit(url).hostname if isinstance(url, str) else None
    return "edge" if servidor == "edge.microsoft.com" else "chrome"


def ruta_local(origen):
    """La ruta si `origen` es un archivo (o una URL file://), si no None."""
    if origen.startswith("file://"):
        origen = urllib.parse.unquote(urllib.parse.urlsplit(origen).path)
    return origen if os.path.isfile(origen) else None


# ── Firma CRX3 ─────────────────────────────────────────────────────────────
# Un CRX3 es: «Cr24», versión 3, una cabecera protobuf con las firmas y el zip.
# El ID de la extensión son los primeros 16 bytes del SHA-256 de la clave
# pública del autor; la firma (RSA PKCS#1 v1.5 con SHA-256) cubre la cabecera
# firmada y todo el zip. Se verifica sin dependencias (Python puro).
PREFIJO_FIRMA = b"CRX3 SignedData\x00"
DIGESTINFO_SHA256 = bytes.fromhex("3031300d060960864801650304020105000420")
OID_RSA = bytes.fromhex("2a864886f70d010101")


def _der(datos, i):
    """Un elemento DER desde `i`: (etiqueta, contenido, posición siguiente)."""
    etiqueta, largo = datos[i], datos[i + 1]
    i += 2
    if largo & 0x80:
        n = largo & 0x7F
        if not 0 < n <= 4:
            raise ValueError("DER inválido")
        largo = int.from_bytes(datos[i : i + n], "big")
        i += n
    if i + largo > len(datos):
        raise ValueError("DER cortado")
    return etiqueta, datos[i : i + largo], i + largo


def _clave_rsa(spki):
    """(n, e) de una clave pública RSA en formato SubjectPublicKeyInfo."""
    etiqueta, secuencia, _ = _der(spki, 0)
    _, algoritmo, i = _der(secuencia, 0)
    _, oid, _ = _der(algoritmo, 0)
    if etiqueta != 0x30 or oid != OID_RSA:
        return None
    etiqueta, bits, _ = _der(secuencia, i)
    if etiqueta != 0x03 or not bits or bits[0] != 0:
        return None
    _, rsa, _ = _der(bits[1:], 0)
    _, n, j = _der(rsa, 0)
    _, e, _ = _der(rsa, j)
    return int.from_bytes(n, "big"), int.from_bytes(e, "big")


def _firma_rsa_valida(spki, firma, mensaje):
    try:
        clave = _clave_rsa(spki)
    except (ValueError, IndexError):
        return False
    if not clave:
        return False
    n, e = clave
    k = (n.bit_length() + 7) // 8
    # Como Chrome: claves de 1024 bits o más (las extensiones viejas, como
    # Google Translate o Tampermonkey, todavía firman con 1024).
    if k < 128 or len(firma) != k or e < 3:
        return False
    recuperado = pow(int.from_bytes(firma, "big"), e, n).to_bytes(k, "big")
    relleno = k - 3 - len(DIGESTINFO_SHA256) - 32
    esperado = b"\x00\x01" + b"\xff" * relleno + b"\x00" + DIGESTINFO_SHA256 + hashlib.sha256(mensaje).digest()
    return hmac.compare_digest(recuperado, esperado)


def verificar_crx(datos):
    """Comprueba la firma del autor de un CRX3 y devuelve (ID, zip).
    Rechaza CRX2, zips sueltos, firmas inválidas y archivos modificados."""
    if datos[:4] != b"Cr24":
        raise ErrorExtension("no es una extensión de Chrome (CRX)")
    try:
        version, largo = struct.unpack("<II", datos[4:12])
        if version != 3:
            raise ErrorExtension(f"formato CRX{version}: no tiene una firma que Velbrum pueda verificar")
        cabecera, archivo_zip = datos[12 : 12 + largo], datos[12 + largo :]
        if len(cabecera) != largo:
            raise ErrorExtension("el CRX está cortado")
        pruebas, firmado = [], b""
        for campo, valor in _campos_protobuf(cabecera):
            if campo == 2:  # sha256_with_rsa
                pruebas.append(dict(_campos_protobuf(valor)))
            elif campo == 10000:  # signed_header_data
                firmado = valor
        crx_id = dict(_campos_protobuf(firmado)).get(1, b"")
    except (IndexError, struct.error, ValueError) as error:
        raise ErrorExtension("el CRX está dañado") from error
    if len(crx_id) != 16:
        raise ErrorExtension("el CRX no dice de qué extensión es")
    mensaje = PREFIJO_FIRMA + struct.pack("<I", len(firmado)) + firmado + archivo_zip
    for prueba in pruebas:
        clave, firma = prueba.get(1, b""), prueba.get(2, b"")
        if hashlib.sha256(clave).digest()[:16] == crx_id and _firma_rsa_valida(clave, firma, mensaje):
            return a_letras(crx_id), archivo_zip
    raise ErrorExtension("la firma del CRX no es válida: fue modificado o no es de quien dice ser")


def crx_a_zip(datos):
    return verificar_crx(datos)[1]


# ── Conversión ─────────────────────────────────────────────────────────────
def json_tolerante(texto):
    """JSON con comentarios y comas finales, como acepta Chrome."""
    texto = texto.lstrip("﻿")
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    salida, i, en_texto = [], 0, False
    while i < len(texto):
        c = texto[i]
        if en_texto:
            salida.append(c)
            if c == "\\":
                salida.append(texto[i + 1 : i + 2])
                i += 1
            elif c == '"':
                en_texto = False
        elif c == '"':
            en_texto = True
            salida.append(c)
        elif texto.startswith("//", i):
            i = texto.find("\n", i)
            i = len(texto) if i < 0 else i
            continue
        elif texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            i = len(texto) if fin < 0 else fin + 2
            continue
        else:
            salida.append(c)
        i += 1
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(salida)))


def resolver(base, relativa):
    if relativa.startswith("/"):
        return os.path.normpath(relativa.lstrip("/"))
    return os.path.normpath(os.path.join(os.path.dirname(base), relativa))


def scripts_importados(archivos, script, vistos=None):
    """Los importScripts('a.js', ...) del service worker, en orden y recursivos."""
    vistos = set() if vistos is None else vistos
    resultado, dinamicos = [], False
    codigo = archivos.get(script, b"").decode("utf-8", "replace")
    for llamada in RE_IMPORT_SCRIPTS.finditer(codigo):
        argumentos = llamada.group(1).strip()
        textos = [m.group(2) for m in RE_TEXTO.finditer(argumentos)]
        if not textos and argumentos:
            dinamicos = True
        for texto in textos:
            ruta = resolver(script, texto)
            if ruta in archivos and ruta not in vistos:
                vistos.add(ruta)
                internos, din = scripts_importados(archivos, ruta, vistos)
                resultado += internos + [ruta]
                dinamicos |= din
    return resultado, dinamicos


def fragmentos_webpack(archivos, sw, ya_incluidos, manifiesto_actual):
    """Fragmentos («chunks») de webpack que el service worker carga con
    importScripts(ruta calculada). En una página de fondo no se pueden cargar
    en el momento, pero webpack acepta los que ya están registrados en su
    variable global (self.webpackChunk…), así que se cargan antes."""
    codigo = archivos.get(sw, b"").decode("utf-8", "replace")
    globales = set(re.findall(r"(?:self|globalThis|this)(?:\.|\[[\"'])(webpackChunk[\w$]*)", codigo))
    if not globales:
        return globales, []
    # Solo los de la carpeta del service worker que no usa otra parte de la
    # extensión: el popup u otras páginas pueden compartir la variable global
    # con números de módulo distintos, y se pisarían.
    usados_en_otro_lado = set()
    for ruta, contenido in archivos.items():
        if ruta.endswith((".html", ".htm")):
            for src in re.findall(r"<script[^>]+src=[\"']([^\"']+)", contenido.decode("utf-8", "replace")):
                usados_en_otro_lado.add(resolver(ruta, src))
    for c in manifiesto_actual.get("content_scripts") or []:
        usados_en_otro_lado.update(os.path.normpath(js.lstrip("/")) for js in c.get("js", []))
    carpeta = os.path.dirname(sw)
    fragmentos = []
    for ruta in sorted(archivos):
        if (
            os.path.dirname(ruta) != carpeta
            or ruta == sw
            or ruta in ya_incluidos
            or ruta in usados_en_otro_lado
            or not ruta.endswith(".js")
        ):
            continue
        inicio = archivos[ruta][:4096].decode("utf-8", "replace")
        if any(g in inicio for g in globales) and ".push(" in inicio:
            fragmentos.append(ruta)
    return globales, fragmentos


def con_script_primero(html, src):
    """El HTML con <script src=…> al principio del <head> (o del todo)."""
    texto = html.decode("utf-8", "replace")
    etiqueta = f'<script src="{src}"></script>'
    if etiqueta in texto:
        return html
    texto, n = re.subn(r"(<head(?:\s[^>]*)?>)", lambda r: r.group(1) + etiqueta, texto, count=1, flags=re.I)
    return (texto if n else etiqueta + texto).encode("utf-8")


def css_en_capa(archivos, ruta):
    """Copia del CSS de un script de contenido dentro de una capa (@layer);
    devuelve su ruta, o la original si no se puede envolver.

    En Chrome, el CSS que una extensión inyecta en las páginas pierde ante el
    de la página cuando empatan; en Gecko gana. Así una regla general de la
    extensión, como «body { height: 100% }», le pisaba a DuckDuckGo su
    «body { height: auto }» y la página quedaba sin barra y sin rueda. Las
    reglas en una capa pierden ante las de la página sin capa, como en Chrome.
    La copia queda en la misma carpeta (las url() relativas siguen valiendo) y
    el archivo original no cambia, por si lo usa también una página de la
    extensión."""
    ruta = ruta.lstrip("/")
    datos = archivos.get(ruta)
    if datos is None or RE_CSS_NO_ENVOLVIBLE.search(datos):
        return ruta
    try:
        texto = datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ruta
    texto = re.sub(r'^\s*@charset\s+"[^"]*"\s*;', "", texto, flags=re.I)
    copia = ruta[: -len(".css")] if ruta.lower().endswith(".css") else ruta
    copia += ".velbrum-capa.css"
    archivos[copia] = f"@layer {CAPA_CSS} {{\n{texto}\n}}\n".encode("utf-8")
    return copia


def adaptar_manifiesto(m, id_chrome, archivos):
    avisos = []
    nombre = m.get("name", id_chrome)

    for clave in CLAVES_DE_CHROME & m.keys():
        if clave == "sandbox":
            avisos.append("usa páginas «sandbox» (eval); en Gecko corren sin ese permiso")
        if clave == "side_panel":
            continue
        del m[clave]
    if not isinstance(m.get("author", ""), str):
        del m["author"]

    for campo in ("permissions", "optional_permissions"):
        if campo in m:
            quitados = [
                p for p in m[campo]
                if isinstance(p, str) and (p in SIN_EQUIVALENTE or p in EMULADOS or p.startswith("chrome://"))
            ]
            m[campo] = [p for p in m[campo] if p not in quitados]
            for permiso in quitados:
                if permiso in EMULADOS:
                    avisos.append(f"usa chrome.{permiso}: Velbrum lo emula")
                elif not permiso.startswith("chrome://"):
                    avisos.append(f"pide el permiso «{permiso}», que Gecko no tiene")
    permisos_a_pedir = sorted(SOLO_OPCIONALES & set(m.get("permissions") or []))
    if permisos_a_pedir:
        m["permissions"] = [p for p in m["permissions"] if p not in permisos_a_pedir]
        m["optional_permissions"] = sorted(set(m.get("optional_permissions") or []) | set(permisos_a_pedir))
        for permiso in permisos_a_pedir:
            avisos.append(f"necesita el permiso «{permiso}»: Velbrum te lo pide con un botón al instalarla")

    # Fondo: service worker → página de fondo con la capa de compatibilidad.
    fondo = m.get("background") or {}
    pagina_de_fondo = None
    compat = ["velbrum-compat/fondo.js", "velbrum-compat/config.js"]
    config = {"fragmentos": [], "permisos": permisos_a_pedir}
    if "service_worker" in fondo:
        sw = os.path.normpath(fondo["service_worker"].lstrip("/"))
        importados, dinamicos = scripts_importados(archivos, sw)
        if dinamicos:
            # Los que salen de una variable los carga compat/fondo.js en el
            # momento; los fragmentos de webpack tienen que estar desde antes.
            globales, fragmentos = fragmentos_webpack(archivos, sw, importados, m)
            if fragmentos:
                config["fragmentos"] = sorted(globales)
                importados = fragmentos + importados
            elif globales:
                avisos.append("el service worker carga scripts con rutas calculadas; puede fallar")
        config["sw"] = sw
        nuevo = {"scripts": compat + importados + [sw]}
        if fondo.get("type") == "module":
            nuevo["type"] = "module"
        m["background"] = nuevo
    elif "scripts" in fondo:
        fondo["scripts"] = compat + fondo["scripts"]
    elif "page" in fondo:
        pagina = os.path.normpath(fondo["page"].lstrip("/"))
        pagina_de_fondo = pagina
        if pagina in archivos:
            for js in reversed(compat):
                archivos[pagina] = con_script_primero(archivos[pagina], f"/{js}")

    # Las demás páginas de la extensión (ventana emergente, opciones, documento
    # oculto…) llevan compat/pagina.js primero: navigator.serviceWorker.
    for ruta in archivos:
        if ruta.lower().endswith((".html", ".htm")) and ruta != pagina_de_fondo:
            archivos[ruta] = con_script_primero(archivos[ruta], "/velbrum-compat/pagina.js")

    # Panel lateral de Chrome → barra lateral de Gecko.
    panel = (m.pop("side_panel", None) or {}).get("default_path")
    if panel and "sidebar_action" not in m:
        accion = m.get("action") or m.get("browser_action") or {}
        m["sidebar_action"] = {"default_panel": panel, "default_title": accion.get("default_title", nombre)}
        icono = accion.get("default_icon") or m.get("icons")
        if icono:
            m["sidebar_action"]["default_icon"] = icono

    if "options_page" in m:
        pagina = m.pop("options_page")
        m.setdefault("options_ui", {"page": pagina, "open_in_tab": True})
    if isinstance(m.get("options_ui"), dict):
        m["options_ui"].pop("chrome_style", None)

    if m.get("incognito") == "split":
        m["incognito"] = "spanning"

    reemplazos = m.get("chrome_url_overrides") or {}
    for pagina in [p for p in reemplazos if p != "newtab"]:
        del reemplazos[pagina]
        avisos.append(f"reemplaza la página chrome://{pagina}, que Gecko no permite cambiar")

    for c in m.get("content_scripts") or []:
        c.pop("match_origin_as_fallback", None)
        # Capa de compatibilidad primero (compat/contenido.js), salvo en los
        # scripts del «mundo» de la página, que no tienen la API de la extensión.
        if c.get("js") and c.get("world") != "MAIN":
            c["js"] = ["velbrum-compat/contenido.js"] + [j for j in c["js"] if j != "velbrum-compat/contenido.js"]
        if c.get("css"):
            c["css"] = [css_en_capa(archivos, css) for css in c["css"] if isinstance(css, str)]

    # Chrome deja bloquear webRequest.onAuthRequired (contraseñas de proxy o de
    # sitios) con webRequestAuthProvider; Gecko pide además webRequestBlocking.
    permisos = m.get("permissions") or []
    if "webRequestAuthProvider" in permisos and "webRequestBlocking" not in permisos:
        permisos.append("webRequestBlocking")

    avisos += adaptar_buscador(m, archivos)

    if m.get("background"):
        archivos["velbrum-compat/config.js"] = f"__velbrumConfigurar({json.dumps(config)});\n".encode()
    elif permisos_a_pedir:
        m["background"] = {"scripts": compat}
        archivos["velbrum-compat/config.js"] = f"__velbrumConfigurar({json.dumps(config)});\n".encode()

    m["browser_specific_settings"] = {
        "gecko": {
            "id": id_chrome + sufijo_para(id_chrome),
            "strict_min_version": "128.0",
            "update_url": URL_SIN_ACTUALIZACIONES,
        }
    }

    # APIs de Chrome que aparecen en el código y Gecko no tiene.
    usadas = set()
    for ruta, contenido in archivos.items():
        if ruta.endswith((".js", ".mjs")):
            usadas.update(RE_API.findall(contenido.decode("utf-8", "replace")))
    for api in sorted(usadas):
        avisos.append(f"usa chrome.{api}, que Gecko no tiene: esa parte puede no funcionar")

    return m, sorted(set(avisos))


RE_COMODIN_CHROME = re.compile(r"\{\w+:\w+\}")  # {google:baseURL}, {bing:cvid}…


def adaptar_buscador(m, archivos):
    """El buscador que agrega la extensión (chrome_settings_overrides). Gecko
    exige nombre y una URL https, y no entiende los comodines propios de
    Chrome y de Edge; en Chrome, sin nombre, se usa el del buscador que trae
    el navegador (prepopulated_id)."""
    ajustes = m.get("chrome_settings_overrides")
    buscador = ajustes.get("search_provider") if isinstance(ajustes, dict) else None
    if not isinstance(buscador, dict):
        return []
    buscador.pop("prepopulated_id", None)
    url = traducir(m, archivos, buscador.get("search_url"))
    if not isinstance(url, str) or not url.startswith("https://") or RE_COMODIN_CHROME.search(url):
        del ajustes["search_provider"]
        if not ajustes:
            del m["chrome_settings_overrides"]
        return ["cambia el buscador de una forma que Gecko no acepta: esa parte no se aplica"]
    sugerencias = traducir(m, archivos, buscador.get("suggest_url"))
    if sugerencias is not None and (
        not isinstance(sugerencias, str) or not sugerencias.startswith("https://") or RE_COMODIN_CHROME.search(sugerencias)
    ):
        del buscador["suggest_url"]
        buscador.pop("suggest_url_get_params", None)
        buscador.pop("suggest_url_post_params", None)
    if not buscador.get("name"):
        # «www.bing.com» → «Bing», como se llama el que trae Gecko.
        partes = (urllib.parse.urlsplit(url).hostname or "").split(".")
        buscador["name"] = (partes[-2] if len(partes) > 1 else partes[0]).capitalize() or m.get("name", "")
    return []


def traducir(m, archivos, texto):
    """Resuelve un «__MSG_clave__» con el idioma predeterminado de la extensión."""
    if not isinstance(texto, str) or not re.fullmatch(r"__MSG_\w+__", texto):
        return texto
    return nombre_legible({"name": texto}, archivos, (m.get("default_locale", "en"), "en"))


def nombre_seguro(nombre):
    """El nombre de un archivo del zip, o None si es peligroso: ruta absoluta,
    «..», barra invertida o caracteres de control."""
    if not nombre or nombre.startswith("/") or "\\" in nombre or any(ord(c) < 32 for c in nombre):
        return None
    limpio = os.path.normpath(nombre)
    if limpio in (".", "..") or ".." in limpio.split("/"):
        return None
    return limpio


def leer_zip_seguro(zip_origen):
    """{nombre: contenido} del zip, sin rutas peligrosas ni «bombas zip»."""
    infos = [i for i in zip_origen.infolist() if not i.is_dir()]
    if len(infos) > MAXIMO_ARCHIVOS:
        raise ErrorExtension("la extensión tiene demasiados archivos")
    if sum(i.file_size for i in infos) > MAXIMO_DESCOMPRIMIDO:
        raise ErrorExtension("la extensión es demasiado grande descomprimida")
    archivos = {}
    for info in infos:
        nombre = nombre_seguro(info.filename)
        if nombre is None:
            raise ErrorExtension(f"la extensión tiene un archivo con ruta peligrosa: {info.filename!r}")
        archivos[nombre] = zip_origen.read(info)
    return archivos


def convertir(datos_crx, id_chrome, tienda="chrome"):
    """CRX de la tienda → (bytes del XPI, manifiesto, avisos)."""
    id_firmado, archivo_zip = verificar_crx(datos_crx)
    if id_firmado != id_chrome:
        raise ErrorExtension(f"el CRX es de otra extensión ({id_firmado}), no de {id_chrome}")
    try:
        zip_origen = zipfile.ZipFile(io.BytesIO(archivo_zip))
        archivos = leer_zip_seguro(zip_origen)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError) as error:
        raise ErrorExtension("el CRX descargado está dañado") from error
    if "manifest.json" not in archivos:
        raise ErrorExtension("la extensión no tiene manifest.json")
    if any(n.startswith("velbrum-compat/") for n in archivos):
        raise ErrorExtension("la extensión ya tiene una carpeta velbrum-compat")

    manifiesto = json_tolerante(archivos.pop("manifest.json").decode("utf-8", "replace"))
    if manifiesto.get("manifest_version") not in (2, 3):
        raise ErrorExtension("la extensión usa una versión de manifiesto desconocida")
    if manifiesto.get("app"):
        raise ErrorExtension("es una «app» de Chrome, no una extensión")
    nombre = nombre_legible(manifiesto, archivos)
    manifiesto, avisos = adaptar_manifiesto(manifiesto, id_chrome, archivos)

    # En una extensión de Chrome, «chrome-extension:» casi siempre se refiere a
    # sus propias páginas; en Gecko el esquema es «moz-extension:».
    for ruta, contenido in archivos.items():
        if ruta.endswith((".js", ".mjs", ".html", ".htm", ".css", ".json")) and b"chrome-extension:" in contenido:
            archivos[ruta] = contenido.replace(b"chrome-extension:", b"moz-extension:")

    for archivo in ARCHIVOS_COMPAT:
        with open(os.path.join(COMPAT, archivo), "rb") as f:
            archivos[f"velbrum-compat/{archivo}"] = f.read()
    archivos["velbrum-compat/origen.json"] = json.dumps(
        {
            "id_chrome": id_chrome,
            # De qué tienda vino: `actualizar` busca ahí las versiones nuevas.
            "tienda": tienda,
            "nombre": nombre,
            "version": manifiesto.get("version"),
            "convertida": time.strftime("%Y-%m-%d %H:%M"),
            "compat": VERSION_COMPAT,
            "avisos": avisos,
        },
        ensure_ascii=False,
        indent=1,
    ).encode("utf-8")

    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as xpi:
        xpi.writestr("manifest.json", json.dumps(manifiesto, ensure_ascii=False, indent=1))
        for ruta in sorted(archivos):
            xpi.writestr(ruta, archivos[ruta])
    return salida.getvalue(), manifiesto, avisos, nombre


def nombre_legible(manifiesto, archivos, idiomas=None):
    """El nombre de la extensión, resolviendo __MSG_clave__ con sus traducciones."""
    nombre = manifiesto.get("name", "")
    m = re.fullmatch(r"__MSG_(\w+)__", nombre)
    if not m:
        return nombre
    for idioma in idiomas or ("es", "es_419", manifiesto.get("default_locale", "en"), "en"):
        datos = archivos.get(f"_locales/{idioma}/messages.json")
        if not datos:
            continue
        try:
            mensajes = {k.lower(): v for k, v in json_tolerante(datos.decode("utf-8", "replace")).items()}
        except ValueError:
            continue
        mensaje = mensajes.get(m.group(1).lower(), {}).get("message")
        if mensaje:
            return mensaje
    return nombre


# ── Acciones ───────────────────────────────────────────────────────────────
def escribir_atomico(ruta, datos):
    temporal = ruta + ".nuevo"
    with open(temporal, "wb") as f:
        f.write(datos)
    os.replace(temporal, ruta)


def preparar(origen, tienda=None):
    """Descarga (o lee el .crx) y convierte; devuelve la ruta del XPI y un resumen.
    `tienda` es «chrome» o «edge»; si no se indica, sale de la URL o, con un
    ID solo, se prueba primero la de Chrome y después la de Edge."""
    if firmas_obligatorias():
        raise ErrorExtension(
            "Velbrum está aceptando solo extensiones firmadas por Mozilla. "
            "Para instalar extensiones de Chrome: velbrum --permitir-sin-firma"
        )
    archivo = ruta_local(origen)
    if archivo:
        if os.path.getsize(archivo) > MAXIMO_DESCARGA:
            raise ErrorExtension("el archivo .crx es demasiado grande")
        with open(archivo, "rb") as f:
            datos = f.read()
        id_chrome, version, tienda = id_de_archivo(datos), None, tienda_de_archivo(datos)
    else:
        id_chrome = id_desde(origen)
        tienda = tienda or tienda_desde(origen)
        tiendas = [tienda] if tienda else ["chrome", "edge"]
        for tienda in tiendas:
            ultima = consultar(id_chrome, tienda=tienda)
            if ultima:
                break
        else:
            if len(tiendas) == 1:
                raise ErrorExtension(f"{TIENDAS[tienda]} no tiene la extensión {id_chrome} (o no es pública)")
            raise ErrorExtension(f"ni la tienda de Chrome ni la de Edge tienen la extensión {id_chrome} (o no es pública)")
        version, url, sha256 = ultima
        datos = descargar(url, sha256, tienda)
    xpi, manifiesto, avisos, nombre = convertir(datos, id_chrome, tienda)
    ruta = os.path.join(carpeta_xpi(), id_chrome + sufijo_para(id_chrome) + ".xpi")
    escribir_atomico(ruta, xpi)
    return ruta, {
        "id_chrome": id_chrome,
        "tienda": tienda,
        "nombre": nombre,
        "version": manifiesto.get("version", version),
        "avisos": avisos,
    }


def instaladas():
    """Extensiones de Chrome convertidas que están en el perfil de Gecko."""
    carpeta = carpeta_extensiones_perfil()
    if not os.path.isdir(carpeta):
        return []
    resultado = []
    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.endswith(tuple(s + ".xpi" for s in SUFIJOS)):
            continue
        ruta = os.path.join(carpeta, archivo)
        try:
            with zipfile.ZipFile(ruta) as xpi:
                nombres = set(xpi.namelist())
                origen = json.loads(xpi.read(next(o for o in ORIGENES if o in nombres)))
                manifiesto = json.loads(xpi.read("manifest.json"))
        except (OSError, KeyError, ValueError, StopIteration, zipfile.BadZipFile):
            continue
        resultado.append((ruta, origen, manifiesto))
    return resultado


def instaladas_por_el_usuario():
    """IDs que Gecko registró como instalados con su cartel o por política
    (no los que aparecieron sueltos en la carpeta del perfil)."""
    try:
        with open(os.path.join(carpeta_datos(), "gecko", "extensions.json"), encoding="utf-8") as f:
            registro = json.load(f)
    except (OSError, ValueError):
        return set()
    return {
        a["id"]
        for a in registro.get("addons", [])
        if a.get("location") == "app-profile" and not a.get("foreignInstall") and a.get("id")
    }


def version_tupla(version):
    return tuple(int(n) for n in re.findall(r"\d+", str(version))[:4])


def permisos_pedidos(m):
    """Lo que una extensión pide sin preguntar: permisos, sitios y dónde corre."""
    pedidos = set()
    for campo in ("permissions", "host_permissions"):
        pedidos.update(p for p in m.get(campo) or [] if isinstance(p, str))
    for script in m.get("content_scripts") or []:
        pedidos.update(s for s in script.get("matches") or [] if isinstance(s, str))
    if "webRequestAuthProvider" in pedidos:
        pedidos.discard("webRequestBlocking")  # lo agrega Velbrum (adaptar_manifiesto)
    return pedidos


def actualizar():
    """Actualiza las extensiones de Chrome instaladas. Devuelve (cambios,
    pendientes): las que piden permisos nuevos no se actualizan solas (Gecko
    preguntaría), quedan para instalarlas a mano con su cartel."""
    cambios, pendientes = [], []
    if firmas_obligatorias():
        return cambios, pendientes  # Gecko tiene desactivadas las de Chrome
    aprobadas = instaladas_por_el_usuario()
    for ruta, origen, manifiesto in instaladas():
        id_chrome = origen["id_chrome"]
        if not RE_ID.fullmatch(id_chrome) or not any(id_chrome + s in aprobadas for s in SUFIJOS):
            continue
        # Las convertidas antes de que Velbrum usara la tienda de Edge no lo dicen.
        tienda = origen.get("tienda") if origen.get("tienda") in TIENDAS else "chrome"
        # Capa de compatibilidad vieja: se vuelve a convertir la misma versión
        # (o una nueva, si la hay).
        compat_vieja = origen.get("compat", 1) < VERSION_COMPAT
        try:
            nueva = consultar(id_chrome, "0" if compat_vieja else manifiesto.get("version", "0"), tienda)
            if not nueva:
                continue
            _, url, sha256 = nueva
            xpi, manifiesto_nuevo, _, nombre = convertir(descargar(url, sha256, tienda), id_chrome, tienda)
        except ErrorExtension as error:
            print(f"{id_chrome}: {error}", file=sys.stderr)
            continue
        anterior, posterior = version_tupla(manifiesto.get("version")), version_tupla(manifiesto_nuevo.get("version"))
        if posterior < anterior or (posterior == anterior and not compat_vieja):
            continue  # nunca volver a una versión anterior
        nuevos = permisos_pedidos(manifiesto_nuevo) - permisos_pedidos(manifiesto)
        if nuevos:
            pendientes.append((nombre, id_chrome, sorted(nuevos)))
            continue
        escribir_atomico(ruta, xpi)
        escribir_atomico(os.path.join(carpeta_xpi(), os.path.basename(ruta)), xpi)
        if posterior == anterior:
            cambios.append(f"{nombre}: {manifiesto.get('version')}, con la compatibilidad nueva de Velbrum")
        else:
            cambios.append(f"{nombre}: {manifiesto.get('version')} → {manifiesto_nuevo.get('version')}")
    return cambios, pendientes


def avisar_escritorio(titulo, texto):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "--app-name=Velbrum", "--icon=velbrum", titulo, texto], check=False)


def main(argv):
    if len(argv) >= 2 and argv[0] == "instalar":
        try:
            ruta, info = preparar(argv[1])
        except ErrorExtension as error:
            print(f"velbrum: {error}", file=sys.stderr)
            return 1
        print(f"{info['nombre']} {info['version']} ({TIENDAS[info['tienda']]}) convertida para Velbrum.", file=sys.stderr)
        for aviso in info["avisos"]:
            print(f"  ⚠ {aviso}", file=sys.stderr)
        oficial = equivalente(info["id_chrome"], info["tienda"])
        if oficial:
            print(f"  ★ Tiene versión oficial para Firefox, más confiable que la convertida: "
                  f"https://{SERVIDOR_AMO}/firefox/addon/{oficial['amo']}/", file=sys.stderr)
        print(pathlib.Path(ruta).as_uri())
        return 0
    if argv[:1] == ["actualizar"]:
        cambios, pendientes = actualizar()
        for cambio in cambios:
            print(f"Actualizada: {cambio}")
        if cambios:
            print("Las versiones nuevas se activan la próxima vez que abras Velbrum.")
        for nombre, id_chrome, nuevos in pendientes:
            texto = (f"La versión nueva pide permisos nuevos ({', '.join(nuevos)}). "
                     f"Para actualizarla y ver el cartel: velbrum --extension-chrome {id_chrome}")
            print(f"{nombre}: {texto}")
            avisar_escritorio(f"{nombre} necesita tu permiso para actualizarse", texto)
        return 0
    if argv[:1] == ["listar"]:
        for _, origen, manifiesto in instaladas():
            tienda = origen.get("tienda", "chrome")
            print(f"{origen['id_chrome']}  {tienda:6}  {manifiesto.get('version')}  {origen.get('nombre') or manifiesto.get('name')}")
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
