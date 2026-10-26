// Velbrum para Android: busca versiones nuevas. Al arrancar y cada 6 horas
// (como mucho una consulta cada 12) pregunta a GitHub cuál es la última
// versión publicada; si es más nueva y tiene APK para este teléfono
// (actualizar.json lo arma reempaquetar.py con la versión y la arquitectura
// de este APK), muestra un cartel abajo en la página que estás mirando
// (aviso-actualizacion.js) con el botón «Actualizar», que baja el APK. Android
// lo instala encima solo si está firmado con la misma clave de Velbrum. Fenix
// deja en segundo plano las pestañas que abre una extensión: por eso un cartel
// y no una pestaña. Se apaga con velbrum.actualizaciones = false en
// about:config.

const HORA = 60 * 60 * 1000;
const POSPONER = 3 * 24 * HORA; // «Más tarde»
const DESPUES_DE_BAJAR = 24 * HORA; // si tocaste «Actualizar» y no se instaló

// "2026.10.25.2" → [2026, 10, 25, 2]
const partesVersion = (v) => String(v).split(".").map((n) => parseInt(n, 10) || 0);
function esMasNueva(a, b) {
  const x = partesVersion(a);
  const y = partesVersion(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) > (y[i] ?? 0);
  }
  return false;
}

// La versión nueva para este teléfono, o null: { version, actual, apk, notas }.
async function versionNueva() {
  const config = await (await fetch(browser.runtime.getURL("actualizar.json"))).json();
  const respuesta = await fetch(`https://api.github.com/repos/${config.repositorio}/releases/latest`, {
    credentials: "omit",
    cache: "no-store",
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!respuesta.ok) throw new Error(`GitHub respondió ${respuesta.status}`);
  const ultima = await respuesta.json();
  const version = String(ultima.tag_name ?? "").replace(/^v/, "");
  if (!/^\d+(\.\d+)*$/.test(version) || !esMasNueva(version, config.version)) return null;
  // Solo el APK de esta versión y arquitectura, de las versiones del
  // repositorio de Velbrum.
  const nombre = `velbrum-${version}-android-${config.abi}.apk`;
  const base = `https://github.com/${config.repositorio}/releases/download/v${version}/`;
  const apk = (ultima.assets ?? []).find((a) => a.name === nombre && a.browser_download_url === base + nombre);
  if (!apk) return null;
  return { version, actual: config.version, apk: apk.browser_download_url, notas: `https://github.com/${config.repositorio}/releases/tag/v${version}` };
}

// En storage.local: consultada (fecha de la última consulta), nueva (la
// versión pendiente o null) y posponerHasta.
async function buscarActualizacion() {
  if (!(await browser.velbrum.buscarActualizaciones())) return;
  const { consultada = 0, nueva: anterior } = await browser.storage.local.get(["consultada", "nueva"]);
  if (Date.now() - consultada < 12 * HORA) return;
  let nueva;
  try {
    nueva = await versionNueva();
  } catch (error) {
    console.warn("Velbrum: no se pudo buscar actualizaciones", error);
    return;
  }
  const cambios = { consultada: Date.now(), nueva };
  if (nueva?.version !== anterior?.version) cambios.posponerHasta = 0; // versión distinta: avisar de nuevo
  await browser.storage.local.set(cambios);
  const [activa] = await browser.tabs.query({ active: true, currentWindow: true });
  if (activa) mostrarAviso(activa);
}

// El cartel, en la pestaña que estás mirando (solo páginas web, no privadas).
async function mostrarAviso(pestana) {
  if (!/^https?:/.test(pestana.url ?? "") || pestana.incognito) return;
  const { nueva, posponerHasta = 0 } = await browser.storage.local.get(["nueva", "posponerHasta"]);
  if (!nueva || Date.now() < posponerHasta) return;
  try {
    await browser.tabs.executeScript(pestana.id, { file: "aviso-actualizacion.js", runAt: "document_idle" });
  } catch {
    // páginas donde no se puede (addons.mozilla.org, por ejemplo)
  }
}

browser.tabs.onUpdated.addListener((id, cambio, pestana) => {
  if (cambio.status === "complete" && pestana.active) mostrarAviso(pestana);
});

// Lo que pide el cartel: los datos de la versión, «Más tarde» y «Actualizar».
browser.runtime.onMessage.addListener((mensaje, remitente) => {
  if (remitente.id !== browser.runtime.id || !String(mensaje?.accion).startsWith("actualizacion-")) return undefined;
  switch (mensaje.accion) {
    case "actualizacion-datos":
      return browser.storage.local.get("nueva").then(({ nueva }) => nueva ?? null);
    case "actualizacion-mas-tarde":
      return browser.storage.local.set({ posponerHasta: Date.now() + POSPONER });
    case "actualizacion-bajando":
      return browser.storage.local.set({ posponerHasta: Date.now() + DESPUES_DE_BAJAR });
    default:
      return undefined;
  }
});

browser.alarms.create("velbrum-actualizar", { delayInMinutes: 1, periodInMinutes: 6 * 60 });
browser.alarms.onAlarm.addListener((alarma) => {
  if (alarma.name === "velbrum-actualizar") buscarActualizacion();
});
