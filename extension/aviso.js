// Velbrum: lo que comparten los botones de las tiendas (tienda.js en la de
// Chrome, edge.js en la de Edge): el cartel de abajo a la derecha, la oferta de
// la versión oficial para Firefox cuando la hay y el pedido de instalación a
// background.js. Se carga antes que ellos.

var TEXTO_VELBRUM = "Agregar a Velbrum";

// ── Mensajes (abajo a la derecha) ─────────────────────────────────────────
let aviso = null;
// `botones`: una función (un botón «Agregar a Velbrum» que la llama) o una
// lista de { texto, alTocar, secundario }. Sin botones, solo el texto.
function mostrar(texto, botones = []) {
  if (typeof botones === "function") botones = [{ texto: TEXTO_VELBRUM, alTocar: botones }];
  if (!aviso) {
    const anfitrion = document.createElement("div");
    anfitrion.id = "velbrum-aviso";
    // Cerrado: la página no puede leer ni tocar el cartel ni sus botones.
    const sombra = anfitrion.attachShadow({ mode: "closed" });
    sombra.innerHTML = `
      <style>
        :host { all: initial; position: fixed; right: 24px; bottom: 24px; z-index: 2147483647;
                font: 14px/1.45 system-ui, sans-serif; }
        .caja { background: #1b1450; color: #fff; border-radius: 14px; padding: 14px 16px;
                box-shadow: 0 8px 28px rgba(0,0,0,.35); max-width: 360px; white-space: pre-line; }
        .titulo { font-size: 12px; opacity: .8; margin-bottom: 6px; }
        button { font: inherit; font-weight: 600; border: 0; border-radius: 10px; padding: 9px 16px;
                 background: #8573ff; color: #fff; cursor: pointer; margin-top: 10px; width: 100%; }
        button.secundario { background: transparent; box-shadow: inset 0 0 0 1px rgba(255,255,255,.45);
                            font-weight: 500; margin-top: 8px; }
        button:disabled { opacity: .6; cursor: progress; }
      </style>
      <div class="caja"><div class="titulo">Velbrum</div><div class="texto"></div><div class="botones"></div></div>`;
    aviso = { anfitrion, texto: sombra.querySelector(".texto"), botones: sombra.querySelector(".botones") };
    document.documentElement.append(anfitrion);
  }
  aviso.texto.textContent = texto;
  aviso.botones.replaceChildren(
    ...botones.map(({ texto, alTocar, secundario }) => {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.textContent = texto;
      if (secundario) boton.className = "secundario";
      boton.addEventListener("click", (evento) => {
        if (evento.isTrusted) alTocar();
      });
      return boton;
    }),
  );
}
function ocultar() {
  aviso?.anfitrion.remove();
  aviso = null;
}
function hayAviso() {
  return aviso !== null;
}

// ── Instalación ───────────────────────────────────────────────────────────
// background.js sabe de qué tienda es la página: acá solo va el ID.
let instalando = false;
async function instalarEnVelbrum(id) {
  if (!id || instalando) return;
  // Si la extensión tiene versión oficial para Firefox (equivalentes.json),
  // se ofrece esa primero: la hacen sus autores para Gecko y la firma Mozilla.
  let oficial = null;
  try {
    oficial = await browser.runtime.sendMessage({ accion: "equivalente", id });
  } catch {
    oficial = null;
  }
  if (oficial) ofrecerVersionDeFirefox(id, oficial);
  else pedirInstalacion("convertir", id);
}

function ofrecerVersionDeFirefox(id, oficial, texto = null) {
  mostrar(
    texto ??
      `${oficial.nombre} tiene una versión oficial para Firefox, hecha por sus autores ` +
        `y firmada por Mozilla (addons.mozilla.org). Es más confiable que adaptar la de ${oficial.tienda}.`,
    [
      { texto: "Instalar la versión de Firefox", alTocar: () => pedirInstalacion("instalar-firefox", id, oficial) },
      {
        texto: `Convertir la de ${oficial.tienda} igual`,
        alTocar: () => pedirInstalacion("convertir", id),
        secundario: true,
      },
    ],
  );
}

// `accion`: «convertir» (adaptar la de la tienda) o «instalar-firefox».
async function pedirInstalacion(accion, id, oficial = null) {
  if (instalando) return;
  instalando = true;
  const fallo = (error) =>
    oficial
      ? ofrecerVersionDeFirefox(id, oficial, `No se pudo instalar la versión de Firefox: ${error}`)
      : mostrar(`No se pudo instalar: ${error}`, () => pedirInstalacion(accion, id));
  mostrar(
    oficial
      ? "Descargando la versión de Firefox de addons.mozilla.org…"
      : "Descargando la extensión y adaptándola a Velbrum…",
  );
  try {
    const r = await browser.runtime.sendMessage({ accion, id });
    if (r?.ok) {
      const avisos = r.avisos?.length ? `\n\nTené en cuenta:\n• ${r.avisos.join("\n• ")}` : "";
      mostrar(`${r.nombre} ${r.version}: tocá «Agregar» en el cartel del navegador.${avisos}`);
    } else {
      fallo(r?.error ?? "error desconocido");
    }
  } catch (error) {
    fallo(error.message);
  } finally {
    instalando = false;
  }
}

// Cambia el texto del botón de la tienda solo en su nodo de texto, para no
// romper el ícono ni el estilo. `esDeLaTienda` elige qué texto reemplazar.
function cambiarTexto(boton, esDeLaTienda) {
  const caminante = document.createTreeWalker(boton, NodeFilter.SHOW_TEXT);
  for (let nodo = caminante.nextNode(); nodo; nodo = caminante.nextNode()) {
    const texto = nodo.textContent.trim();
    if (texto === TEXTO_VELBRUM) return;
    if (texto && esDeLaTienda(texto)) {
      nodo.textContent = TEXTO_VELBRUM;
      return;
    }
  }
}

// Habilita el botón de la tienda y hace que instale en Velbrum.
function adaptarBoton(boton, esDeLaTienda, alTocar) {
  if (boton.disabled) boton.disabled = false;
  if (boton.getAttribute("aria-disabled") === "true") boton.setAttribute("aria-disabled", "false");
  cambiarTexto(boton, esDeLaTienda);
  if (!boton.dataset.velbrum) {
    boton.dataset.velbrum = "1";
    boton.addEventListener(
      "click",
      (evento) => {
        evento.preventDefault();
        evento.stopImmediatePropagation();
        // Solo un clic tuyo de verdad: un script de la página puede «hacer
        // clic» en el botón, pero esos clics no son isTrusted.
        if (evento.isTrusted) alTocar(boton);
      },
      true,
    );
  }
}

// La tienda es una página que cambia la URL sin recargar y redibuja sus
// botones: `revisar` se repite con cada cambio de la página.
function seguirLaPagina(revisar) {
  let pendiente = null;
  const revisarPronto = () => {
    pendiente ??= setTimeout(() => {
      pendiente = null;
      revisar();
    }, 120);
  };
  new MutationObserver(revisarPronto).observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["disabled", "aria-disabled"],
  });
  setInterval(revisar, 1000);
  revisar();
}
