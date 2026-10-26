"""Prueba del actualizador de los paquetes (marca/actualizador-velbrum.sys.mjs,
portable/actualizar): la usa GitHub Actions en Windows, macOS y Linux (ver
.github/workflows/paquetes.yml).

Con un Velbrum armado (portable/empaquetar.py) prepara dos copias:
- la «instalada» (portable, con su carpeta de datos);
- una «versión nueva» 9999.01.01: la misma, con un archivo de marca, en el
  formato que se publica para ese sistema;
y sirve en 127.0.0.1 una versión publicada como la de GitHub (releases/latest)
con SHA256SUMS firmado con una clave de prueba (ssh-keygen), que reemplaza en
las dos copias a la clave de Velbrum.

Después, como un usuario: «Buscar actualizaciones» en el botón «Velbrum»,
«Instalar y reiniciar», «Reiniciar ahora». Revisa que Velbrum se cierre, que
el script ponga la versión nueva (con la marca) sin tocar los datos, y que
Velbrum vuelva a abrirse solo. Antes prueba que una firma de otra clave se
rechaza.

Con --iscc (Windows) prueba el Velbrum instalado con el instalador: arma con
Inno Setup el instalador de la instalada y el de la versión nueva, instala el
primero y la actualización corre el segundo. Usa la carpeta de datos del
usuario (%LOCALAPPDATA%\\Velbrum) y la borra: solo corre en GitHub Actions.

Uso: python portable/prueba-actualizacion.py --sistema linux|windows|macos --velbrum VELBRUM --trabajo DIR [--iscc ISCC.exe] [-- args...]
VELBRUM: la carpeta Velbrum (Linux, Windows) o Velbrum.app (macOS). Los args van
al navegador (por ejemplo --headless; Velbrum los conserva al reabrirse).
"""
import argparse
import hashlib
import http.server
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from prueba import PUERTO, conectar  # noqa: E402

AQUI = pathlib.Path(__file__).resolve().parent
REPO = "ebalia-real/velbrum"
NUEVA = "9999.01.01"


def nombre_paquete(sistema, version, instalador=False):
    if instalador:
        return f"velbrum-{version}-windows-x86_64-instalador.exe"
    if sistema == "linux":
        return f"velbrum-{version}-linux-x86_64-portable.tar.gz"
    if sistema == "windows":
        return f"velbrum-{version}-windows-x86_64-portable.zip"
    arq = "arm64" if subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip() == "arm64" else "x86_64"
    return f"velbrum-{version}-macos-{arq}-portable.zip"


def copiar(origen, destino):
    if sys.platform == "darwin":
        subprocess.run(["ditto", str(origen), str(destino)], check=True)
    else:
        shutil.copytree(origen, destino, symlinks=True)


def clave_de_prueba(trabajo, nombre):
    clave = trabajo / nombre
    for p in (clave, clave.with_suffix(".pub")):
        p.unlink(missing_ok=True)
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", nombre, "-f", str(clave)], check=True)
    return clave


def firmar(clave, archivo):
    firma = archivo.with_name(archivo.name + ".sig")
    firma.unlink(missing_ok=True)
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", "velbrum-paquetes", "-f", str(clave), str(archivo)], check=True)
    return firma


def poner_clave(recursos, clave):
    publica = clave.with_suffix(".pub").read_text().split()
    (recursos / "firmas" / "claves-permitidas").write_text(
        f'prueba namespaces="git,velbrum-paquetes" {publica[0]} {publica[1]}\n')


def comprimir(sistema, carpeta, salida):
    """carpeta: Velbrum/ (Linux, Windows) o «Velbrum Portable»/ (macOS)."""
    if sistema == "linux":
        with tarfile.open(salida, "w:gz") as t:
            t.add(carpeta, arcname="Velbrum")
    elif sistema == "windows":
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
            for ruta in sorted(carpeta.rglob("*")):
                z.write(ruta, pathlib.PurePosixPath("Velbrum", *ruta.relative_to(carpeta).parts))
    else:
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(carpeta), str(salida)], check=True)


