// Bruma: lo que comparten los botones de las tiendas (tienda.js en la de
// Chrome, edge.js en la de Edge): el cartel de abajo a la derecha y el pedido
// de instalación a background.js. Se carga antes que ellos.

var TEXTO_BRUMA = "Agregar a Bruma";

// ── Mensajes (abajo a la derecha) ─────────────────────────────────────────
let aviso = null;
// Con `alTocar`, el cartel lleva el botón «Agregar a Bruma».
function mostrar(texto, alTocar = null) {
  if (!aviso) {
    const anfitrion = document.createElement("div");
    anfitrion.id = "bruma-aviso";
    // Cerrado: la página no puede leer ni tocar el cartel ni su botón.
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
        button:disabled { opacity: .6; cursor: progress; }
        [hidden] { display: none; }
      </style>
      <div class="caja"><div class="titulo">Bruma</div><div class="texto"></div>
        <button type="button" hidden>${TEXTO_BRUMA}</button></div>`;
    aviso = { anfitrion, texto: sombra.querySelector(".texto"), boton: sombra.querySelector("button") };
    aviso.boton.addEventListener("click", (evento) => {
      if (evento.isTrusted) aviso?.alTocar?.();
    });
    document.documentElement.append(anfitrion);
  }
  aviso.texto.textContent = texto;
  aviso.alTocar = alTocar;
  aviso.boton.hidden = !alTocar;
}
function ocultar() {
  aviso?.anfitrion.remove();
  aviso = null;
}
function hayAviso() {
  return aviso !== null;
}

// ── Instalación ───────────────────────────────────────────────────────────
let instalando = false;
// `accion`: «instalar-chrome» o «instalar-edge» (de qué tienda bajarla).
async function instalarEnBruma(accion, id) {
  if (!id || instalando) return;
  instalando = true;
  const reintentar = () => instalarEnBruma(accion, id);
  mostrar("Descargando la extensión y adaptándola a Bruma…");
  try {
    const r = await browser.runtime.sendMessage({ accion, id });
    if (r?.ok) {
      const avisos = r.avisos?.length ? `\n\nTené en cuenta:\n• ${r.avisos.join("\n• ")}` : "";
      mostrar(`${r.nombre} ${r.version}: tocá «Agregar» en el cartel del navegador.${avisos}`);
    } else {
      mostrar(`No se pudo instalar: ${r?.error ?? "error desconocido"}`, reintentar);
    }
  } catch (error) {
    mostrar(`No se pudo instalar: ${error.message}`, reintentar);
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
    if (texto === TEXTO_BRUMA) return;
    if (texto && esDeLaTienda(texto)) {
      nodo.textContent = TEXTO_BRUMA;
      return;
    }
  }
}

// Habilita el botón de la tienda y hace que instale en Bruma.
function adaptarBoton(boton, esDeLaTienda, alTocar) {
  if (boton.disabled) boton.disabled = false;
  if (boton.getAttribute("aria-disabled") === "true") boton.setAttribute("aria-disabled", "false");
  cambiarTexto(boton, esDeLaTienda);
  if (!boton.dataset.bruma) {
    boton.dataset.bruma = "1";
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
