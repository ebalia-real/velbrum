"""Arma Velbrum para Windows, macOS o Linux sin Nix sobre la versión oficial de
LibreWolf de ese sistema (lo mismo que hace default.nix en NixOS):

- la marca de Velbrum en los dos omni.ja (íconos, «Acerca de», textos en todos
  los idiomas, el botón «Velbrum»: marca/textos.py y marca/codigo.py);
- los ajustes de Velbrum (gecko/ajustes.cfg) al final de librewolf.cfg;
- las políticas (sin el menú de ayuda de LibreWolf, la extensión de las
  tiendas también en ventanas privadas);
- la extensión de las tiendas (extension/), el host de mensajería nativa y el
  conversor de extensiones de Chrome (PyInstaller), Tor y el lanzador;
- en Linux, las fuentes de Mullvad Browser.

Uso:
  python3 -I portable/empaquetar.py --sistema linux|windows|macos
      --navegador DIR      LibreWolf descomprimido (carpeta con librewolf o
                           librewolf.exe; en macOS, LibreWolf.app)
      --tor DIR            Tor Expert Bundle descomprimido
      --lanzador DIR       PyInstaller: carpeta del lanzador (portable/velbrum.py)
      --host DIR           PyInstaller: carpeta del host (host/host-extensiones.py)
      --recursos DIR       salida de portable/recursos.sh
      [--mullvad DIR]      Linux: Mullvad Browser descomprimido (la carpeta
                           con fonts/ y browser/omni.ja): sus fuentes y sus
                           preferencias de fuentes por idioma
      --salida DIR         ahí queda Velbrum/ (o Velbrum.app en macOS)
"""
import argparse
import json
import pathlib
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

AQUI = pathlib.Path(__file__).resolve().parent.parent
MARCA = AQUI / "marca"
DOMINIOS_LOCALES = ["lan", "home", "home.arpa", "internal", "localdomain"]
ARCHIVOS_COMPAT = ("fondo.js", "pagina.js", "contenido.js", "permisos.html", "permisos.js")
ARCHIVOS_EXTENSION = ("manifest.json", "background.js", "tienda.js", "edge.js", "aviso.js", "equivalentes.json")


def copiar_arbol(origen, destino):
    shutil.copytree(origen, destino, symlinks=True, dirs_exist_ok=True)
    # Lo que viene de solo lectura (por ejemplo del store de Nix) se tiene que
    # poder modificar acá.
    for ruta in [pathlib.Path(destino), *pathlib.Path(destino).rglob("*")]:
        if not ruta.is_symlink():
            ruta.chmod(ruta.stat().st_mode | 0o200)


def extraer(omni, carpeta):
    with zipfile.ZipFile(omni) as z:
        nombres = z.namelist()
        z.extractall(carpeta)
    archivos = sum(1 for p in pathlib.Path(carpeta).rglob("*") if p.is_file())
    if archivos != len([n for n in nombres if not n.endswith("/")]):
        sys.exit(f"empaquetar: {omni}: faltan archivos al descomprimir")


def comprimir(carpeta, omni):
    carpeta = pathlib.Path(carpeta)
    with zipfile.ZipFile(omni, "w", zipfile.ZIP_DEFLATED) as z:
        for ruta in sorted(carpeta.rglob("*")):
            if ruta.is_file():
                z.write(ruta, ruta.relative_to(carpeta).as_posix())


def marca_en_omni(resources, recursos):
    """Los dos omni.ja: browser/omni.ja (navegador) y omni.ja (general)."""
    with tempfile.TemporaryDirectory() as tmp:
        omni, general = pathlib.Path(tmp, "omni"), pathlib.Path(tmp, "general")
        extraer(resources / "browser" / "omni.ja", omni)
        extraer(resources / "omni.ja", general)

        b = omni / "chrome/browser/content/branding"
        if not (b / "icon32.png").is_file():
            sys.exit("empaquetar: no encontré la marca de LibreWolf en browser/omni.ja")
        for archivo in (recursos / "branding").iterdir():
            shutil.copyfile(archivo, b / archivo.name)
        shutil.copyfile(MARCA / "nombre.svg", b / "firefox-wordmark.svg")
        shutil.copyfile(MARCA / "nombre.svg", b / "about-wordmark.svg")
        for destino, origen in (
            ("chrome/browser/skin/classic/browser/preferences/category-librewolf.svg", MARCA / "simbolo.svg"),
            ("chrome/browser/skin/classic/browser/sidebar/firefox.svg", AQUI / "iconos/velbrum-chico.svg"),
            ("chrome/devtools/skin/images/aboutdebugging-firefox-librewolf.svg", AQUI / "iconos/velbrum.svg"),
        ):
            if (omni / destino).parent.is_dir():
                shutil.copyfile(origen, omni / destino)

        subprocess.run([sys.executable, "-I", str(MARCA / "textos.py"), str(MARCA), str(omni), str(general)], check=True)
        shutil.copyfile(MARCA / "ajustes-velbrum.sys.mjs", omni / "chrome/browser/content/browser/ajustes-velbrum.sys.mjs")
        subprocess.run([sys.executable, "-I", str(MARCA / "codigo.py"), str(omni), str(general)], check=True)

        comprimir(omni, resources / "browser" / "omni.ja")
        comprimir(general, resources / "omni.ja")

    iconos = resources / "browser" / "chrome" / "icons" / "default"
    if iconos.is_dir():
        for archivo in (recursos / "ventana").iterdir():
            shutil.copyfile(archivo, iconos / archivo.name)


