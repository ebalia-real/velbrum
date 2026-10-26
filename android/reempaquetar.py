#!/usr/bin/env python3
"""Velbrum para Android: el APK oficial de IronFox (bajado y verificado por
android/bajar.sh) con la marca, los ajustes y la extensión de Velbrum, firmado
con la clave de Velbrum. Ver README.md, «Android».

No se toca el código de la aplicación (classes*.dex): se cambian los recursos
(nombre, textos, íconos), el ID de la aplicación y, dentro de assets/omni.ja,
la configuración de Gecko (ironfox.cfg + gecko/ajustes.cfg +
android/ajustes-android.cfg), la marca de Gecko y el arranque de la extensión
de Velbrum (android/extension), que va como complemento integrado.

Uso: android/reempaquetar.py --apk IRONFOX.apk --salida VELBRUM.apk
         [--clave FIRMA.p12] [--trabajo CARPETA]
La frase de la clave la pide apksigner (o va en la variable
VELBRUM_ANDROID_FRASE, como en GitHub Actions). Sin --clave se
firma con una clave de prueba descartable (para el emulador, no para publicar).
Necesita apktool, rsvg-convert, ImageMagick y las build-tools de Android
(zipalign, apksigner) en el PATH.
"""
import argparse
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
PAQUETE_IRONFOX = "org.ironfoxoss.ironfox"
CHROME_POR_DEFECTO = "150.0.7843.0"  # si no se puede consultar (como portable/compilar.py)


def leer_env(ruta):
    valores = {}
    for linea in ruta.read_text().splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip()
    return valores


VERSIONES = leer_env(AQUI / "versiones.env")
PAQUETE = VERSIONES["PAQUETE"]
VERSION_VELBRUM = (RAIZ / "VERSION").read_text().strip()


def correr(*comando, **opciones):
    print("+", " ".join(str(c) for c in comando), flush=True)
    subprocess.run([str(c) for c in comando], check=True, **opciones)


# ── Manifiesto e ID de la aplicación ──────────────────────────────────────
def cambiar_paquete(carpeta):
    """ID propio, para que Velbrum se instale al lado de IronFox: el paquete,
    los permisos y proveedores con su nombre, y los alias de los íconos. Las
    clases siguen siendo las de Fenix (org.mozilla.fenix.*), que no cambian."""
    manifiesto = carpeta / "AndroidManifest.xml"
    texto = manifiesto.read_text(encoding="utf-8")
    if f'package="{PAQUETE_IRONFOX}"' not in texto:
        raise SystemExit("reempaquetar.py: el APK no es de IronFox")
    texto = re.sub(rf"\b{re.escape(PAQUETE_IRONFOX)}(?=[\"./])", PAQUETE, texto)
    manifiesto.write_text(texto, encoding="utf-8")

    yml = carpeta / "apktool.yml"
    texto = yml.read_text(encoding="utf-8")
    texto, n = re.subn(r"(?m)^(\s*versionName:\s*)(\S+)\s*$",
                       lambda m: f"{m.group(1)}{m.group(2)}-velbrum.{VERSION_VELBRUM}", texto)
    if n != 1:
        raise SystemExit("reempaquetar.py: no encontré versionName en apktool.yml")
    yml.write_text(texto, encoding="utf-8")


# ── Textos ─────────────────────────────────────────────────────────────────
RE_MARCA = re.compile(r"IronFox(?: OSS)?")


def sin_marca(texto):
    """«IronFox» → «Velbrum» en los textos, no en las etiquetas ni en nombres
    de recursos (las direcciones de ironfoxoss.org van en minúscula y no se
    tocan)."""
    partes = re.split(r"(<[^>]*>)", texto)
    return "".join(p if p.startswith("<") else RE_MARCA.sub("Velbrum", p) for p in partes)


