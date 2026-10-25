"""Cambia «LibreWolf» por «Velbrum» en los textos de los omni.ja de LibreWolf.

Se usa al compilar (default.nix), sobre los omni.ja ya descomprimidos. Solo
toca archivos de traducción (.ftl, .properties, .dtd), nunca código. La marca
(brand.ftl, brand.properties) se reemplaza entera por la de esta carpeta, y la
descripción de «Acerca de Velbrum» por una propia.

Uso: python3 -I textos.py CARPETA_MARCA CARPETA_OMNI...
"""
import pathlib
import re
import shutil
import sys

ACERCA = "Navegador privado basado en Firefox, con la protección de Mullvad Browser y extensiones de Chrome."

marca, *omnis = (pathlib.Path(a) for a in sys.argv[1:])
cambios = 0
for omni in omnis:
    for propio, destino in (
        ("brand.ftl", "localization/en-US/branding/brand.ftl"),
        ("brand.properties", "chrome/en-US/locale/branding/brand.properties"),
    ):
        if (omni / destino).is_file():
            shutil.copyfile(marca / propio, omni / destino)
            cambios += 1

    archivos = list(omni.glob("localization/en-US/**/*.ftl"))
    archivos += [p for p in omni.glob("chrome/en-US/locale/**/*") if p.suffix in (".properties", ".dtd")]
    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8")
        nuevo = re.sub(r"(?m)^about-librewolf = .*$", f"about-librewolf = {ACERCA}", texto)
        nuevo = nuevo.replace("LibreWolf", "Velbrum")
        if nuevo != texto:
            cambios += texto.count("LibreWolf") or 1
            archivo.write_text(nuevo, encoding="utf-8")

if not (omnis[0] / "localization/en-US/branding/brand.ftl").is_file():
    print("textos.py: AVISO: no encontré la marca de LibreWolf en omni.ja; revisá marca/textos.py")
print(f"textos.py: {cambios} textos cambiados a Velbrum")
