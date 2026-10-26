/* Velbrum: botón «Velbrum» de la barra de herramientas, con los ajustes propios
 * de Velbrum adentro del navegador: nivel de seguridad, bordes de privacidad,
 * siempre privado, modo liviano, extensiones firmadas y la ventana privada
 * con Tor. En la ventana con Tor, además, cada sitio usa su propio circuito.
 *
 * Va dentro de omni.ja (solo lectura, en el store de Nix) y lo carga
 * browser-main.js en cada ventana (ver marca/codigo.py). Los cambios de
 * bordes y firmas se aplican al instante (Gecko escucha esas preferencias) y
 * se anotan en ~/.local/share/velbrum igual que «velbrum --sin-bordes» o «velbrum
 * --exigir-firmas», para que el lanzador los mantenga y el conversor de
 * extensiones de Chrome los respete. */

const lazy = {};
ChromeUtils.defineESModuleGetters(lazy, {
  AddonManager: "resource://gre/modules/AddonManager.sys.mjs",
  CustomizableUI: "moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs",
  ExtensionPermissions: "resource://gre/modules/ExtensionPermissions.sys.mjs",
  PrivateBrowsingUtils: "resource://gre/modules/PrivateBrowsingUtils.sys.mjs",
  RFPHelper: "resource://gre/modules/RFPHelper.sys.mjs",
  setTimeout: "resource://gre/modules/Timer.sys.mjs",
  setInterval: "resource://gre/modules/Timer.sys.mjs",
});
// El actualizador de los paquetes para otros sistemas (no se usa en NixOS).
ChromeUtils.defineLazyGetter(lazy, "paquete", () =>
  ChromeUtils.importESModule("chrome://browser/content/actualizador-velbrum.sys.mjs")
);

const ID = "velbrum-ajustes";
const PANEL = "velbrum-ajustes-panel";
const ICONO = "chrome://browser/skin/preferences/category-librewolf.svg";
const CON_TOR = Services.env.get("VELBRUM_TOR") == "1";

// ── Niveles de seguridad, como los de Mullvad y Tor Browser ──────────────
// (sin NoScript: con preferencias de Gecko).
const MAS_SEGURO = {
  "javascript.options.ion": false,
  "javascript.options.baselinejit": false,
  "javascript.options.native_regexp": false,
  "javascript.options.wasm": false,
  "javascript.options.asmjs": false,
  "gfx.font_rendering.opentype_svg.enabled": false,
  "gfx.font_rendering.graphite.enabled": false,
  "mathml.disabled": true,
  "media.autoplay.default": 5,
  "media.autoplay.blocking_policy": 2,
};
const NIVELES = [
  {
    nombre: "Estándar",
    texto: "Todo funciona como en un navegador común.",
    prefs: {},
  },
  {
    nombre: "Más seguro",
    texto:
      "Sin el compilador rápido de JavaScript ni WebAssembly, sin algunas fuentes y " +
      "símbolos matemáticos, y el audio y el video arrancan con un clic. Algunos " +
      "sitios andan más lentos.",
    prefs: MAS_SEGURO,
  },
  {
    nombre: "El más seguro",
    texto:
      "Además, sin JavaScript, SVG, WebGL ni fuentes descargadas. Muchos sitios " +
      "no van a funcionar bien.",
    prefs: {
      ...MAS_SEGURO,
      "javascript.enabled": false,
      "svg.disabled": true,
      "webgl.disabled": true,
      "gfx.downloadable_fonts.enabled": false,
    },
  },
];
const PREF_NIVEL = "velbrum.nivelSeguridad";

// ── Modo liviano: menos memoria para PCs con 1 a 3 GB ───────────────────
const LIVIANO = {
  "dom.ipc.processCount": 2,
  "dom.ipc.processCount.webIsolated": 1,
  "dom.ipc.keepProcessesAlive.web": 0,
  "dom.ipc.processPrelaunch.enabled": false,
  "browser.sessionhistory.max_total_viewers": 0,
  "browser.cache.memory.capacity": 32768,
  "media.memory_cache_max_size": 16384,
  "image.mem.surfacecache.max_size_kb": 131072,
  "browser.tabs.unloadOnLowMemory": true,
  "browser.tabs.min_inactive_duration_before_unload": 300000,
  "toolkit.cosmeticAnimations.enabled": false,
};
const PREF_LIVIANO = "velbrum.liviano";
// Con menos de esto (en bytes), el modo liviano se prende solo.
const POCA_MEMORIA = 3.5 * 1024 ** 3;

