// Velbrum para Android: en la Chrome Web Store, el botón «Agregar a Chrome»
// instala en Velbrum (tienda.js); en la tienda de Edge, el botón «Obtener»
// (edge.js). Si la extensión tiene versión oficial para Firefox
// (equivalentes.json), se ofrece esa primero. Los avisos y botones de las
// tiendas son los mismos que en la PC (extension/); lo que en la PC hace el
// host de mensajería nativa acá lo hace convertir.js, y la instalación la
// abre la aplicación (api/padre.js) con su cartel «¿Agregar …?».

const TIENDAS = {
  chrome: { url: "https://chromewebstore.google.com/", nombre: "Chrome" },
  edge: { url: "https://microsoftedge.microsoft.com/addons/", nombre: "Edge" },
};
// La tienda sale de la página que pide (solo su marco principal), así cada
// una solo puede pedir sus extensiones.
const tiendaDe = (remitente) =>
  remitente.frameId === 0
    ? Object.keys(TIENDAS).find((tienda) => remitente.url?.startsWith(TIENDAS[tienda].url))
    : undefined;

async function equivalenteDe(tienda, id) {
  const fila = await equivalente(id, tienda);
  return fila ? { nombre: fila.nombre, tienda: TIENDAS[tienda].nombre } : null;
}

const SIN_INSTALACION =
  "la instalación de complementos está apagada. Prendela en Ajustes → Velbrum → " +
  "Ajustes de Velbrum → Seguridad → «Permitir la instalación de complementos» y volvé a tocar el botón.";

// `preparar` da { xpi, archivo, info }: se guarda en el perfil y la aplicación
// muestra su cartel.
async function instalar(preparar) {
  try {
    const { xpi, archivo, info } = await preparar();
    if (!(await browser.velbrum.instalar(xpi, archivo))) return { ok: false, error: SIN_INSTALACION };
    return { ok: true, ...info };
  } catch (error) {
    return { ok: false, error: error instanceof ErrorExtension ? error.message : `error inesperado: ${error}` };
  }
}

browser.runtime.onMessage.addListener((mensaje, remitente) => {
  const tienda = tiendaDe(remitente);
  if (!tienda || typeof mensaje?.id !== "string" || !/^[a-p]{32}$/.test(mensaje.id)) return undefined;
  switch (mensaje.accion) {
    case "equivalente":
      return equivalenteDe(tienda, mensaje.id);
    case "convertir":
      return instalar(() => preparar(mensaje.id, tienda));
    case "instalar-firefox":
      return instalar(() => prepararFirefox(mensaje.id, tienda));
    default:
      return undefined;
  }
});