# «Acerca de»: IronFox dice «%1$s es producido por IronFox OSS».
ACERCA_DE = {"values": "%1$s is free software (MPL-2.0).", "values-es": "%1$s es software libre (MPL-2.0)."}
RE_ACERCA_DE = re.compile(r'\n?\s*<string name="about_content">[^<]*</string>')


def cambiar_textos(carpeta):
    cambiados = 0
    for archivo in (carpeta / "res").glob("values*/*.xml"):
        if archivo.name not in ("strings.xml", "plurals.xml", "arrays.xml"):
            continue
        texto = archivo.read_text(encoding="utf-8")
        nuevo = sin_marca(texto)
        if archivo.name == "strings.xml":
            idioma = "values-es" if archivo.parent.name.startswith("values-es") else archivo.parent.name
            reemplazo = ACERCA_DE.get(idioma)
            # En los demás idiomas se borra: queda el texto en inglés.
            nuevo = RE_ACERCA_DE.sub(
                lambda m: f'\n    <string name="about_content">{reemplazo}</string>' if reemplazo else "", nuevo)
        if nuevo != texto:
            archivo.write_text(nuevo, encoding="utf-8")
            cambiados += 1
    print(f"textos: {cambiados} archivos con la marca cambiada")


# ── Íconos ─────────────────────────────────────────────────────────────────
DENSIDADES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
CIELO = """<radialGradient id="cielo" cx="0.4" cy="0.3" r="0.8">
      <stop offset="0" stop-color="#8f80ff"/>
      <stop offset="0.6" stop-color="#5140d0"/>
      <stop offset="1" stop-color="#33268f"/>
    </radialGradient>"""


def svg_logo():
    return (RAIZ / "iconos/velbrum.svg").read_text(encoding="utf-8")


def svg_frente():
    """El dibujo del logo sin el círculo de fondo, centrado con el margen de un
    ícono adaptable (108 dp, con lo importante dentro de los 66 dp del medio)."""
    texto = svg_logo()
    texto = re.sub(r'\s*<circle cx="64" cy="64" r="58" fill="url\(#cielo\)"/>', "", texto)
    texto = re.sub(r'\s*<circle cx="64" cy="64" r="57"[^>]*/>', "", texto)
    lado = 128 * 108 / 72
    inicio = (128 - lado) / 2
    return re.sub(r'viewBox="0 0 128 128" width="128" height="128"',
                  f'viewBox="{inicio:.2f} {inicio:.2f} {lado:.2f} {lado:.2f}" width="108" height="108"', texto, count=1)


def svg_fondo():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108" width="108" height="108">
  <defs>{CIELO}</defs>
  <rect width="108" height="108" fill="url(#cielo)"/>