// ── Casillas ─────────────────────────────────────────────────────────────
const CASILLAS = [
  {
    id: "bordes",
    pref: "privacy.resistFingerprinting.letterboxing",
    titulo: "Bordes de privacidad",
    texto:
      "Las páginas ven un tamaño de ventana redondeado, como en Mullvad Browser. " +
      "Sin bordes usan toda la ventana, pero los sitios ven su tamaño exacto.",
    // Archivo que lee el lanzador: existe cuando los bordes están sacados.
    marca: "sin-bordes",
    marcaCuando: false,
  },
  {
    id: "privado",
    pref: "browser.privatebrowsing.autostart",
    // LibreWolf la vuelve a false en cada arranque: el lanzador la repone si
    // existe este archivo (gecko/ajustes.cfg).
    marca: "siempre-privado",
    marcaCuando: true,
    titulo: "Siempre privado, como Mullvad",
    texto:
      "No guarda historial, cookies ni caché al cerrar. Tus extensiones siguen " +
      "andando: Velbrum les da permiso para ventanas privadas. Se aplica al reiniciar.",
    reiniciar: true,
    soloNormal: true,
  },
  {
    id: "liviano",
    pref: PREF_LIVIANO,
    titulo: "Modo liviano (poca memoria)",
    texto:
      "Menos procesos y caché, sin guardar en memoria las páginas anteriores, y " +
      "descarga las pestañas que no usás cuando falta memoria. Se prende solo en " +
      "PCs con menos de 4 GB. Se aplica del todo al reiniciar.",
    reiniciar: true,
    soloNormal: true,
  },
  {
    id: "firmas",
    pref: "xpinstall.signatures.required",
    titulo: "Solo extensiones firmadas por Mozilla",
    texto:
      "Desactiva las extensiones de Chrome (no las borra). Sin esto, Velbrum acepta " +
      "extensiones de Chrome, siempre con el cartel de confirmación.",
    bloqueada: "Lo fija la configuración del sistema (velbrum.extensionesDeChrome).",
    marca: "firmas-obligatorias",
    marcaCuando: true,
    soloNormal: true,
  },
];

// Países de salida de la ventana con Tor: los que tienen suficientes nodos de
// salida (muchos países no tienen). Ver «velbrum --tor-pais».
const PAISES = [
  ["auto", "Automático (el más anónimo)"],
  ["de", "Alemania"],
  ["nl", "Países Bajos"],
  ["us", "Estados Unidos"],
  ["se", "Suecia"],
  ["at", "Austria"],
  ["fr", "Francia"],
  ["no", "Noruega"],
  ["ch", "Suiza"],
  ["ro", "Rumania"],
  ["fi", "Finlandia"],
  ["is", "Islandia"],
  ["dk", "Dinamarca"],
  ["lu", "Luxemburgo"],
];

let creado = false;
let reinicioPendiente = false;
// Clave de los circuitos de Tor: cambiarla da circuitos nuevos en todos los
// sitios (ver aislarCircuitos).
let clave = Services.uuid.generateUUID().toString();

// El perfil de Velbrum es <datos>/gecko (en NixOS ~/.local/share/velbrum; en
// los paquetes para otros sistemas, la carpeta que indica el lanzador en
// VELBRUM_DATOS): los interruptores se anotan en <datos>, donde los lee el
// lanzador. Con otro perfil (la ventana con Tor, o velbrum --profile …) no se
// anota nada.
function carpetaDatos() {
  const perfil = PathUtils.profileDir;
  const datos = PathUtils.parent(perfil);
  if (PathUtils.filename(perfil) != "gecko") {
    return null;
  }
  return (Services.env.get("VELBRUM_DATOS") || PathUtils.filename(datos) == "velbrum") ? datos : null;
}

async function anotar(casilla, valor) {
  const datos = carpetaDatos();
  if (!casilla.marca || !datos) {
    return;
  }
  const ruta = PathUtils.join(datos, casilla.marca);
  if (valor == casilla.marcaCuando) {
    await IOUtils.writeUTF8(ruta, "");
  } else {
    await IOUtils.remove(ruta, { ignoreAbsent: true });
  }
}

function poner(pref, valor) {
  if (typeof valor == "boolean") {
    Services.prefs.setBoolPref(pref, valor);
  } else if (typeof valor == "number") {
    Services.prefs.setIntPref(pref, valor);
  } else {
    Services.prefs.setStringPref(pref, valor);
  }
}

// Cada nivel pone sus preferencias y vuelve a su valor normal las del resto.
function aplicarNivel(nivel) {
  const todas = new Set(NIVELES.flatMap(n => Object.keys(n.prefs)));
  for (const pref of todas) {
    if (pref in NIVELES[nivel].prefs) {
      poner(pref, NIVELES[nivel].prefs[pref]);
    } else {
      Services.prefs.clearUserPref(pref);
    }
  }
  Services.prefs.setIntPref(PREF_NIVEL, nivel);
}

function aplicarLiviano(activo) {
  for (const [pref, valor] of Object.entries(LIVIANO)) {
    if (activo) {
      poner(pref, valor);
    } else {
      Services.prefs.clearUserPref(pref);
    }
  }
  Services.prefs.setBoolPref(PREF_LIVIANO, activo);
}

function cambiar(casilla, valor) {
  if (casilla.id == "liviano") {
    aplicarLiviano(valor);
  } else {
    Services.prefs.setBoolPref(casilla.pref, valor);
  }
  if (casilla.reiniciar) {
    reinicioPendiente = true;
  }
  anotar(casilla, valor).catch(error => console.error("Velbrum: no pude anotar", casilla.marca, error));
}

// Corre el lanzador de Velbrum (velbrum …) y avisa cuando termina.
function correrLanzador(argumentos) {
  return new Promise((resolver, rechazar) => {
    const ruta = Services.env.get("VELBRUM_LANZADOR");
    if (!ruta) {
      rechazar(new Error("no sé dónde está el lanzador (VELBRUM_LANZADOR)"));
      return;
    }
    const archivo = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsIFile);
    archivo.initWithPath(ruta);
    const proceso = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
    proceso.init(archivo);
    proceso.runAsync(argumentos, argumentos.length, {
      observe(_sujeto, tema) {
        if (tema == "process-finished" && proceso.exitValue == 0) {
          resolver();
        } else {
          rechazar(new Error(`velbrum ${argumentos.join(" ")}: salió con ${proceso.exitValue}`));
        }
      },
    });
  });
}

