// Bruma: en la Chrome Web Store, el botón «Agregar a Chrome» de la tienda
// instala la extensión en Bruma. Si la tienda cambia y el botón no aparece, se
// muestra uno propio abajo a la derecha. El cartel, la instalación y el
// seguimiento de la página están en aviso.js.

const RE_DETALLE = /\/detail\/(?:[^/]+\/)?([a-p]{32})(?:[/?#]|$)/;
// «Agregar a Chrome» en los idiomas más comunes de la tienda.
const RE_AGREGAR =
  /^(agregar|añadir|add|ajouter|hinzufügen|adicionar|aggiungi|toevoegen|dodaj|lägg till|tilføj|legg til|lisää|přidat)\b.*\bchrome$/i;
const RE_NO_GRACIAS = /^(no,? gracias|no,? thanks|non merci|nein,? danke|não,? obrigado)$/i;

const idActual = () => location.pathname.match(RE_DETALLE)?.[1] ?? null;
const instalar = () => instalarEnBruma("instalar-chrome", idActual());
const esAgregarAChrome = (texto) => RE_AGREGAR.test(texto);

// ── Botón de la tienda ────────────────────────────────────────────────────
function botonDeLaTienda() {
  for (const boton of document.querySelectorAll("button")) {
    if (esAgregarAChrome(boton.innerText.trim()) || boton.dataset.bruma) return boton;
  }
  return null;
}

// El cartel «¿Quieres cambiar a Chrome?» se cierra con su propio «No, gracias».
function cerrarCartelDeChrome() {
  for (const boton of document.querySelectorAll("button")) {
    if (!RE_NO_GRACIAS.test(boton.innerText.trim())) continue;
    const cartel = boton.closest("aside, [role=dialog], [role=alertdialog]");
    if (cartel && /chrome/i.test(cartel.innerText)) boton.click();
  }
}

// La franja fija «Cambia a Chrome para instalar extensiones» no tiene botón
// para cerrarla: se oculta el contenedor más alto que no incluye el botón de
// instalar.
const RE_FRANJA = /^(cambia a chrome|switch to chrome|wechsle zu chrome|passez à chrome|mude para o chrome)/i;
function ocultarFranjaDeChrome() {
  const caminante = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let nodo = caminante.nextNode(); nodo; nodo = caminante.nextNode()) {
    if (!RE_FRANJA.test(nodo.textContent.trim())) continue;
    let franja = null;
    for (let e = nodo.parentElement; e && e !== document.body; e = e.parentElement) {
      if (e.querySelector("[data-bruma]") || e.getBoundingClientRect().height > 120) break;
      franja = e;
    }
    if (franja && franja.style.display !== "none") franja.style.display = "none";
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
  cerrarCartelDeChrome();
  if (!idActual()) return;
  const boton = botonDeLaTienda();
  if (boton) {
    adaptarBoton(boton, esAgregarAChrome, instalar);
    ocultarFranjaDeChrome();
  } else if (!hayAviso() && Date.now() - desde > 4000) {
    mostrar("Esta extensión de Chrome se puede usar en Bruma.", instalar);
  }
});
