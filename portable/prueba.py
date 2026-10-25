"""Prueba de arranque de un paquete de Velbrum (la usa GitHub Actions en
Windows, macOS y Linux; ver .github/workflows/paquetes.yml).

Abre el Velbrum empaquetado con Marionette y revisa:
- los ajustes de Velbrum (resistFingerprinting, bordes, DNS cifrado);
- la marca (la ventana se llama Velbrum) y el botón «Velbrum»;
- la extensión de las tiendas (chrome@velbrum) activa;
- el host de mensajería nativa: responde y está registrado;
- en la Chrome Web Store, el botón «Agregar a Velbrum» y el aviso de la
  versión oficial para Firefox (Dark Reader la tiene); con --conversion,
  además, que convertir la de Chrome llegue al cartel de instalación.

Uso: python portable/prueba.py --datos CARPETA --host PROGRAMA_HOST [--conversion] -- LANZADOR [args...]
CARPETA es la carpeta de datos de Velbrum (en la versión portable, «datos»
junto al programa). Sale con error si algo obligatorio falla.
"""
import argparse
import json
import pathlib
import socket
import struct
import subprocess
import sys
import time

PUERTO = 2828 + 11


class Marionette:
    def __init__(self, puerto):
        self.s = socket.create_connection(("127.0.0.1", puerto), timeout=120)
        self.n = 0
        self._leer()
        self.cmd("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {"acceptInsecureCerts": False}}})

    def _leer(self):
        largo = b""
        while not largo.endswith(b":"):
            largo += self.s.recv(1)
        largo = int(largo[:-1])
        datos = b""
        while len(datos) < largo:
            datos += self.s.recv(largo - len(datos))
        return json.loads(datos)

    def cmd(self, nombre, params=None):
        self.n += 1
        mensaje = json.dumps([0, self.n, nombre, params or {}]).encode()
        self.s.sendall(str(len(mensaje)).encode() + b":" + mensaje)
        while True:
            r = self._leer()
            if r[0] == 1 and r[1] == self.n:
                if r[2]:
                    raise RuntimeError(r[2])
                return r[3]

    def js(self, codigo, *args):
        return self.cmd("WebDriver:ExecuteScript", {"script": codigo, "args": list(args)}).get("value")

    def js_async(self, codigo):
        envuelto = "const done = arguments[arguments.length - 1]; (async () => {" + codigo + "})().then(done, e => done('ERROR ' + e));"
        return self.cmd("WebDriver:ExecuteAsyncScript", {"script": envuelto}).get("value")

    def contexto(self, c):
        self.cmd("Marionette:SetContext", {"value": c})

    def clic(self, x, y):
        self.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "raton", "parameters": {"pointerType": "mouse"},
                 "actions": [{"type": "pointerMove", "x": int(x), "y": int(y), "origin": "viewport"},
                             {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]}]})
        self.cmd("WebDriver:ReleaseActions")


def conectar(puerto, segundos=180):
    limite = time.time() + segundos
    while True:
        try:
            return Marionette(puerto)
        except OSError:
            if time.time() > limite:
                raise
            time.sleep(2)