// ── Actualizaciones ──────────────────────────────────────────────────────
// Una vez por día se fija en GitHub si hay una versión más nueva que la
// instalada y lo ofrece en una barra con «Instalar y reiniciar».
// - En NixOS (etiquetas vAAAA.MM.DD): corre el ayudante velbrum-actualizar
//   con pkexec (contraseña de administrador), que baja la versión, verifica
//   su firma y hace el rebuild. Después, o cuando un rebuild propio instala
//   otra versión, ofrece reiniciar con el lanzador instalado (así arranca la
//   versión nueva) y las pestañas.
// - En los paquetes para Windows, macOS y Linux (la última versión publicada):
//   actualizador-velbrum.sys.mjs baja el paquete, verifica la firma de sus
//   sumas y lo instala al reiniciar (o al cerrar, con «Al cerrar»). Los .deb,
//   .rpm y de Arch, o si no se puede escribir donde está instalado:
//   «Descargar».
const VERSION = Services.env.get("VELBRUM_VERSION") || "";
const REPO = Services.env.get("VELBRUM_REPO_ACTUALIZACIONES") || "";
const AYUDANTE = Services.env.get("VELBRUM_ACTUALIZADOR") || "";
// (VELBRUM_LANZADOR_SISTEMA solo sirve para probar el reinicio con otro lanzador.)
const LANZADOR_SISTEMA = Services.env.get("VELBRUM_LANZADOR_SISTEMA") || "/run/current-system/sw/bin/velbrum";
// (VELBRUM_PKEXEC solo sirve para probar la instalación sin pedir contraseña.)
const PKEXEC = Services.env.get("VELBRUM_PKEXEC") || "/run/wrappers/bin/pkexec";
const PREF_ULTIMA = "velbrum.actualizador.ultimaBusqueda";
const PREF_RECORDAR = "velbrum.actualizador.recordarDesde";
const BARRA = "velbrum-actualizacion";
const UN_DIA = 24 * 3600;
let versionDisponible = null;
// Paquetes: lo que devolvió actualizador-velbrum.sys.mjs buscar().
let encontrada = null;
let instalando = false;
let relanzarAlCerrar = false;
let reinicioOfrecido = false;

const ahora = () => Math.floor(Date.now() / 1000);

// «2026.10.21.2» es más nueva que «2026.10.21».
function masNueva(a, b) {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    if ((pa[i] ?? 0) != (pb[i] ?? 0)) {
      return (pa[i] ?? 0) > (pb[i] ?? 0);
    }
  }
  return false;
}

function archivoLocal(ruta) {
  const archivo = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsIFile);
  archivo.initWithPath(ruta);
  return archivo;
}

// El lanzador que instaló el último rebuild (resolviendo los enlaces).
function lanzadorInstalado() {
  try {
    const archivo = archivoLocal(LANZADOR_SISTEMA);
    archivo.normalize();
    return archivo.exists() ? archivo.path : null;
  } catch {
    return null;
  }
}

// ¿Un rebuild instaló otra versión de Velbrum desde que se abrió esta? (Solo
// NixOS: en los paquetes lo que se instala es lo que preparó el actualizador.)
function hayVersionInstaladaNueva() {
  if (instalacionPaquete()) {
    return false;
  }
  const actual = Services.env.get("VELBRUM_LANZADOR");
  const instalado = lanzadorInstalado();
  return Boolean(actual && instalado && actual != instalado);
}

// Paquetes: cómo está instalado este Velbrum (null en NixOS).
let instalacion;
function instalacionPaquete() {
  if (instalacion === undefined) {
    instalacion = null;
    if (!AYUDANTE && !CON_TOR) {
      try {
        instalacion = lazy.paquete.instalacion();
      } catch (error) {
        console.error("Velbrum: actualizador", error);
      }
    }
  }
  return instalacion;
}

async function buscarVersion(ventana, forzar) {
  if (!REPO || !VERSION) {
    return null;
  }
  if (!forzar && ahora() - Services.prefs.getIntPref(PREF_ULTIMA, 0) < UN_DIA) {
    return versionDisponible;
  }
  const inst = instalacionPaquete();
  if (inst) {
    const ultima = await lazy.paquete.buscar(ventana, REPO, inst);
    Services.prefs.setIntPref(PREF_ULTIMA, ahora());
    encontrada = ultima && masNueva(ultima.version, VERSION) ? ultima : null;
    versionDisponible = encontrada?.version ?? null;
    return versionDisponible;
  }
  const respuesta = await ventana.fetch(`https://api.github.com/repos/${REPO}/tags?per_page=50`, {
    credentials: "omit",
    cache: "no-store",
  });
  if (!respuesta.ok) {
    throw new Error(`GitHub respondió ${respuesta.status}`);
  }
  const versiones = (await respuesta.json())
    .map(etiqueta => String(etiqueta.name))
    .filter(nombre => /^v\d{4}\.\d{2}\.\d{2}(\.\d+)?$/.test(nombre))
    .map(nombre => nombre.slice(1));
  Services.prefs.setIntPref(PREF_ULTIMA, ahora());
  const ultima = versiones.reduce((mejor, v) => (!mejor || masNueva(v, mejor) ? v : mejor), null);
  versionDisponible = ultima && masNueva(ultima, VERSION) ? ultima : null;
  return versionDisponible;
}