</svg>"""


def svg_centrado(lado_util):
    """El logo entero (con su círculo) dentro de un cuadrado de 108 dp, ocupando
    `lado_util` dp: pantalla de inicio de Android 12+ y logos sueltos."""
    lado = 128 * 108 / lado_util
    inicio = (128 - lado) / 2
    return re.sub(r'viewBox="0 0 128 128" width="128" height="128"',
                  f'viewBox="{inicio:.2f} {inicio:.2f} {lado:.2f} {lado:.2f}" width="108" height="108"',
                  svg_logo(), count=1)


def svg_simbolo(color):
    """El símbolo de un color (notificaciones y menús)."""
    texto = (RAIZ / "marca/simbolo.svg").read_text(encoding="utf-8")
    return texto.replace('stroke="context-fill"', f'stroke="{color}"').replace(
        ' fill-opacity="context-fill-opacity"', "")


def svg_nombre(color):
    """El nombre «Velbrum» (marca/nombre.svg) en un color fijo."""
    texto = (RAIZ / "marca/nombre.svg").read_text(encoding="utf-8")
    return texto.replace("fill:context-fill", f"fill:{color}")


def dibujar(svg, ancho, alto, destino, tmp):
    fuente = Path(tmp) / "fuente.svg"
    fuente.write_text(svg, encoding="utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    correr("rsvg-convert", "-w", round(ancho), "-h", round(alto), "-o", destino, fuente)


def magick():
    return shutil.which("magick") or shutil.which("convert")


def nombre_en_lienzo(color, ancho, alto, destino, tmp):
    """«Velbrum» centrado en un lienzo de ancho×alto px, como los logotipos de
    IronFox (el texto ocupa 90 % del ancho o 50 % del alto)."""
    proporcion = 7898.5 / 1532
    w = min(ancho * 0.9, alto * 0.5 * proporcion)
    texto = Path(tmp) / "nombre.png"
    dibujar(svg_nombre(color), w, w / proporcion, texto, tmp)
    correr(magick(), "-size", f"{ancho}x{alto}", "xc:none", texto, "-gravity", "center", "-composite", destino)


def reemplazar_recurso(res, nombre, carpetas, crear):
    """Borra todas las versiones del recurso `nombre` (cualquier extensión) en
    las carpetas indicadas y crea las nuevas con crear(carpeta, factor)."""
    for carpeta in res.iterdir():
        if carpeta.name.split("-")[0] not in carpetas:
            continue
        for viejo in carpeta.glob(f"{nombre}.*"):
            viejo.unlink()
    for densidad, factor in DENSIDADES.items():
        crear(res / f"{carpetas[0]}-{densidad}", factor)


def cambiar_iconos(carpeta):
    res = carpeta / "res"
    with tempfile.TemporaryDirectory() as tmp:
        def png(svg, dp):
            return lambda c, f: dibujar(svg, dp * f, dp * f, c / f"{nombre}.png", tmp)

        # Capas del ícono adaptable (y del ícono privado).
        for nombre, svg in (
            ("ic_launcher_foreground", svg_frente()),
            ("ic_launcher_private_foreground", svg_frente()),
            ("ic_launcher_monochrome", svg_frente()),
            ("ic_launcher_private_background", svg_fondo()),
            ("ic_splash_logo", svg_centrado(66)),
            ("animated_splash_screen", svg_centrado(66)),
            ("nova_onboarding_tou", svg_centrado(66)),  # bienvenida
            ("ic_firefox", svg_centrado(108)),
        ):
            reemplazar_recurso(res, nombre, ["drawable"], png(svg, 108))
        for nombre, dp in (("firefox_icon", 16), ("mozac_ic_logo_firefox_24", 24)):
            reemplazar_recurso(res, nombre, ["drawable"], png(svg_logo(), dp))
        nombre = "ic_status_logo"
        reemplazar_recurso(res, nombre, ["drawable"], png(svg_simbolo("#ffffff"), 24))
        nombre = "ic_wordmark_logo"
        reemplazar_recurso(res, nombre, ["drawable"], png(svg_logo(), 48))
        nombre = "expressive_firefox"
        reemplazar_recurso(res, nombre, ["drawable"],
                           lambda c, f: dibujar(svg_logo(), 31 * f, 31 * f, c / f"{nombre}.png", tmp))

        # Íconos de siempre (Android 7 y anteriores, y lanzadores sin íconos
        # adaptables).
        for nombre in ("ic_launcher", "ic_launcher_round", "ic_launcher_private", "ic_launcher_private_round"):
            for viejo in res.glob(f"mipmap-*dpi/{nombre}.*"):
                viejo.unlink()
            for densidad, factor in DENSIDADES.items():
                dibujar(svg_logo(), 48 * factor, 48 * factor, res / f"mipmap-{densidad}/{nombre}.png", tmp)

        # Logotipos con el nombre: claro (modo normal) y oscuro (privado).
        for nombre, color in (
            ("ic_logo_wordmark_normal", "#000000"),
            ("ic_wordmark_text_normal", "#000000"),
            ("ic_logo_wordmark_private", "#ffffff"),
            ("ic_wordmark_text_private", "#ffffff"),
        ):
            for viejo in res.glob(f"drawable*/{nombre}.*"):
                viejo.unlink()
            for densidad, factor in DENSIDADES.items():
                nombre_en_lienzo(color, round(208.75 * factor), round(80 * factor),
                                 res / f"drawable-{densidad}/{nombre}.png", tmp)

        # Vista previa del widget de búsqueda: el logo de Velbrum sobre el zorro.
        for widget in res.glob("drawable*/fenix_search_widget.webp"):
            imagen = Path(tmp) / "widget.png"
            correr(magick(), widget, imagen)
            identify = [magick(), "identify"] if shutil.which("magick") else ["identify"]
            alto = int(subprocess.run([*identify, "-format", "%h", imagen],
                                      capture_output=True, text=True, check=True).stdout)
            logo = Path(tmp) / "logo.png"
            dibujar(svg_logo(), alto * 0.62, alto * 0.62, logo, tmp)
            lado = round(alto * 0.72)
            correr(magick(), imagen, "-fill", "white", "-draw",
                   f"rectangle {round(alto * 0.14)},{round(alto * 0.14)} {round(alto * 0.14) + lado},{round(alto * 0.86)}",
                   logo, "-gravity", "west", "-geometry", f"+{round(alto * 0.19)}+0", "-composite",
                   widget.with_suffix(".png"))
            widget.unlink()

    # Todos los íconos adaptables (también los alternativos que se eligen en
    # Ajustes) con las capas de Velbrum.
    adaptable = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_private_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
"""
    for xml in res.glob("mipmap-anydpi*/ic_launcher*.xml"):
        xml.write_text(adaptable, encoding="utf-8")