def fuentes_mullvad_cfg(mullvad):
    """Qué fuente usa cada idioma y la lista de fuentes permitidas, tal cual
    Mullvad Browser (como fuentesMullvadCfg en default.nix)."""
    with zipfile.ZipFile(mullvad / "browser" / "omni.ja") as z:
        texto = z.read("defaults/preferences/001-base-profile.js").decode("utf-8")
    lineas = [re.sub(r"^pref\(", "defaultPref(", l) for l in texto.splitlines() if l.startswith('pref("font.')]
    if len(lineas) < 50 or not any('"font.system.whitelist"' in l for l in lineas):
        sys.exit("empaquetar: no encontré las preferencias de fuentes de Mullvad Browser")
    return "\n/** [SECTION] FUENTES DE MULLVAD BROWSER (por idioma) */\n" + "\n".join(lineas) + "\n"


def ajustes(resources, mullvad):
    """gecko/ajustes.cfg (y en Linux las fuentes de Mullvad) al final de
    librewolf.cfg, como hace wrapFirefox en NixOS."""
    cfg = resources / "librewolf.cfg"
    if not cfg.is_file():
        sys.exit("empaquetar: no encontré librewolf.cfg")
    partes = [cfg.read_text(encoding="utf-8"), "\n\n/** ════════ VELBRUM ════════ */\n",
              (AQUI / "gecko/ajustes.cfg").read_text(encoding="utf-8")]
    if mullvad:
        partes.append(fuentes_mullvad_cfg(mullvad))
    partes.append(f'\ndefaultPref("network.trr.excluded-domains", {json.dumps(",".join(DOMINIOS_LOCALES))});\n')
    cfg.write_text("".join(partes), encoding="utf-8")


def politicas(resources):
    ruta = resources / "distribution" / "policies.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    p = datos.setdefault("policies", {})
    p.pop("SupportMenu", None)
    extensiones = p.setdefault("ExtensionSettings", {})
    todas = extensiones.setdefault("*", {})
    todas["allowed_types"] = ["dictionary", "extension", "locale", "sitepermission", "theme"]
    todas["blocked_install_message"] = "Velbrum no permite instalar este complemento."
    extensiones["chrome@velbrum"] = {"private_browsing": True}
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    (resources / "distribution" / "distribution.ini").unlink(missing_ok=True)
    if "librewolf" in json.dumps(p).lower():
        print("empaquetar: AVISO: las políticas todavía nombran a LibreWolf")


def extension(resources, recursos):
    """La extensión de las tiendas, como complemento de distribución: las
    versiones oficiales de LibreWolf no cargan complementos sueltos de la
    carpeta de la aplicación (browser/extensions, como en NixOS), pero sí
    instalan en el perfil los de distribution/extensions la primera vez. Las
    versiones nuevas las copia el lanzador (portable/velbrum.py)."""
    destino = resources / "distribution" / "extensions"
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino / "chrome@velbrum.xpi", "w", zipfile.ZIP_DEFLATED) as z:
        for nombre in ARCHIVOS_EXTENSION:
            z.write(AQUI / "extension" / nombre, nombre)
        for t in (48, 96):
            z.write(recursos / "hicolor" / f"velbrum-{t}.png", f"iconos/velbrum-{t}.png")


def host(destino, host_dir):
    copiar_arbol(host_dir, destino)
    compat = destino / "compat"
    compat.mkdir(exist_ok=True)
    for nombre in ARCHIVOS_COMPAT:
        shutil.copyfile(AQUI / "host" / "compat" / nombre, compat / nombre)
    shutil.copyfile(AQUI / "extension" / "equivalentes.json", destino / "equivalentes.json")


def tor(destino, tor_dir):
    for parte in ("tor", "data", "docs"):
        if (tor_dir / parte).exists():
            copiar_arbol(tor_dir / parte, destino / parte)
    if not any((destino / "tor").glob("tor*")):
        sys.exit("empaquetar: el Tor Expert Bundle no trae tor")