def armar_instalador(iscc, velbrum, carpeta, version, salida):
    """El instalador de Windows de la carpeta, como en paquetes.yml (el .iss
    toma el ícono de la carpeta de al lado)."""
    shutil.copyfile(velbrum.parent / "velbrum.ico", carpeta.parent / "velbrum.ico")
    subprocess.run([str(iscc), "-Q", f"-DVersion={version}", f"-DOrigen={carpeta}", f"-DSalida={salida}",
                    str(AQUI / "windows" / "velbrum.iss")], check=True)
    return salida / nombre_paquete("windows", version, True)


class Servidor(http.server.SimpleHTTPRequestHandler):
    publicados = None
    version = NUEVA

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.publicados), **kwargs)

    def do_GET(self):
        if self.path == f"/repos/{REPO}/releases/latest":
            base = f"http://127.0.0.1:{self.server.server_address[1]}/"
            datos = {"tag_name": f"v{self.version}",
                     "assets": [{"name": p.name, "browser_download_url": base + p.name, "size": p.stat().st_size}
                                for p in sorted(self.publicados.iterdir())]}
            cuerpo = json.dumps(datos).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def paso(texto):
    print(f"[{time.strftime('%H:%M:%S')}] {texto}", flush=True)


# Los mensajes de Velbrum en la consola del navegador (para saber qué falló).
CONSOLA = """return Services.console.getMessageArray().map(m => m.message || String(m))
    .filter(t => /velbrum|actualiz/i.test(t)).slice(-30);"""


def principal_js(m, codigo):
    m.contexto("chrome")
    return m.js_async(codigo)


# La barra de actualización de la ventana principal y sus botones.
BARRA = """const v = Services.wm.getMostRecentWindow("navigator:browser");
    const n = v?.gNotificationBox.getNotificationWithValue("velbrum-actualizacion");
    if (!n) return null;
    const botones = [...n.querySelectorAll("button"), ...(n.shadowRoot ? n.shadowRoot.querySelectorAll("button") : [])];
    const etiqueta = b => b.label || b.textContent.trim();
"""


def leer_barra(m):
    return principal_js(m, BARRA + 'return {texto: n.messageText?.textContent || n.label || "", botones: botones.map(etiqueta)};')


def tocar_boton(m, nombre):
    r = principal_js(m, BARRA + f"""const b = botones.find(b => etiqueta(b) == {json.dumps(nombre)});
    if (!b) return "no está"; b.doCommand ? b.doCommand() : b.click(); return "ok";""")
    if r != "ok":
        raise SystemExit(f"FALLA: no encontré el botón «{nombre}» ({leer_barra(m)})")
    return r


def esperar_barra(m, contiene, segundos):
    limite = time.time() + segundos
    ultima = None
    while time.time() < limite:
        ultima = leer_barra(m)
        if ultima and contiene in ultima["texto"]:
            return ultima
        time.sleep(1)
    raise SystemExit(f"FALLA: no apareció «{contiene}» (última barra: {ultima})")