# ── Gecko (assets/omni.ja) ─────────────────────────────────────────────────
ARRANQUE = """
// Velbrum: la extensión propia (assets/extensions/velbrum) se instala como
// complemento integrado de la aplicación en cada arranque, como Fenix hace
// con los suyos (no se puede desinstalar ni aparece en la lista).
if (Services.appinfo.processType === Services.appinfo.PROCESS_TYPE_DEFAULT) {
  const { AddonManager: velbrumAddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  velbrumAddonManager.readyPromise
    .then(() => {
      const { GeckoViewWebExtension } = ChromeUtils.importESModule("resource://gre/modules/GeckoViewWebExtension.sys.mjs");
      return GeckoViewWebExtension.ensureBuiltIn(
        Services.io.newURI("resource://android/assets/extensions/velbrum/"), "chrome@velbrum");
    })
    .then(
      () => console.info("Velbrum: extensión lista"),
      error => console.error("Velbrum: no se pudo instalar la extensión", error)
    );
}
"""


def sin_marca_ftl(texto):
    """«IronFox» → «Velbrum» en los valores de un .ftl o .properties (no en
    los identificadores)."""
    lineas = []
    for linea in texto.splitlines(keepends=True):
        clave, igual, valor = linea.partition("=")
        lineas.append(clave + igual + RE_MARCA.sub("Velbrum", valor) if igual and not linea.startswith("#") else linea)
    return "".join(lineas)


def cambiar_omni(carpeta):
    omni = carpeta / "assets/omni.ja"
    ajustes = (
        "\n\n// ═══ Velbrum: gecko/ajustes.cfg ═══\n"
        + (RAIZ / "gecko/ajustes.cfg").read_text(encoding="utf-8")
        + "\n// ═══ Velbrum: android/ajustes-android.cfg ═══\n"
        + (AQUI / "ajustes-android.cfg").read_text(encoding="utf-8")
    )
    salida = io.BytesIO()
    cambios = set()
    with zipfile.ZipFile(omni) as origen, zipfile.ZipFile(salida, "w") as destino:
        for info in origen.infolist():
            datos = origen.read(info)
            nombre = info.filename
            if nombre == "defaults/autoconfig/ironfox.cfg":
                datos = datos.rstrip(b"\n") + ajustes.encode("utf-8")
                cambios.add("ajustes")
            elif nombre == "modules/GeckoViewStartup.sys.mjs":
                datos += ARRANQUE.encode("utf-8")
                cambios.add("arranque")
            elif (
                nombre.endswith("/branding/brand.ftl")
                or nombre.endswith("/branding/brand.properties")
                or nombre.endswith("/ironfox/ironfox.ftl")
            ):
                datos = sin_marca_ftl(datos.decode("utf-8")).encode("utf-8")
                cambios.add("marca")
            destino.writestr(info, datos, compress_type=info.compress_type)
    if cambios != {"ajustes", "arranque", "marca"}:
        raise SystemExit(f"reempaquetar.py: omni.ja no tiene lo esperado (solo {sorted(cambios)})")
    omni.write_bytes(salida.getvalue())


