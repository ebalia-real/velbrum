// Velbrum: compatibilidad de los scripts de contenido de extensiones de Chrome
// (los que corren dentro de las páginas). Va primero en cada uno (ver
// extensiones_chrome.py y velbrum-compat/fondo.js); nunca en los del «mundo»
// de la página (world: "MAIN"), que no tienen la API de la extensión.
(() => {
  "use strict";
  try {
    // (En un marco que se está cerrando, Gecko tira un error al leer la API.)
    if (typeof browser === "undefined" || typeof chrome === "undefined" || globalThis.__velbrumContenido) return;
  } catch {
    return;
  }
  globalThis.__velbrumContenido = true;

  // En Chrome, window.chrome es la API de la extensión también en estos
  // scripts. En Gecko, window es la página vista a través de un envoltorio y
  // chrome es solo una variable del script. Lo que se agrega al envoltorio lo
  // ve solo esta extensión: la página no.
  try {
    if (window.chrome === undefined) window.chrome = chrome;
  } catch {}
  // Lo mismo con Symbol: un script en un marco lee parent.Symbol.for(…), que
  // en Gecko llega sin sus métodos. Se agrega en este marco y en los de afuera
  // (los del mismo sitio; con Symbol.for todos ven los mismos símbolos).
  for (let marco = window; ; marco = marco.parent) {
    try {
      if (typeof marco.Symbol?.for !== "function") marco.Symbol = Symbol;
    } catch {} // marco de otro sitio
    if (marco === marco.parent) break;
  }

  // CustomEvent: Chrome copia el «detail» cuando el evento pasa del script a
  // la página. Gecko le pasa el objeto del script, que la página no puede leer
  // («Permission denied to access property…»), y la página se rompe. Se copia
  // a la página como en Chrome (si no se puede copiar, queda como estaba).
  const Original = window.CustomEvent;
  if (typeof cloneInto === "function" && typeof Original === "function") {
    const copiar = (inicio) => {
      if (inicio && typeof inicio === "object" && inicio.detail !== null && typeof inicio.detail === "object") {
        try {
          return { ...inicio, detail: cloneInto(inicio.detail, window, { wrapReflectors: true }) };
        } catch {}
      }
      return inicio;
    };
    const CustomEvent = function CustomEvent(tipo, inicio) {
      if (!new.target) throw new TypeError("Constructor CustomEvent requires 'new'");
      return Reflect.construct(Original, [tipo, copiar(inicio)], new.target === CustomEvent ? Original : new.target);
    };
    CustomEvent.prototype = Original.prototype;
    globalThis.CustomEvent = CustomEvent;
    try {
      window.CustomEvent = CustomEvent;
    } catch {}
    const iniciar = Original.prototype.initCustomEvent;
    if (typeof iniciar === "function") {
      Original.prototype.initCustomEvent = function (tipo, burbujea, cancelable, detalle) {
        const copia = copiar({ detail: detalle }).detail;
        return iniciar.call(this, tipo, burbujea, cancelable, copia);
      };
    }
  }
})();
