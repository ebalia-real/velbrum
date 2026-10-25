// Velbrum: instala extensiones de Chrome en el navegador, sin pasos manuales.
// - En la Chrome Web Store, el botón «Agregar a Chrome» instala en Velbrum
//   (tienda.js); en la tienda de Edge, el botón «Obtener» (edge.js).
// - Cualquier archivo .crx que se descargue: Velbrum avisa con una notificación
//   y, si la tocás, lo convierte e instala (así un sitio no puede hacerte
//   aparecer el cartel de instalación sin que lo pidas).
// El trabajo lo hace el host de mensajería nativa «velbrum.extensiones»
// (host/host-extensiones.py): descarga, adapta a Gecko y abre la instalación,
// que el navegador confirma con su cartel «¿Agregar …?».
//
// La extensión es Manifest V2 a propósito: en MV3 Gecko concede los sitios de
// los content scripts solo al instalarla, y como viene con el navegador nunca
// se reinstala; un sitio nuevo (como la tienda de Edge) quedaría sin permiso
// en los perfiles que ya existen. En MV2 los content scripts no lo necesitan.

const HOST = "velbrum.extensiones";

function pedir(mensaje) {
  return browser.runtime
    .sendNativeMessage(HOST, mensaje)
    .catch((error) => ({ ok: false, error: error.message }));
}

function avisar(titulo, texto) {
  browser.notifications.create({
    type: "basic",
    iconUrl: browser.runtime.getURL("iconos/velbrum-96.png"),
    title: titulo,
    message: texto,
  });
}

// Pedidos de las tiendas: cada una solo puede pedir sus extensiones.
const TIENDAS = {
  "instalar-chrome": "https://chromewebstore.google.com/",
  "instalar-edge": "https://microsoftedge.microsoft.com/addons/",
};
browser.runtime.onMessage.addListener((mensaje, remitente) => {
  const tienda = TIENDAS[mensaje?.accion];
  if (!tienda || !remitente.url?.startsWith(tienda) || remitente.frameId !== 0) return undefined;
  if (typeof mensaje.id !== "string" || !/^[a-p]{32}$/.test(mensaje.id)) return undefined;
  return pedir({ accion: mensaje.accion, id: mensaje.id });
});

// Archivos .crx descargados de cualquier sitio: primero una notificación;
// la instalación empieza recién cuando la tocás.
const esCrx = (descarga) =>
  /\.crx$/i.test(descarga.filename) || descarga.mime === "application/x-chrome-extension";
const descargasPendientes = new Map(); // id de la notificación → ruta del .crx

function sitioDe(descarga) {
  try {
    return new URL(descarga.referrer || descarga.url).hostname || "un sitio";
  } catch {
    return "un sitio";
  }
}

browser.downloads.onChanged.addListener(async (cambio) => {
  if (cambio.state?.current !== "complete") return;
  const [descarga] = await browser.downloads.search({ id: cambio.id });
  if (!descarga || !esCrx(descarga)) return;
  const archivo = descarga.filename.split("/").pop();
  const id = await browser.notifications.create({
    type: "basic",
    iconUrl: browser.runtime.getURL("iconos/velbrum-96.png"),
    title: "Extensión de Chrome descargada",
    message: `${archivo} (de ${sitioDe(descarga)}). Tocá acá para instalarla en Velbrum.`,
  });
  descargasPendientes.set(id, descarga.filename);
});

browser.notifications.onClicked.addListener(async (id) => {
  const ruta = descargasPendientes.get(id);
  if (!ruta) return;
  descargasPendientes.delete(id);
  browser.notifications.clear(id);
  const respuesta = await pedir({ accion: "instalar-crx", ruta });
  if (!respuesta.ok) {
    avisar("Velbrum no pudo instalar la extensión", respuesta.error ?? "error desconocido");
  } else if (respuesta.avisos?.length) {
    avisar(`${respuesta.nombre}: tené en cuenta`, respuesta.avisos.join("\n"));
  }
});
