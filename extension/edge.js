// Bruma: en la tienda de complementos de Edge, el botón «Obtener» («Get») de
// cada extensión, que fuera de Edge viene desactivado, la instala en Bruma.
// Sirve en la página de la extensión y en las listas de la tienda. Si la
// tienda cambia y el botón no aparece, en la página de la extensión se muestra
// uno propio abajo a la derecha. El cartel, la instalación y el seguimiento
// de la página están en aviso.js.

const RE_DETALLE = /\/addons\/detail\/(?:[^/]+\/)?([a-p]{32})(?:[/?#]|$)/;
// La tienda marca cada botón con el ID de la extensión: «installButton-ID».
const RE_ID_BOTON = /^installButton-([a-p]{32})$/;
// «Obtener» en los idiomas más comunes, por si la tienda deja de marcarlo.
const RE_OBTENER = /^(obtener|get|abrufen|obtenir|obter|ottieni|ophalen|pobierz|hämta|hent|hae|získat)$/i;

const idDeLaPagina = () => location.pathname.match(RE_DETALLE)?.[1] ?? null;
const idDelBoton = (boton) => boton.id.match(RE_ID_BOTON)?.[1] ?? idDeLaPagina();
const instalar = (boton) => instalarEnBruma("instalar-edge", boton ? idDelBoton(boton) : idDeLaPagina());
// El botón ya marcado con el ID se reconoce por eso: cualquier texto vale.
const cualquierTexto = () => true;

function botonesDeLaTienda() {
  const botones = [...document.querySelectorAll("button[id^='installButton-']")].filter((b) =>
    RE_ID_BOTON.test(b.id),
  );
  if (botones.length || !idDeLaPagina()) return botones;
  const porTexto = [...document.querySelectorAll("button")].find(
    (b) => b.dataset.bruma || RE_OBTENER.test(b.innerText.trim()),
  );
  return porTexto ? [porTexto] : [];
}

// Fuera de Edge la tienda pinta el botón como desactivado con sus propias
// clases (no con :disabled): se lo pinta como su botón principal.
function pintarBotones() {
  if (document.getElementById("bruma-estilo")) return;
  const estilo = document.createElement("style");
  estilo.id = "bruma-estilo";
  estilo.textContent = `
    button[data-bruma] { background-color: var(--colorBrandBackground, #0f6cbd) !important;
      color: var(--colorNeutralForegroundOnBrand, #fff) !important;
      border-color: transparent !important; cursor: pointer !important; }
    button[data-bruma]:hover { background-color: var(--colorBrandBackgroundHover, #115ea3) !important; }
    button[data-bruma]:active { background-color: var(--colorBrandBackgroundPressed, #0c3b5e) !important; }`;
  (document.head || document.documentElement).append(estilo);
}

// «Esta extensión no se puede instalar ya que no es compatible con la versión
// de tu navegador» (debajo del botón) y la franja «Para instalar los
// complementos, necesitarás el nuevo Microsoft Edge»: no corren en Bruma.
function ocultarAvisosDeEdge() {
  for (const e of document.querySelectorAll(".incompatible")) e.style.display = "none";
  for (const franja of document.querySelectorAll("[role=banner]")) {
    if (franja.querySelector("a[href*='microsoft.com'][href*='/edge']") && franja.style.display !== "none") {
      franja.style.display = "none";
    }
  }
}

// ── Seguir los cambios de la página ───────────────────────────────────────
let rutaAnterior = null;
let desde = 0;
seguirLaPagina(() => {
  if (location.pathname !== rutaAnterior) {
    rutaAnterior = location.pathname;
    desde = Date.now();
    ocultar();
  }
  ocultarAvisosDeEdge();
  const botones = botonesDeLaTienda();
  if (botones.length) pintarBotones();
  for (const boton of botones) {
    adaptarBoton(boton, RE_ID_BOTON.test(boton.id) ? cualquierTexto : (t) => RE_OBTENER.test(t), instalar);
  }
  if (!botones.length && idDeLaPagina() && !hayAviso() && Date.now() - desde > 4000) {
    mostrar("Esta extensión se puede usar en Bruma.", () => instalar(null));
  }
});