async function barra(ventana, texto, botones) {
  const caja = ventana.gNotificationBox;
  const vieja = caja.getNotificationWithValue(BARRA);
  if (vieja) {
    caja.removeNotification(vieja);
  }
  return caja.appendNotification(
    BARRA,
    { label: texto, image: ICONO, priority: caja.PRIORITY_INFO_HIGH },
    botones
  );
}

function reiniciarVelbrum() {
  Services.prefs.setBoolPref("browser.sessionstore.resume_session_once", true);
  // Paquetes con una versión nueva preparada: al cerrarse esta instancia la
  // instala un script, que después vuelve a abrir Velbrum (ver iniciar).
  if (instalacionPaquete() && lazy.paquete.hayPendiente()) {
    relanzarAlCerrar = true;
    Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit);
    return;
  }
  // El lanzador instalado espera a que esta instancia se cierre y abre la
  // versión instalada; al abrir se recuperan las pestañas.
  const proceso = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
  proceso.init(archivoLocal(lanzadorInstalado() ?? Services.env.get("VELBRUM_LANZADOR")));
  proceso.runAsync(["--reiniciar"], 1);
  Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit);
}

function ofrecerReinicio(ventana, texto) {
  reinicioOfrecido = true;
  return barra(ventana, texto, [
    { label: "Reiniciar ahora", accessKey: "R", callback: () => reiniciarVelbrum() },
    { label: "Más tarde", accessKey: "M", callback: () => false },
  ]);
}

function instalar(ventana, version) {
  if (instalando || !AYUDANTE) {
    return;
  }
  instalando = true;
  barra(
    ventana,
    `Instalando Velbrum ${version}… Te va a pedir la contraseña de administrador; ` +
      "después el sistema se actualiza, lo que puede tardar varios minutos.",
    []
  );
  const proceso = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
  proceso.init(archivoLocal(PKEXEC));
  proceso.runAsync([AYUDANTE, "instalar"], 2, {
    observe(_sujeto, tema) {
      instalando = false;
      const codigo = proceso.exitValue;
      if (tema == "process-finished" && codigo == 0) {
        if (hayVersionInstaladaNueva()) {
          ofrecerReinicio(ventana, `Velbrum ${version} está instalada.`);
        } else {
          barra(ventana, `Velbrum ya está al día (${VERSION}).`, []);
        }
      } else if (codigo == 126 || codigo == 127) {
        barra(ventana, "No se instaló la actualización: se canceló la contraseña de administrador.", [
          { label: "Intentar de nuevo", accessKey: "I", callback: () => instalar(ventana, version) },
        ]);
      } else {
        barra(
          ventana,
          "No se pudo instalar la actualización. Los detalles están en /var/log/velbrum-actualizar.log.",
          []
        );
      }
    },
  });
}

// Paquetes: baja y verifica la versión nueva; después ofrece reiniciar.
async function instalarPaquete(ventana, version) {
  if (instalando || !encontrada) {
    return;
  }
  instalando = true;
  try {
    const aviso = await barra(ventana, `Bajando Velbrum ${version}…`, []);
    await lazy.paquete.preparar(ventana, instalacionPaquete(), encontrada, texto => {
      aviso.label = texto;
    });
    ofrecerPreparada(ventana, version);
  } catch (error) {
    console.error("Velbrum: actualización", error);
    barra(ventana, `No se pudo actualizar Velbrum: ${error.message}.`, [
      { label: "Intentar de nuevo", accessKey: "I", callback: () => instalarPaquete(ventana, version) },
    ]);
  } finally {
    instalando = false;
  }
}

function ofrecerPreparada(ventana, version) {
  reinicioOfrecido = true;
  return barra(ventana, `Velbrum ${version} está lista. Se instala al reiniciar.`, [
    { label: "Reiniciar ahora", accessKey: "R", callback: () => reiniciarVelbrum() },
    { label: "Al cerrar Velbrum", accessKey: "A", callback: () => false },
  ]);
}

async function ofrecerActualizacion(ventana, version) {
  // En NixOS la instala el ayudante (pkexec + rebuild) y en los paquetes, el
  // actualizador; si no se puede, se baja de la página de la versión.
  const inst = instalacionPaquete();
  const descargar = {
    label: "Descargar",
    accessKey: "D",
    callback: () => {
      ventana.openTrustedLinkIn(`https://github.com/${REPO}/releases/tag/v${version}`, "tab");
      return false;
    },
  };
  let primero = descargar;
  let mensaje = `Hay una versión nueva de Velbrum (${version}).`;
  if (AYUDANTE) {
    primero = { label: "Instalar y reiniciar", accessKey: "I", callback: () => instalar(ventana, version) };
  } else if (await lazy.paquete.sePuedeInstalar(inst)) {
    primero = { label: "Instalar y reiniciar", accessKey: "I", callback: () => instalarPaquete(ventana, version) };
  } else if (inst?.tipo == "sistema") {
    mensaje += " Actualizala con el gestor de paquetes de tu sistema.";
  }
  return barra(ventana, mensaje, [
    primero,
    {
      label: "Ahora no",
      accessKey: "A",
      callback: () => {
        Services.prefs.setIntPref(PREF_RECORDAR, ahora() + UN_DIA);
        return false;
      },
    },
  ]);
}