# ── Extensión de Velbrum ───────────────────────────────────────────────────
def copiar_extension(carpeta, recursos):
    """android/extension con lo que comparte con la extensión de la PC (los
    avisos de las tiendas, la tabla de equivalentes y la capa de
    compatibilidad de host/compat) y sus íconos."""
    destino = carpeta / "assets/extensions/velbrum"
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(AQUI / "extension", destino)
    for archivo in ("aviso.js", "tienda.js", "edge.js", "equivalentes.json"):
        shutil.copy(RAIZ / "extension" / archivo, destino / archivo)
    shutil.copytree(RAIZ / "host/compat", destino / "compat",
                    ignore=shutil.ignore_patterns("*.before-*", "__pycache__"))
    (destino / "iconos").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for lado in (48, 96):
            dibujar(svg_logo(), lado, lado, destino / f"iconos/velbrum-{lado}.png", tmp)

    # Las listas de la conversión, de host/extensiones_chrome.py.
    especificacion = importlib.util.spec_from_file_location("extensiones_chrome", RAIZ / "host/extensiones_chrome.py")
    conversor = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(conversor)
    tablas = {
        nombre: sorted(valor) if isinstance(valor, (set, frozenset, tuple)) else valor
        for nombre in ("SIN_EQUIVALENTE", "EMULADOS", "SOLO_OPCIONALES", "CLAVES_DE_CHROME", "APIS_SIN_EQUIVALENTE",
                       "ARCHIVOS_COMPAT", "VERSION_COMPAT", "CAPA_CSS", "MAXIMO_DESCARGA", "MAXIMO_DESCOMPRIMIDO",
                       "MAXIMO_ARCHIVOS")
        for valor in [getattr(conversor, nombre)]
    }
    tablas["ARCHIVOS_COMPAT"] = list(conversor.ARCHIVOS_COMPAT)  # en orden
    (destino / "tablas.json").write_text(json.dumps(tablas, indent=1), encoding="utf-8")

    # Para buscar versiones nuevas (actualizar.js): la de este APK y su
    # arquitectura, que elige qué APK bajar.
    abis = [d.name for d in (carpeta / "lib").iterdir() if d.is_dir()]
    if len(abis) != 1:
        raise SystemExit(f"reempaquetar.py: se esperaba un APK de una sola arquitectura, no {abis}")
    (destino / "actualizar.json").write_text(json.dumps(
        {"version": VERSION_VELBRUM, "abi": abis[0], "repositorio": VERSIONES["REPOSITORIO"]}, indent=1), encoding="utf-8")

    for archivo, reemplazos in (
        ("manifest.json", {"@version@": VERSION_VELBRUM}),
        ("convertir.js", {"@versionChromium@": version_chrome()}),
    ):
        ruta = destino / archivo
        contenido = ruta.read_text(encoding="utf-8")
        for de, a in reemplazos.items():
            if de not in contenido:
                raise SystemExit(f"reempaquetar.py: falta {de} en {archivo}")
            contenido = contenido.replace(de, a)
        ruta.write_text(contenido, encoding="utf-8")


def version_chrome():
    """La versión estable de Chrome: el conversor la manda al pedir
    extensiones (como portable/compilar.py)."""
    url = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions?pageSize=1"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)["versions"][0]["version"]
    except (OSError, ValueError, KeyError, IndexError):
        print(f"reempaquetar.py: no pude consultar la versión de Chrome; uso {CHROME_POR_DEFECTO}")
        return CHROME_POR_DEFECTO