def buscar_actualizaciones(m):
    return principal_js(m, """const v = Services.wm.getMostRecentWindow("navigator:browser");
        v.focus();
        const {CustomizableUI} = ChromeUtils.importESModule("moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs");
        CustomizableUI.getWidget("velbrum-ajustes").forWindow(v).node.click();
        for (let i = 0; i < 50 && !v.document.getElementById("velbrum-ajustes-panel"); i++) await new Promise(r => v.setTimeout(r, 100));
        const panel = v.document.getElementById("velbrum-ajustes-panel");
        const b = [...panel.querySelectorAll("button")].find(b => b.getAttribute("label") == "Buscar actualizaciones");
        b.doCommand();
        await new Promise(r => v.setTimeout(r, 3000));
        const texto = panel.querySelector(".velbrum-version").textContent;
        panel.hidePopup();
        return texto;""")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--sistema", choices=("linux", "windows", "macos"), required=True)
    a.add_argument("--velbrum", type=pathlib.Path, required=True)
    a.add_argument("--trabajo", type=pathlib.Path, required=True)
    a.add_argument("--iscc", type=pathlib.Path)
    a.add_argument("extra", nargs=argparse.REMAINDER)
    args = a.parse_args()
    trabajo = args.trabajo.resolve()
    shutil.rmtree(trabajo, ignore_errors=True)
    trabajo.mkdir(parents=True)
    macos = args.sistema == "macos"
    instalador = bool(args.iscc)
    if instalador and not (args.sistema == "windows" and os.environ.get("GITHUB_ACTIONS")):
        raise SystemExit("--iscc solo en Windows y en GitHub Actions (borra los datos de Velbrum del usuario)")

    clave = clave_de_prueba(trabajo, "clave-prueba")
    otra = clave_de_prueba(trabajo, "otra-clave")

    # La instalada: portable, con su carpeta de datos (o con el instalador).
    publicados = trabajo / "publicados"
    publicados.mkdir()
    if instalador:
        raiz = trabajo / "instalada"
        copia = trabajo / "vieja" / "Velbrum"
        copiar(args.velbrum, copia)
        poner_clave(copia, clave)
        version = (AQUI.parent / "VERSION").read_text().strip()
        exe = armar_instalador(args.iscc, args.velbrum, copia, version, trabajo / "vieja")
        subprocess.run([str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", f"/DIR={raiz}"], check=True)
        shutil.rmtree(trabajo / "vieja")
        recursos = raiz
        lanzador = [str(raiz / "velbrum.exe")]
        marca = raiz / "ACTUALIZADA"
        datos = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Velbrum"
        shutil.rmtree(datos, ignore_errors=True)
    elif macos:
        raiz = trabajo / "instalada"
        raiz.mkdir()
        app = raiz / "Velbrum.app"
        copiar(args.velbrum, app)
        recursos = app / "Contents" / "Resources" / "velbrum"
        lanzador = [str(app / "Contents" / "MacOS" / "velbrum")]
        marca = recursos / "ACTUALIZADA"
    else:
        raiz = trabajo / "instalada"
        copiar(args.velbrum, raiz)
        recursos = raiz
        lanzador = [str(raiz / ("velbrum.exe" if args.sistema == "windows" else "velbrum"))]
        marca = raiz / "ACTUALIZADA"
    if not instalador:
        (raiz / "portable").touch()
        poner_clave(recursos, clave)
        datos = raiz / "datos"
    perfil = datos / "gecko"
    perfil.mkdir(parents=True)
    (perfil / "user.js").write_text(f'user_pref("marionette.port", {PUERTO});\nuser_pref("remote.prefs.recommended", false);\n')
    (datos / "no-borrar").write_text("datos del usuario")

    # La versión nueva: la misma, con la marca.
    armado = trabajo / "armado"
    armado.mkdir()
    if macos:
        carpeta = armado / "Velbrum Portable"
        carpeta.mkdir()
        copiar(args.velbrum, carpeta / "Velbrum.app")
        (carpeta / "portable").touch()
        recursos_nueva = carpeta / "Velbrum.app" / "Contents" / "Resources" / "velbrum"
    else:
        carpeta = armado / "Velbrum"
        copiar(args.velbrum, carpeta)
        (carpeta / "portable").touch()
        recursos_nueva = carpeta
    poner_clave(recursos_nueva, clave)
    (recursos_nueva / "ACTUALIZADA").write_text(NUEVA)
    if macos:
        # La marca invalida el sello de la firma ad hoc: se vuelve a firmar.
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(carpeta / "Velbrum.app")], check=True)
    if instalador:
        (carpeta / "portable").unlink()
        paquete = armar_instalador(args.iscc, args.velbrum, carpeta, NUEVA, publicados)
    else:
        paquete = publicados / nombre_paquete(args.sistema, NUEVA)
        comprimir(args.sistema, carpeta, paquete)
    shutil.rmtree(armado)
    sumas = publicados / "SHA256SUMS"
    sumas.write_text(f"{hashlib.sha256(paquete.read_bytes()).hexdigest()}  {paquete.name}\n")

    # Primero con la firma de otra clave: se tiene que rechazar.
    firmar(otra, sumas)
    Servidor.publicados = publicados
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Servidor)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    env = dict(os.environ, VELBRUM_SERVIDOR_ACTUALIZACIONES=f"http://127.0.0.1:{servidor.server_address[1]}")

    proceso = subprocess.Popen([*lanzador, "--marionette", "--remote-allow-system-access", *[x for x in args.extra if x != "--"]], env=env)
    m = conectar(PUERTO)
    res = {}
    try:
        time.sleep(3)
        paso("Buscar actualizaciones")
        res["buscar"] = buscar_actualizaciones(m)
        esperar_barra(m, f"Hay una versión nueva de Velbrum ({NUEVA})", 30)
        paso("Instalar y reiniciar (firmada con otra clave)")
        res["instalar_otra_clave"] = tocar_boton(m, "Instalar y reiniciar")
        res["otra_clave"] = esperar_barra(m, "No se pudo actualizar", 120)["texto"]
        paso(res["otra_clave"])
        if "clave de Velbrum" not in res["otra_clave"]:
            raise SystemExit(f"FALLA: con otra clave: {res['otra_clave']}")

        # Ahora bien firmada.
        firmar(clave, sumas)
        paso("Intentar de nuevo (bien firmada)")
        res["reintentar"] = tocar_boton(m, "Intentar de nuevo")
        res["lista"] = esperar_barra(m, "está lista", 600)["texto"]
        paso(res["lista"])
        if marca.exists():
            raise SystemExit("FALLA: la versión nueva se instaló antes de cerrar Velbrum")
        paso("Reiniciar ahora")
        res["reiniciar"] = tocar_boton(m, "Reiniciar ahora")
    except BaseException:
        try:
            res["consola"] = principal_js(m, CONSOLA)
        except Exception:  # noqa: BLE001
            pass
        print(json.dumps(res, ensure_ascii=False, indent=1))
        try:
            m.contexto("chrome")
            m.cmd("Marionette:Quit", {"flags": ["eForceQuit"]})
        except Exception:  # noqa: BLE001
            pass
        raise

    # Velbrum se cierra, el script pone la versión nueva y lo vuelve a abrir.
    paso("Esperando que Velbrum se cierre y se instale la versión nueva")
    try:
        proceso.wait(120)
    except subprocess.TimeoutExpired:
        raise SystemExit("FALLA: Velbrum no se cerró")
    limite = time.time() + 300
    while not marca.exists() and time.time() < limite:
        time.sleep(1)
    actualizacion = datos / "actualizacion"
    res["registro"] = (actualizacion / "registro.txt").read_text(errors="replace") if (actualizacion / "registro.txt").exists() else ""
    if not marca.exists():
        print(json.dumps(res, ensure_ascii=False, indent=1))
        raise SystemExit("FALLA: no se instaló la versión nueva")
    if (datos / "no-borrar").read_text() != "datos del usuario":
        raise SystemExit("FALLA: se tocaron los datos")
    paso("Versión nueva instalada; esperando que Velbrum vuelva a abrirse")
    m = conectar(PUERTO, 180)
    try:
        # Al volver a abrir lee «resultado» y borra la carpeta de la actualización.
        limite = time.time() + 60
        while actualizacion.exists() and time.time() < limite:
            time.sleep(1)
        res["carpeta_actualizacion_borrada"] = not actualizacion.exists()
        m.contexto("chrome")
        res["ventanas"] = m.js("return [...Services.wm.getEnumerator('navigator:browser')].length")
    finally:
        try:
            m.contexto("chrome")
            m.cmd("Marionette:Quit", {"flags": ["eForceQuit"]})
        except Exception:  # noqa: BLE001
            pass
    servidor.shutdown()
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if not res["carpeta_actualizacion_borrada"] or not res["ventanas"]:
        raise SystemExit("FALLA: Velbrum no volvió a abrir bien")
    print("Todo bien: Velbrum se actualizó y volvió a abrir.")


if __name__ == "__main__":
    main()
