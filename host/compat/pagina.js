// Velbrum: compatibilidad de extensiones de Chrome en sus propias páginas
// (ventana emergente, opciones, documento oculto…). Va primero en cada página
// de la extensión salvo la de fondo (ver extensiones_chrome.py).
//
// En Chrome estas páginas le hablan al service worker de fondo con
// navigator.serviceWorker (controller.postMessage, ready, onmessage). En Gecko
// el fondo es una página y las extensiones no tienen navigator.serviceWorker:
// acá se arma uno que le entrega los mensajes a la página de fondo, donde
// velbrum-compat/fondo.js los convierte en eventos «message» del service
// worker y trata a cada página como un «client».
(() => {
  "use strict";
  if (typeof chrome === "undefined" || !chrome.runtime?.id || "serviceWorker" in navigator || window.__velbrumSW) {
    return;
  }
  // Funciones de la ventana que el código copia a otro objeto y llama desde
  // ahí: en Gecko fallan si no se llaman sobre la ventana.
  for (const nombre of ["requestIdleCallback", "cancelIdleCallback", "requestAnimationFrame", "cancelAnimationFrame"]) {
    if (typeof window[nombre] === "function") window[nombre] = window[nombre].bind(window);
  }

  const fondo = () => {
    try {
      const pagina = chrome.extension.getBackgroundPage();
      return pagina && pagina !== window && pagina.__velbrumSW ? pagina : null;
    } catch {
      return null;
    }
  };
  const esPuerto = (x) => Object.prototype.toString.call(x) === "[object MessagePort]";
  const listaDeTransferencia = (t) => (Array.isArray(t) ? t : Array.isArray(t?.transfer) ? t.transfer : []);

  // El service worker visto desde esta página (controller y registration.active).
  let trabajador = null;
  let fondoDelTrabajador = null;
  const elTrabajador = () => {
    const pagina = fondo();
    if (!pagina) return null;
    if (fondoDelTrabajador !== pagina) {
      fondoDelTrabajador = pagina;
      trabajador = new EventTarget();
      Object.defineProperties(trabajador, {
        state: { value: "activated", enumerable: true },
        scriptURL: { value: pagina.__velbrumSW.scriptURL, enumerable: true },
      });
      trabajador.onstatechange = trabajador.onerror = null;
      trabajador.postMessage = (mensaje, transferir) => {
        const destino = fondo();
        if (!destino) throw new DOMException("El fondo de la extensión no está corriendo.", "InvalidStateError");
        destino.__velbrumSW.recibir(window, mensaje, transferir);
      };
    }
    return trabajador;
  };

  const registro = new EventTarget();
  Object.defineProperty(registro, "active", { get: elTrabajador, enumerable: true });
  Object.assign(registro, {
    scope: `${location.origin}/`,
    installing: null,
    waiting: null,
    updateViaCache: "imports",
    onupdatefound: null,
    navigationPreload: {
      enable: async () => {},
      disable: async () => {},
      setHeaderValue: async () => {},
      getState: async () => ({ enabled: false, headerValue: "true" }),
    },
    update: async () => registro,
    unregister: async () => false,
    getNotifications: async () => [],
    showNotification: async () => {},
  });

  // Listo cuando corre el fondo (runtime.getBackgroundPage lo despierta).
  const listo = new Promise((resolver) => {
    const probar = () => (elTrabajador() ? resolver(registro) : setTimeout(probar, 100));
    Promise.resolve(chrome.runtime.getBackgroundPage?.(() => void chrome.runtime.lastError))
      .catch(() => {})
      .finally(probar);
  });

  // Los mensajes del fondo esperan hasta que la página empieza a escuchar
  // (onmessage, startMessages() o el fin de la carga), como en Chrome.
  const contenedor = new EventTarget();
  const enEspera = [];
  let habilitado = false;
  const habilitar = () => {
    if (habilitado) return;
    habilitado = true;
    for (const evento of enEspera.splice(0)) contenedor.dispatchEvent(evento);
  };
  let alMensaje = null;
  Object.defineProperties(contenedor, {
    // Sin «controller», como una página que el service worker no controla:
    // con él, algunas extensiones (Stylus) esperan datos que su service worker
    // mete en la página al servirla, y eso no se puede imitar. Las que lo usan
    // caen en «ready», que sí funciona.
    controller: { value: null, enumerable: true },
    ready: { value: listo, enumerable: true },
    onmessage: {
      get: () => alMensaje,
      set: (oyente) => {
        if (alMensaje) contenedor.removeEventListener("message", alMensaje);
        alMensaje = typeof oyente === "function" ? oyente : null;
        if (alMensaje) contenedor.addEventListener("message", alMensaje);
        habilitar();
      },
      enumerable: true,
    },
  });
  Object.assign(contenedor, {
    oncontrollerchange: null,
    onmessageerror: null,
    register: async () => registro,
    getRegistration: async () => registro,
    getRegistrations: async () => [registro],
    startMessages: habilitar,
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", habilitar, { once: true });
  } else {
    queueMicrotask(habilitar);
  }

  Object.defineProperty(window, "__velbrumSW", {
    value: {
      id: crypto.randomUUID(),
      entregar(mensaje, transferir) {
        const transferencia = listaDeTransferencia(transferir);
        const { data, ports } = structuredClone(
          { data: mensaje, ports: transferencia.filter(esPuerto) },
          { transfer: transferencia },
        );
        const evento = new MessageEvent("message", { data, ports, origin: location.origin });
        Object.defineProperty(evento, "source", { value: elTrabajador() });
        if (habilitado) contenedor.dispatchEvent(evento);
        else enEspera.push(evento);
      },
    },
  });
  Object.defineProperty(navigator, "serviceWorker", { value: contenedor, configurable: true, enumerable: true });
})();