// Revisión periódica (y con «Buscar actualizaciones», forzada). Devuelve un
// texto para el panel.
async function revisarActualizaciones(forzar = false) {
  const ventana = Services.wm.getMostRecentWindow("navigator:browser");
  if (!ventana || CON_TOR || instalando) {
    return "";
  }
  if (hayVersionInstaladaNueva()) {
    if (forzar || !reinicioOfrecido) {
      await ofrecerReinicio(ventana, "Hay una versión nueva de Velbrum instalada. Reiniciá para usarla.");
    }
    return "Hay una versión nueva instalada: reiniciá Velbrum.";
  }
  if (instalacionPaquete() && lazy.paquete.hayPendiente()) {
    if (forzar) {
      await ofrecerPreparada(ventana, versionDisponible);
    }
    return `Velbrum ${versionDisponible} está lista: reiniciá para instalarla.`;
  }
  try {
    const version = await buscarVersion(ventana, forzar);
    if (version) {
      if (forzar || ahora() >= Services.prefs.getIntPref(PREF_RECORDAR, 0)) {
        await ofrecerActualizacion(ventana, version);
      }
      return `Hay una versión nueva: ${version}.`;
    }
    return REPO ? "Velbrum está al día." : "";
  } catch (error) {
    console.warn("Velbrum: no pude buscar actualizaciones", error);
    return forzar ? "No se pudo buscar actualizaciones (¿hay internet?)." : "";
  }
}

async function mostrarResultado() {
  const r = await lazy.paquete.resultado();
  const ventana = Services.wm.getMostRecentWindow("navigator:browser");
  if (!r || !ventana) {
    return;
  }
  if (r.error) {
    barra(ventana, `No se pudo instalar Velbrum ${r.version}: ${r.error}. Sigue la versión ${VERSION}.`, []);
  } else if (r.version == VERSION) {
    barra(ventana, `Velbrum se actualizó a la versión ${VERSION}.`, []);
  }
}

// Abre la ventana con Tor, o una pestaña nueva en ella si ya está abierta
// (con una dirección, esa página). En la ventana con Tor, abre otra ventana.
function abrirConTor(ventana, direccion) {
  if (CON_TOR) {
    ventana.OpenBrowserWindow();
    return;
  }
  const argumentos = direccion ? ["--tor", "--", direccion] : ["--tor"];
  correrLanzador(argumentos).catch(error => console.error("Velbrum:", error));
}

// Menú ≡ («Nueva pestaña con Tor», debajo de «Nueva ventana privada») y
// menú de los enlaces («Abrir enlace en una pestaña con Tor»).
function menusDeTor(ventana) {
  if (CON_TOR) {
    return;
  }
  const doc = ventana.document;
  doc.addEventListener(
    "ViewShowing",
    evento => {
      const vista = evento.target;
      if (vista.id != "appMenu-mainView" || vista.querySelector("#appMenu-velbrum-tor")) {
        return;
      }
      const privada = vista.querySelector("#appMenu-new-private-window-button2");
      if (!privada) {
        return;
      }
      const boton = doc.createXULElement("toolbarbutton");
      boton.id = "appMenu-velbrum-tor";
      boton.className = "subviewbutton";
      boton.setAttribute("label", "Nueva pestaña con Tor");
      boton.addEventListener("command", () => {
        ventana.PanelUI.hide();
        abrirConTor(ventana);
      });
      privada.after(boton);
    },
    true
  );

  const menu = doc.getElementById("contentAreaContextMenu");
  if (!menu) {
    return;
  }
  const opcion = doc.createXULElement("menuitem");
  opcion.id = "context-velbrum-tor";
  opcion.setAttribute("label", "Abrir enlace en una pestaña con Tor");
  opcion.addEventListener("command", () => {
    const direccion = ventana.gContextMenu?.linkURL;
    // Solo páginas web (nada de javascript:, file:, etc.).
    if (direccion && /^https?:\/\//i.test(direccion)) {
      abrirConTor(ventana, direccion);
    }
  });
  const referencia = doc.getElementById("context-openlinkprivate");
  if (referencia) {
    referencia.after(opcion);
  } else {
    menu.append(opcion);
  }
  menu.addEventListener("popupshowing", evento => {
    if (evento.target == menu) {
      const enlace = ventana.gContextMenu?.onLink ? ventana.gContextMenu.linkURL : "";
      opcion.hidden = !/^https?:\/\//i.test(enlace || "");
    }
  });
}

async function paisActual() {
  try {
    const datos = PathUtils.parent(PathUtils.profileDir);
    return (await IOUtils.readUTF8(PathUtils.join(datos, "tor-pais"))).trim() || "auto";
  } catch {
    return "auto";
  }
}

// Cambia el país de salida (o lo vuelve a pedir, para circuitos nuevos),
// renueva los circuitos de todos los sitios y recarga la pestaña.
async function cambiarPais(ventana, pais, estado) {
  const nombre = PAISES.find(([codigo]) => codigo == pais)?.[1] ?? pais;
  estado.textContent = "Cambiando…";
  try {
    await correrLanzador(["--tor-pais", pais]);
    clave = Services.uuid.generateUUID().toString();
    // Que no se reusen conexiones abiertas por los circuitos viejos.
    Services.obs.notifyObservers(null, "net:prune-all-connections");
    estado.textContent = pais == "auto" ? "Circuitos nuevos, por cualquier país." : `Circuitos nuevos, saliendo por ${nombre}.`;
    ventana.gBrowser.selectedBrowser.reload();
  } catch (error) {
    console.error("Velbrum:", error);
    estado.textContent = "No se pudo cambiar (¿Tor está conectado?).";
  }
}