# ── Armar y firmar ─────────────────────────────────────────────────────────
def firmar(sin_firma, salida, clave, trabajo):
    alineado = trabajo / "alineado.apk"
    # -P 16: bibliotecas alineadas a páginas de 16 KB (Android 15+).
    correr("zipalign", "-f", "-P", "16", "4", sin_firma, alineado)
    de_prueba = clave is None
    if not de_prueba:
        # Sin la variable, apksigner pide la frase en la terminal.
        frase = ["--ks-pass", "env:VELBRUM_ANDROID_FRASE"] if os.environ.get("VELBRUM_ANDROID_FRASE") else []
    else:
        clave = trabajo / "clave-de-prueba.p12"
        if not clave.exists():
            correr("keytool", "-genkeypair", "-keystore", clave, "-storetype", "PKCS12",
                   "-storepass", "prueba", "-alias", "prueba", "-keyalg", "RSA", "-keysize", "3072",
                   "-validity", "3650", "-dname", "CN=Velbrum prueba")
        frase = ["--ks-pass", "pass:prueba"]
        print("AVISO: firmado con una clave de prueba; no publicar este APK", file=sys.stderr)
    # Sin la firma v4 (un .idsig aparte, solo para instalar por adb de a partes).
    correr("apksigner", "sign", "--ks", clave, "--ks-type", "PKCS12", *frase, "--v4-signing-enabled", "false",
           "--out", salida, alineado)
    correr("apksigner", "verify", "--print-certs", salida)
    # Con la clave de Velbrum, tiene que ser el certificado publicado
    # (versiones.env), no otro (un secreto equivocado en GitHub, por ejemplo).
    esperado = VERSIONES.get("VELBRUM_CERTIFICADO")
    if not de_prueba and esperado:
        salida_verify = subprocess.run(["apksigner", "verify", "--print-certs", str(salida)],
                                       capture_output=True, text=True, check=True).stdout
        firmantes = re.findall(r"certificate SHA-256 digest: ([0-9a-f]{64})", salida_verify)
        if firmantes != [esperado]:
            raise SystemExit(f"reempaquetar.py: la clave no es la de Velbrum ({firmantes}, se esperaba {esperado})")
        print("certificado de Velbrum correcto")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--apk", required=True, type=Path, help="APK oficial de IronFox (verificado por bajar.sh)")
    p.add_argument("--salida", required=True, type=Path)
    p.add_argument("--clave", type=Path, help="almacén PKCS#12 con la clave de firma de Velbrum")
    p.add_argument("--trabajo", type=Path, help="carpeta de trabajo (por defecto, una temporal)")
    p.add_argument("--version", help="otra versión de Velbrum que la de VERSION (para probar el actualizador)")
    args = p.parse_args()
    if args.version:
        global VERSION_VELBRUM
        VERSION_VELBRUM = args.version

    temporal = None
    if args.trabajo:
        trabajo = args.trabajo.resolve()
        trabajo.mkdir(parents=True, exist_ok=True)
    else:
        temporal = tempfile.TemporaryDirectory()
        trabajo = Path(temporal.name)
    carpeta = trabajo / "desarmado"
    correr("apktool", "d", "-s", "-f", "-o", carpeta, args.apk.resolve())
    cambiar_paquete(carpeta)
    cambiar_textos(carpeta)
    cambiar_iconos(carpeta)
    cambiar_omni(carpeta)
    copiar_extension(carpeta, trabajo)
    sin_firma = trabajo / "sin-firma.apk"
    correr("apktool", "b", "-f", "-o", sin_firma, carpeta)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    firmar(sin_firma, args.salida.resolve(), args.clave and args.clave.resolve(), trabajo)
    print(f"listo: {args.salida}")
    if temporal:
        temporal.cleanup()


if __name__ == "__main__":
    main()