def probar_host(programa):
    mensaje = json.dumps({"accion": "nada"}).encode()
    r = subprocess.run([programa], input=struct.pack("@I", len(mensaje)) + mensaje, capture_output=True, timeout=120)
    return json.loads(r.stdout[4:]) if len(r.stdout) > 4 else {"salida": r.stdout.decode(errors="replace"), "error": r.stderr.decode(errors="replace")[-500:]}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--datos", type=pathlib.Path, required=True)
    a.add_argument("--host", required=True)
    a.add_argument("--conversion", action="store_true")
    a.add_argument("lanzador", nargs=argparse.REMAINDER)
    args = a.parse_args()
    comando = args.lanzador[1:] if args.lanzador[:1] == ["--"] else args.lanzador

    perfil = args.datos / "gecko"
    perfil.mkdir(parents=True, exist_ok=True)
    (perfil / "user.js").write_text(f'user_pref("marionette.port", {PUERTO});\nuser_pref("remote.prefs.recommended", false);\n')

    res, fallas = {}, []
    res["host"] = probar_host(args.host)
    if res["host"].get("error") != "pedido inválido":
        fallas.append("el host de mensajería nativa no responde")

    proceso = subprocess.Popen([*comando, "--marionette", "--remote-allow-system-access"])
    m = conectar(PUERTO)
    try:
        m.contexto("chrome")
        res["ajustes"] = m.js("""return {rfp: Services.prefs.getBoolPref("privacy.resistFingerprinting"),
            bordes: Services.prefs.getBoolPref("privacy.resistFingerprinting.letterboxing"),
            doh: Services.prefs.getStringPref("network.trr.uri", "")}""")
        if not (res["ajustes"]["rfp"] and res["ajustes"]["bordes"] and "quad9" in res["ajustes"]["doh"]):
            fallas.append("faltan los ajustes de Velbrum")
        res["marca"] = m.js("""return [document.title, Boolean(document.getElementById("velbrum-ajustes")
            || CustomizableUI.getWidget("velbrum-ajustes"))]""")
        if "Velbrum" not in res["marca"][0] or not res["marca"][1]:
            fallas.append("falta la marca o el botón «Velbrum»")
        for _ in range(30):
            res["extensiones"] = m.js_async("""const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
                return (await AddonManager.getAllAddons()).filter(a => a.type == "extension" && a.isActive).map(a => a.id)""")
            if "chrome@velbrum" in res["extensiones"]:
                break
            time.sleep(2)
        if "chrome@velbrum" not in res["extensiones"]:
            fallas.append("la extensión de las tiendas no está activa")

        m.contexto("content")
        m.cmd("WebDriver:Navigate", {"url": "https://chromewebstore.google.com/detail/eimadpbcbfnmbkopoojfekhnkhdbieeh"})
        botones = []
        for _ in range(20):
            time.sleep(1)
            botones = m.js("return [...document.querySelectorAll('button')].filter(b => b.dataset.velbrum).map(b => b.getBoundingClientRect().toJSON())")
            if botones:
                break
        res["boton_tienda"] = bool(botones)
        if not botones:
            fallas.append("no apareció «Agregar a Velbrum» en la tienda de Chrome")
        else:
            # En las máquinas lentas (macOS Intel, dibujo por software) el aviso
            # tarda; si no aparece, se vuelve a tocar el botón una vez.
            aviso = None
            for intento in range(2):
                b = m.js("""const b = [...document.querySelectorAll('button')].find(b => b.dataset.velbrum);
                    b.scrollIntoView({block: "center", inline: "center"}); return b.getBoundingClientRect().toJSON()""")
                m.clic(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
                for _ in range(20):
                    time.sleep(1)
                    aviso = m.js("const a = document.getElementById('velbrum-aviso'); return a && a.getBoundingClientRect().toJSON()")
                    if aviso and aviso["height"] > 150:  # ya con los dos botones
                        break
                if aviso:
                    break
            res["aviso_firefox"] = bool(aviso)
            if not aviso:
                fallas.append("no apareció el aviso de la versión para Firefox")
            elif args.conversion:
                m.clic(aviso["x"] + aviso["width"] / 2, aviso["bottom"] - 34)  # «Convertir la de Chrome igual»
                cartel = None
                for _ in range(60):
                    time.sleep(2)
                    m.contexto("chrome")
                    cartel = m.js("""const p = document.querySelector("#addon-webext-permissions-notification");
                        return p && !p.hidden ? p.querySelector(".popup-notification-description")?.textContent : null""")
                    m.contexto("content")
                    if cartel:
                        break
                res["cartel_instalacion"] = cartel
                if not cartel:
                    fallas.append("la conversión no llegó al cartel de instalación")
                    # Para saber en qué paso quedó: lo que convirtió el host y
                    # cómo se ve el aviso.
                    registro = args.datos / "velbrum.log"
                    res["registro"] = registro.read_text(errors="replace")[-2000:] if registro.exists() else ""
                    convertidas = args.datos / "extensiones-chrome"
                    res["convertidas"] = sorted(p.name for p in convertidas.glob("*")) if convertidas.is_dir() else []
                    try:
                        import base64
                        captura = m.cmd("WebDriver:TakeScreenshot", {"full": False})["value"]
                        pathlib.Path("prueba-captura.png").write_bytes(base64.b64decode(captura))
                    except Exception:  # noqa: BLE001 - es solo un diagnóstico
                        pass
    finally:
        try:
            m.contexto("chrome")
            m.cmd("Marionette:Quit", {"flags": ["eForceQuit"]})
        except Exception:  # noqa: BLE001 - el navegador puede cerrarse antes de contestar
            pass
        try:
            proceso.wait(60)
        except subprocess.TimeoutExpired:
            proceso.kill()

    for clave, valor in res.items():
        print(f"{clave}: {json.dumps(valor, ensure_ascii=False)}")
    if fallas:
        print("FALLAS:\n- " + "\n- ".join(fallas))
        sys.exit(1)
    print("Todo bien.")


if __name__ == "__main__":
    main()