// ── Panel ────────────────────────────────────────────────────────────────
function actualizar(panel) {
  const lista = panel.querySelector(".velbrum-pais");
  if (lista) {
    paisActual().then(pais => (lista.value = pais));
  }
  const nivel = Services.prefs.getIntPref(PREF_NIVEL, 0);
  const grupo = panel.querySelector("radiogroup");
  grupo.value = String(nivel);
  panel.querySelector(".velbrum-nivel-texto").textContent = NIVELES[nivel].texto;
  for (const casilla of CASILLAS) {
    const elemento = panel.querySelector(`checkbox[data-id="${casilla.id}"]`);
    if (!elemento) {
      continue;
    }
    const bloqueada = Services.prefs.prefIsLocked(casilla.pref);
    elemento.checked = Services.prefs.getBoolPref(casilla.pref, false);
    elemento.disabled = bloqueada;
    elemento.nextElementSibling.textContent =
      bloqueada && casilla.bloqueada ? casilla.bloqueada : casilla.texto;
  }
  panel.querySelector(".velbrum-reiniciar").hidden = !reinicioPendiente;
}

function crearPanel(doc) {
  const xul = nombre => doc.createXULElement(nombre);
  const texto = (contenido, estilo) => {
    const d = xul("description");
    d.textContent = contenido;
    d.setAttribute("style", estilo);
    return d;
  };
  const chico = "margin: 0 0 8px 26px; opacity: 0.8; font-size: 0.9em;";
  const panel = xul("panel");
  panel.id = PANEL;
  panel.setAttribute("type", "arrow");
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Ajustes de Velbrum");

  const caja = xul("vbox");
  caja.setAttribute("style", "padding: 12px 16px; gap: 4px; width: 26em;");
  const titulo = xul("label");
  titulo.setAttribute("value", CON_TOR ? "Velbrum con Tor" : "Velbrum");
  titulo.setAttribute("style", "font-weight: 600; font-size: 1.15em; margin: 0 0 6px;");
  caja.append(titulo);
  if (CON_TOR) {
    caja.append(
      texto(
        "Todo pasa por Tor y cada sitio usa su propio circuito: los sitios ven una IP " +
          "de Tor, no la tuya. Tu huella es la de Velbrum, no la de Tor Browser.",
        "margin: 0 0 10px; opacity: 0.85; font-size: 0.9em;"
      )
    );
    const etiquetaPais = xul("label");
    etiquetaPais.setAttribute("value", "País de salida");
    etiquetaPais.setAttribute("style", "font-weight: 600; margin: 0;");
    const lista = xul("menulist");
    lista.classList.add("velbrum-pais");
    lista.setAttribute("aria-label", "País de salida");
    const opciones = xul("menupopup");
    for (const [codigo, nombre] of PAISES) {
      const opcion = xul("menuitem");
      opcion.setAttribute("label", nombre);
      opcion.setAttribute("value", codigo);
      opciones.append(opcion);
    }
    lista.append(opciones);
    const estado = texto(
      "Elegir un país te hace un poco más fácil de distinguir que «Automático».",
      "margin: 0 0 4px; opacity: 0.8; font-size: 0.9em;"
    );
    lista.addEventListener("command", () => cambiarPais(doc.defaultView, lista.value, estado));
    const nuevos = xul("button");
    nuevos.setAttribute("label", "Circuitos nuevos");
    nuevos.addEventListener("command", () => cambiarPais(doc.defaultView, lista.value || "auto", estado));
    caja.append(etiquetaPais, lista, estado, nuevos);
    caja.append(texto("", "margin: 0 0 6px;"));
  }

  const etiquetaNivel = xul("label");
  etiquetaNivel.setAttribute("value", "Nivel de seguridad");
  etiquetaNivel.setAttribute("style", "font-weight: 600; margin: 0;");
  const grupo = xul("radiogroup");
  grupo.setAttribute("orient", "horizontal");
  grupo.setAttribute("aria-label", "Nivel de seguridad");
  NIVELES.forEach((nivel, i) => {
    const radio = xul("radio");
    radio.setAttribute("label", nivel.nombre);
    radio.setAttribute("value", String(i));
    grupo.append(radio);
  });
  const textoNivel = texto("", "margin: 0 0 4px; opacity: 0.8; font-size: 0.9em;");
  textoNivel.classList.add("velbrum-nivel-texto");
  grupo.addEventListener("command", () => {
    aplicarNivel(Number(grupo.value));
    textoNivel.textContent = NIVELES[Number(grupo.value)].texto;
  });
  caja.append(etiquetaNivel, grupo, textoNivel,
    texto("Recargá las páginas abiertas para aplicarlo.", "margin: 0 0 10px; opacity: 0.6; font-size: 0.85em;"));

  for (const casilla of CASILLAS) {
    if (CON_TOR && casilla.soloNormal) {
      continue;
    }
    const elemento = xul("checkbox");
    elemento.setAttribute("label", casilla.titulo);
    elemento.setAttribute("data-id", casilla.id);
    elemento.addEventListener("command", () => {
      cambiar(casilla, elemento.checked);
      actualizar(panel);
    });
    caja.append(elemento, texto("", chico));
  }

  const reiniciar = xul("button");
  reiniciar.classList.add("velbrum-reiniciar");
  reiniciar.setAttribute("label", "Reiniciar Velbrum para aplicar");
  reiniciar.addEventListener("command", () => reiniciarVelbrum());
  const tor = xul("button");
  tor.setAttribute("label", CON_TOR ? "Nueva ventana con Tor" : "Nueva pestaña con Tor");
  tor.addEventListener("command", () => {
    panel.hidePopup();
    abrirConTor(doc.defaultView);
  });
  caja.append(reiniciar, tor);

  // Versión y actualizaciones.
  const version = texto(VERSION ? `Velbrum ${VERSION}` : "Velbrum", "margin: 10px 0 0; opacity: 0.7; font-size: 0.9em;");
  version.classList.add("velbrum-version");
  caja.append(version);
  if (!CON_TOR) {
    const buscar = xul("button");
    buscar.setAttribute("label", "Buscar actualizaciones");
    buscar.addEventListener("command", async () => {
      version.textContent = `Velbrum ${VERSION} · buscando…`;
      const estado = await revisarActualizaciones(true);
      version.textContent = `Velbrum ${VERSION}${estado ? " · " + estado : ""}`;
    });
    caja.append(buscar);
  }

  panel.append(caja);
  panel.addEventListener("popupshowing", () => actualizar(panel));
  (doc.getElementById("mainPopupSet") ?? doc.documentElement).append(panel);
  return panel;
}

