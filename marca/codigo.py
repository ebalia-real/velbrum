"""Cambios de código en los omni.ja de LibreWolf (se usa al compilar).

- LibreWolf borra todos los paquetes de idioma en cada arranque
  (BrowserGlue.sys.mjs, «removeLangpacks»): sus versiones oficiales traen
  todos los idiomas, pero la de nixpkgs solo trae inglés, y el paquete con la
  marca de Bruma (marca/idioma.py) se borraría siempre.
- «Acerca de»: el nombre, el logo del lobo, el azul de LibreWolf y el enlace a
  librewolf.net pasan a ser los de Bruma.
- La carpeta de copias de seguridad («Restore LibreWolf») y el nombre que
  muestra about:support.
- El botón «Bruma» de la barra de herramientas, con los interruptores de
  bordes y firmas (marca/ajustes-bruma.sys.mjs).
- La barra de pestañas: sin el espacio vacío de 40 px que Firefox deja antes
  de la primera pestaña en las ventanas sin maximizar (la pestaña queda
  alineada con el borde y el botón «atrás»; la ventana se sigue arrastrando
  desde la parte vacía de la barra).

Si una versión nueva de LibreWolf cambia alguno de estos archivos, se avisa en
el registro de compilación (AVISO) pero no se corta la compilación, para no
trabar las actualizaciones del sistema.

Uso: python3 -I codigo.py CARPETA_OMNI_BROWSER CARPETA_OMNI_TOOLKIT
"""
import pathlib
import re
import sys

browser, toolkit = (pathlib.Path(a) for a in sys.argv[1:3])
avisos = 0


def cambiar(archivo, patron, reemplazo, que):
    global avisos
    try:
        codigo = archivo.read_text(encoding="utf-8")
    except OSError:
        codigo = ""
    nuevo, n = re.subn(patron, reemplazo, codigo)
    if n:
        archivo.write_text(nuevo, encoding="utf-8")
        print(f"codigo.py: {que}")
    else:
        avisos += 1
        print(f"codigo.py: AVISO: no pude cambiar {que} ({archivo.name}); revisá marca/codigo.py")


cambiar(
    browser / "modules/BrowserGlue.sys.mjs",
    r"\n[ \t]*removeLangpacks\(\)\.catch\(err => \{\n[^}]*\}\);\n",
    "\n    // Bruma: los paquetes de idioma no se borran (ver marca/codigo.py).\n",
    "LibreWolf ya no borra los paquetes de idioma",
)

dialogo = browser / "chrome/browser/content/browser/aboutDialog.xhtml"
cambiar(dialogo, r'<label id="wordmark">[^<]*</label>', '<label id="wordmark">Bruma</label>', "nombre en «Acerca de»")
cambiar(dialogo, r'\n[ \t]*<label id="websiteLink"[^\n]*</label>', "", "sin enlace a librewolf.net en «Acerca de»")

estilo = browser / "chrome/browser/content/browser/aboutDialog.css"
cambiar(estilo, r'url\("data:image/svg\+xml;base64,[^"]*"\)', 'url("chrome://branding/content/about-logo.svg")', "logo de Bruma en «Acerca de»")
cambiar(estilo, r"#00acff", "#8573ff", "color de Bruma en «Acerca de»")

cambiar(
    browser / "modules/backup/BackupService.sys.mjs",
    r'"Restore LibreWolf"',
    '"Restaurar Bruma"',
    "carpeta de copias de seguridad",
)
cambiar(
    toolkit / "modules/Troubleshoot.sys.mjs",
    r"name: Services\.appinfo\.name,",
    'name: "Bruma",',
    "nombre en about:support",
)

cambiar(
    browser / "chrome/browser/skin/classic/browser/browser-shared.css",
    r"\n\.titlebar-spacer \{\n",
    '\n/* Bruma: sin espacio vacío antes de la primera pestaña (ver marca/codigo.py). */\n'
    '.titlebar-spacer[type="pre-tabs"] {\n  display: none !important;\n}\n\n.titlebar-spacer {\n',
    "barra de pestañas alineada (sin el espacio antes de la primera pestaña)",
)

# El botón «Bruma» de la barra de herramientas (marca/ajustes-bruma.sys.mjs,
# que default.nix copia en omni.ja antes de correr este script).
cambiar(
    browser / "chrome/browser/content/browser/browser-main.js",
    r"(\nwindow\.onload = gBrowserInit\.onLoad\.bind\(gBrowserInit\);\n)",
    r"""\1
// Bruma: botón «Bruma» con los ajustes de Bruma (ver marca/codigo.py).
try {
  ChromeUtils.importESModule("chrome://browser/content/ajustes-bruma.sys.mjs").iniciar(window);
} catch (error) {
  console.error("Bruma: no pude cargar el botón de ajustes", error);
}
""",
    "botón «Bruma» con los ajustes en la barra de herramientas",
)

print(f"codigo.py: listo ({avisos} avisos)")