def fuentes(destino, mullvad):
    """Las fuentes de Mullvad Browser con su fonts.conf, que las busca en su
    misma carpeta (prefix="relative", como Tor Browser): así funciona en
    cualquier lugar y los procesos de las páginas, que no pueden leer la
    carpeta personal, las encuentran."""
    copiar_arbol(mullvad / "fonts", destino)
    conf = destino / "fonts.conf"
    texto = conf.read_text(encoding="utf-8")
    texto, n = re.subn(r"<dir[^>]*>[^<]*</dir>", '<dir prefix="relative">.</dir>', texto)
    if n != 1:
        sys.exit("empaquetar: el fonts.conf de Mullvad Browser cambió; revisá portable/empaquetar.py")
    conf.write_text(texto, encoding="utf-8")


def permisos_normales(raiz):
    """Carpetas 755, archivos 644 y ejecutables 755, como un paquete de distro:
    lo que viene de afuera (Tor trae carpetas 700) tiene que poder usarlo
    cualquier usuario de la PC."""
    for ruta in [raiz, *raiz.rglob("*")]:
        if ruta.is_symlink():
            continue
        if ruta.is_dir():
            ruta.chmod(0o755)
        else:
            ruta.chmod(0o755 if ruta.stat().st_mode & 0o100 else 0o644)


def info_plist(app, version):
    ruta = app / "Contents" / "Info.plist"
    with open(ruta, "rb") as f:
        info = plistlib.load(f)
    info.update({
        "CFBundleName": "Velbrum",
        "CFBundleDisplayName": "Velbrum",
        "CFBundleExecutable": "velbrum",
        "CFBundleIconFile": "velbrum.icns",
        "CFBundleIdentifier": "io.github.ebalia-real.velbrum",
        "CFBundleShortVersionString": version,
        "CFBundleGetInfoString": f"Velbrum {version}",
    })
    with open(ruta, "wb") as f:
        plistlib.dump(info, f)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--sistema", choices=("linux", "windows", "macos"), required=True)
    for opcion in ("navegador", "tor", "lanzador", "host", "recursos", "salida"):
        a.add_argument(f"--{opcion}", required=True, type=pathlib.Path)
    a.add_argument("--mullvad", type=pathlib.Path)
    args = a.parse_args()
    version = (AQUI / "VERSION").read_text().strip()

    args.salida.mkdir(parents=True, exist_ok=True)
    if args.sistema == "macos":
        app = args.salida / "Velbrum.app"
        shutil.rmtree(app, ignore_errors=True)
        copiar_arbol(args.navegador, app)
        shutil.rmtree(app / "Contents" / "_CodeSignature", ignore_errors=True)
        resources = app / "Contents" / "Resources"
        programa = app / "Contents" / "MacOS"
        recursos_velbrum = resources / "velbrum"
        shutil.copyfile(args.recursos / "velbrum.icns", resources / "velbrum.icns")
        info_plist(app, version)
    else:
        raiz = args.salida / "Velbrum"
        shutil.rmtree(raiz, ignore_errors=True)
        copiar_arbol(args.navegador, raiz / "navegador")
        resources = raiz / "navegador"
        programa = recursos_velbrum = raiz

    marca_en_omni(resources, args.recursos)
    mullvad = args.mullvad if args.sistema == "linux" else None
    ajustes(resources, mullvad)
    politicas(resources)
    extension(resources, args.recursos)
    host(recursos_velbrum / "host", args.host)
    tor(recursos_velbrum / "tor", args.tor)
    if mullvad:
        fuentes(resources / "fuentes", mullvad)
    if args.sistema == "macos":
        # En Contents/MacOS solo van ejecutables (si no, la firma de la app no
        # cierra): el lanzador de PyInstaller va en Resources y lo abre un script.
        copiar_arbol(args.lanzador, recursos_velbrum / "lanzador")
        script = programa / "velbrum"
        script.write_text('#!/bin/sh\nexec "$(dirname "$0")/../Resources/velbrum/lanzador/velbrum" "$@"\n')
        script.chmod(0o755)
    else:
        copiar_arbol(args.lanzador, programa)
    if args.sistema == "linux":
        shutil.copyfile(args.recursos / "hicolor" / "velbrum-256.png", programa / "velbrum.png")
    for nombre in ("LICENSE",):
        shutil.copyfile(AQUI / nombre, recursos_velbrum / f"{nombre}-velbrum.txt")
    if args.sistema != "windows":
        permisos_normales(app if args.sistema == "macos" else raiz)
    print(f"empaquetar: Velbrum {version} para {args.sistema} listo en {args.salida}")


if __name__ == "__main__":
    main()