function abrir(evento) {
  const nodo = evento.target;
  const doc = nodo.ownerDocument;
  const panel = doc.getElementById(PANEL) ?? crearPanel(doc);
  // Si el botón está en el menú de desborde (ya cerrado), el panel se abre
  // debajo del botón del menú.
  const ancla = nodo.checkVisibility?.()
    ? (nodo.querySelector(".toolbarbutton-icon") ?? nodo)
    : doc.getElementById("PanelUI-menu-button");
  panel.openPopup(ancla, { position: "bottomright topright", triggerEvent: evento });
}

// ── Ventana con Tor: un circuito por sitio ───────────────────────────────
// Como Tor Browser: el usuario SOCKS es el sitio principal de cada pedido y
// Tor (IsolateSOCKSAuth) usa un circuito distinto para cada usuario. La clave
// cambia en cada arranque y con «Circuitos nuevos» o al cambiar de país.
function aislarCircuitos() {
  const servicio = Cc["@mozilla.org/network/protocol-proxy-service;1"].getService(Ci.nsIProtocolProxyService);
  const sitioDe = canal => {
    const primero = canal.loadInfo?.originAttributes?.firstPartyDomain;
    if (primero) {
      return primero;
    }
    try {
      return Services.eTLD.getBaseDomain(canal.URI);
    } catch {
      return canal.URI?.host || "--sin-sitio--";
    }
  };
  servicio.registerChannelFilter(
    {
      QueryInterface: ChromeUtils.generateQI(["nsIProtocolProxyChannelFilter"]),
      applyFilter(canal, proxy, respuesta) {
        try {
          if (proxy?.type == "socks") {
            // La clave va también en el usuario: Gecko separa las conexiones
            // por usuario del proxy, así una clave nueva no reusa conexiones
            // de los circuitos viejos.
            proxy = servicio.newProxyInfoWithAuth(
              "socks", proxy.host, proxy.port, `${sitioDe(canal.QueryInterface(Ci.nsIChannel))}:${clave}`, clave,
              "", "", proxy.flags, proxy.failoverTimeout, proxy.failoverProxy
            );
          }
        } catch (error) {
          console.error("Velbrum: circuito por sitio", error);
        }
        respuesta.onProxyFilterResult(proxy);
      },
    },
    0
  );
}

// En la ventana con Tor, una línea violeta bajo la barra para distinguirla.
const ESTILO_TOR =
  "data:text/css," +
  encodeURIComponent("#nav-bar { box-shadow: inset 0 -3px #7d4698 !important; }");

// ── Siempre privado y extensiones ───────────────────────────────────────
// Con «Siempre privado» todas las ventanas son privadas, y Gecko solo corre en
// ellas las extensiones que tienen ese permiso: sin él quedarían apagadas del
// todo. En el primer arranque con el modo prendido, Velbrum se lo da a las que
// ya estaban, y después a cada una que se instale. Si se lo sacás a una en
// Complementos, queda sacado.
const PREF_PRIVADO_EXTENSIONES = "velbrum.privado.extensiones";
const PERMISO_PRIVADO = { permissions: ["internal:privateBrowsingAllowed"], origins: [] };

async function permitirEnPrivado(addon) {
  if (addon.type != "extension" || addon.isBuiltin || addon.isSystem || addon.incognito == "not_allowed") {
    return;
  }
  if (!(addon.permissions & lazy.AddonManager.PERM_CAN_CHANGE_PRIVATEBROWSING_ACCESS)) {
    return;
  }
  const politica = WebExtensionPolicy.getByID(addon.id);
  if (politica?.privateBrowsingAllowed) {
    return;
  }
  await lazy.ExtensionPermissions.add(addon.id, PERMISO_PRIVADO, politica?.extension);
  if (addon.isActive) {
    await addon.reload();
  }
}

async function extensionesEnPrivado() {
  if (!lazy.PrivateBrowsingUtils.permanentPrivateBrowsing) {
    Services.prefs.clearUserPref(PREF_PRIVADO_EXTENSIONES);
    return;
  }
  lazy.AddonManager.addAddonListener({
    onInstalled: (addon) => permitirEnPrivado(addon).catch((e) => console.error("Velbrum: extensión en privado", e)),
  });
  if (Services.prefs.getBoolPref(PREF_PRIVADO_EXTENSIONES, false)) {
    return;
  }
  for (const addon of await lazy.AddonManager.getAddonsByTypes(["extension"])) {
    try {
      await permitirEnPrivado(addon);
    } catch (error) {
      console.error(`Velbrum: no se pudo permitir ${addon.id} en ventanas privadas`, error);
    }
  }
  Services.prefs.setBoolPref(PREF_PRIVADO_EXTENSIONES, true);
}

// Velbrum antes se llamaba Bruma: los ajustes guardados con el nombre viejo
// (bruma.*) pasan a velbrum.* una vez.
function migrarAjustesViejos() {
  for (const viejo of Services.prefs.getChildList("bruma.")) {
    const nuevo = "velbrum." + viejo.slice("bruma.".length);
    if (Services.prefs.prefHasUserValue(viejo) && !Services.prefs.prefHasUserValue(nuevo)) {
      const tipo = Services.prefs.getPrefType(viejo);
      if (tipo == Services.prefs.PREF_BOOL) {
        Services.prefs.setBoolPref(nuevo, Services.prefs.getBoolPref(viejo));
      } else if (tipo == Services.prefs.PREF_INT) {
        Services.prefs.setIntPref(nuevo, Services.prefs.getIntPref(viejo));
      } else if (tipo == Services.prefs.PREF_STRING) {
        Services.prefs.setStringPref(nuevo, Services.prefs.getStringPref(viejo));
      }
    }
    Services.prefs.clearUserPref(viejo);
  }
}

// ── Bordes de privacidad al cambiar el tamaño de la ventana ──────────────
// Firefox recalcula el tamaño redondeado de la página con un ResizeObserver,
// pero en Wayland al maximizar o restaurar lee las medidas de antes: la página
// queda un paso atrasada (más chica que la ventana, o más grande y corrida, con
// la barra de desplazamiento afuera). Cuando la ventana termina de cambiar de
// tamaño, se vuelve a calcular con las medidas ya asentadas.
function bordesAlRedimensionar(ventana) {
  let espera = null;
  const recalcular = () => {
    ventana.clearTimeout(espera);
    espera = ventana.setTimeout(() => {
      if (ventana.closed || !ventana.gBrowser) {
        return;
      }
      if (!Services.prefs.getBoolPref("privacy.resistFingerprinting.letterboxing", false)) {
        return;
      }
      try {
        lazy.RFPHelper._updateSizeForTabsInWindow(ventana);
      } catch (error) {
        console.error("Velbrum: bordes de privacidad", error);
      }
    }, 250);
  };
  ventana.addEventListener("resize", recalcular);
  ventana.addEventListener("sizemodechange", recalcular);
}

export function iniciar(ventana) {
  if (ventana) {
    ventana.addEventListener(
      "load",
      () => {
        try {
          menusDeTor(ventana);
        } catch (error) {
          console.error("Velbrum: menús de Tor", error);
        }
        try {
          bordesAlRedimensionar(ventana);
        } catch (error) {
          console.error("Velbrum: bordes de privacidad", error);
        }
      },
      { once: true }
    );
  }
  if (creado) {
    return;
  }
  creado = true;
  try {
    migrarAjustesViejos();
  } catch (error) {
    console.error("Velbrum: ajustes viejos", error);
  }
  if (CON_TOR) {
    aislarCircuitos();
  } else {
    if (!Services.prefs.prefHasUserValue(PREF_LIVIANO) && Services.sysinfo.getProperty("memsize") < POCA_MEMORIA) {
      // PC con poca memoria y sin elección del usuario: modo liviano.
      aplicarLiviano(true);
    }
    extensionesEnPrivado().catch((error) => console.error("Velbrum: extensiones en privado", error));
    // Paquetes: cómo terminó la última actualización, y la versión que quedó
    // preparada se instala al cerrar (cuando ya es seguro que se cierra: si
    // se cancela, por ejemplo en «¿Cerrar las pestañas?», no se arranca nada).
    if (instalacionPaquete()) {
      lazy.setTimeout(() => mostrarResultado().catch(error => console.error("Velbrum:", error)), 2000);
      Services.obs.addObserver((_sujeto, _tema, datos) => {
        if (datos != "restart" && lazy.paquete.hayPendiente()) {
          lazy.paquete.aplicar(relanzarAlCerrar);
        }
      }, "quit-application");
    }
    // Actualizaciones: al minuto de abrir y después cada 3 horas (la búsqueda
    // en GitHub es una vez por día).
    lazy.setTimeout(() => revisarActualizaciones(), 60 * 1000);
    lazy.setInterval(() => revisarActualizaciones(), 3 * 3600 * 1000);
  }
  lazy.CustomizableUI.createWidget({
    id: ID,
    type: "button",
    defaultArea: lazy.CustomizableUI.AREA_NAVBAR,
    label: CON_TOR ? "Velbrum con Tor" : "Velbrum",
    tooltiptext: CON_TOR ? "Velbrum con Tor: ajustes" : "Ajustes de privacidad de Velbrum",
    onCreated(nodo) {
      nodo.setAttribute("image", ICONO);
      if (CON_TOR) {
        nodo.ownerGlobal.windowUtils.loadSheetUsingURIString(ESTILO_TOR, Ci.nsIDOMWindowUtils.AUTHOR_SHEET);
      }
    },
    onCommand: abrir,
  });
}
