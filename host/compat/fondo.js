// Bruma: compatibilidad de extensiones de Chrome en Bruma (motor Gecko).
// Se carga antes que el código de la extensión convertida (ver
// extensiones_chrome.py). En Chrome el fondo es un service worker; en Gecko es
// una página de fondo («event page»), que tiene casi la misma API y además DOM.
(() => {
  "use strict";
  const g = globalThis;
  const api = g.chrome;
  const navegador = g.browser;
  if (!api || !navegador) return;

  // Promesa o callback, como en Chrome: si el último argumento es una función
  // se usa como callback y runtime.lastError queda disponible.
  const dual = (funcion) =>
    function (...args) {
      const callback = typeof args[args.length - 1] === "function" ? args.pop() : null;
      const promesa = Promise.resolve().then(() => funcion.apply(this, args));
      if (!callback) return promesa;
      promesa.then(
        (valor) => callback(valor),
        (error) => {
          console.error("Bruma (compatibilidad Chrome):", error);
          callback(undefined);
        },
      );
      return undefined;
    };

  // ── Service worker → página de fondo ────────────────────────────────────
  // Los scripts de importScripts() con rutas escritas en el código ya se
  // cargaron antes (los agrega el conversor al manifiesto). Si son fragmentos
  // de webpack, quedaron anotados en su variable global antes de que
  // arrancara webpack, que con importScripts no los procesa solo: se los
  // entregamos cuando los pide. Los demás (rutas que salen de una variable)
  // se cargan acá, a continuación del script que los pide.
  const fragmentosPendientes = new Map(); // variable global → [push propio, entradas]
  let permisosPedidos = [];
  // En un service worker, importScripts resuelve las rutas desde el script
  // del service worker, no desde la página.
  let baseSW = location.href;
  // Lo llama bruma-compat/config.js, que arma el conversor para cada extensión.
  g.__brumaConfigurar = ({ fragmentos = [], permisos = [], sw = null } = {}) => {
    prepararFragmentos(fragmentos);
    permisosPedidos = permisos;
    if (sw) baseSW = new URL(`/${sw}`, location.href).href;
  };
  const prepararFragmentos = (nombres) => {
    for (const nombre of nombres) {
      const lista = (g[nombre] = g[nombre] || []);
      const entradas = [];
      const pushPropio = function (...elementos) {
        if (lista.push === pushPropio) entradas.push(...elementos);
        return Array.prototype.push.apply(lista, elementos);
      };
      lista.push = pushPropio;
      fragmentosPendientes.set(nombre, [pushPropio, entradas]);
    }
  };
  const cargados = new Set();
  const cargar = (ruta) => {
    const url = new URL(String(ruta), baseSW).href;
    if (cargados.has(url) || [...document.scripts].some((s) => s.src === url)) return;
    cargados.add(url);
    const script = document.createElement("script");
    script.src = url;
    script.onerror = () => console.error(`Bruma: importScripts no pudo cargar ${url}`);
    // Mientras la página de fondo se arma, document.write lo deja en orden,
    // justo después del script actual; más tarde solo se puede agregar.
    if (document.readyState === "loading") document.write(script.outerHTML);
    else (document.head || document.documentElement).append(script);
  };
  if (typeof g.importScripts !== "function") {
    g.importScripts = (...rutas) => {
      rutas.forEach(cargar);
      for (const [nombre, [pushPropio, entradas]] of fragmentosPendientes) {
        const lista = g[nombre];
        if (!lista || lista.push === pushPropio) continue; // webpack todavía no arrancó
        while (entradas.length) lista.push(entradas.shift());
      }
    };
  }
  if (typeof g.skipWaiting !== "function") g.skipWaiting = () => Promise.resolve();
  if (!g.clients) {
    g.clients = {
      claim: () => Promise.resolve(),
      matchAll: () => Promise.resolve([]),
      get: () => Promise.resolve(undefined),
      openWindow: (url) => navegador.tabs.create({ url }),
    };
  }
  // Los eventos «install» y «activate» del service worker se disparan cuando
  // la extensión se instala o se actualiza (runtime.onInstalled).
  const oyentesSW = { install: [], activate: [] };
  const agregarOyente = g.addEventListener.bind(g);
  g.addEventListener = function (tipo, oyente, opciones) {
    if (tipo in oyentesSW) {
      oyentesSW[tipo].push(oyente);
      return;
    }
    return agregarOyente(tipo, oyente, opciones);
  };
  const dispararSW = async (tipo) => {
    for (const oyente of oyentesSW[tipo]) {
      const pendientes = [];
      const evento = { type: tipo, waitUntil: (p) => pendientes.push(p) };
      try {
        (typeof oyente === "function" ? oyente : oyente.handleEvent).call(g, evento);
        await Promise.allSettled(pendientes);
      } catch (error) {
        console.error(`Bruma: error en el evento ${tipo} del service worker:`, error);
      }
    }
  };
  // Permisos que Chrome concede al instalar y Gecko solo como opcionales
  // (userScripts): se piden en una página propia, con un botón.
  const revisarPermisos = async () => {
    const faltan = [];
    for (const permiso of permisosPedidos) {
      if (!(await navegador.permissions.contains({ permissions: [permiso] }))) faltan.push(permiso);
    }
    if (faltan.length) {
      await navegador.tabs.create({
        url: navegador.runtime.getURL(`bruma-compat/permisos.html?permisos=${faltan.join(",")}`),
      });
    }
  };
  navegador.runtime.onInstalled.addListener(async () => {
    await dispararSW("install");
    await dispararSW("activate");
    await revisarPermisos();
  });

  // ── chrome.offscreen: un iframe dentro de la página de fondo ────────────
  let documentoOculto = null;
  if (!api.offscreen) {
    api.offscreen = {
      Reason: new Proxy({}, { get: (_, nombre) => String(nombre) }),
      createDocument: dual(({ url }) => {
        if (documentoOculto) throw new Error("Only a single offscreen document may be created.");
        documentoOculto = document.createElement("iframe");
        documentoOculto.src = new URL(url, location.href).href;
        const listo = new Promise((resolver) =>
          documentoOculto.addEventListener("load", () => resolver(), { once: true }),
        );
        (document.body || document.documentElement).appendChild(documentoOculto);
        return listo;
      }),
      closeDocument: dual(() => {
        if (!documentoOculto) throw new Error("No current offscreen document.");
        documentoOculto.remove();
        documentoOculto = null;
      }),
      hasDocument: dual(() => Boolean(documentoOculto)),
    };
  }
  if (!api.runtime.getContexts) {
    api.runtime.ContextType ??= {
      TAB: "TAB",
      POPUP: "POPUP",
      BACKGROUND: "BACKGROUND",
      OFFSCREEN_DOCUMENT: "OFFSCREEN_DOCUMENT",
      SIDE_PANEL: "SIDE_PANEL",
    };
    api.runtime.getContexts = dual((filtro = {}) => {
      const contextos = [];
      if (documentoOculto) {
        contextos.push({
          contextType: "OFFSCREEN_DOCUMENT",
          documentUrl: documentoOculto.src,
          documentOrigin: location.origin,
          incognito: false,
          frameId: -1,
          tabId: -1,
          windowId: -1,
        });
      }
      const tipos = filtro.contextTypes;
      return tipos ? contextos.filter((c) => tipos.includes(c.contextType)) : contextos;
    });
  }

  // ── chrome.sidePanel → barra lateral de Gecko (sidebarAction) ───────────
  if (!api.sidePanel && navegador.sidebarAction) {
    let abrirConBoton = false;
    navegador.action?.onClicked.addListener(() => {
      if (abrirConBoton) navegador.sidebarAction.toggle();
    });
    api.sidePanel = {
      setOptions: dual(async ({ path, enabled, tabId } = {}) => {
        if (path) await navegador.sidebarAction.setPanel({ panel: path, ...(tabId ? { tabId } : {}) });
        if (enabled === false) await navegador.sidebarAction.close();
      }),
      getOptions: dual(async ({ tabId } = {}) => ({
        path: await navegador.sidebarAction.getPanel(tabId ? { tabId } : {}),
        enabled: true,
      })),
      open: dual(() => navegador.sidebarAction.open()),
      close: dual(() => navegador.sidebarAction.close()),
      setPanelBehavior: dual(({ openPanelOnActionClick } = {}) => {
        abrirConBoton = Boolean(openPanelOnActionClick);
      }),
      getPanelBehavior: dual(() => ({ openPanelOnActionClick: abrirConBoton })),
    };
  }

  // ── sender.origin en los mensajes (Chrome lo manda siempre) ─────────────
  const conOrigen = (remitente) => {
    if (remitente && !remitente.origin && remitente.url) {
      try {
        remitente.origin = new URL(remitente.url).origin;
      } catch {}
    }
    return remitente;
  };
  const envolverEvento = (evento, adaptar) => {
    if (!evento?.addListener) return;
    const envoltorios = new WeakMap();
    const agregar = evento.addListener.bind(evento);
    const quitar = evento.removeListener.bind(evento);
    const tiene = evento.hasListener.bind(evento);
    evento.addListener = (oyente, ...resto) => {
      if (!envoltorios.has(oyente)) envoltorios.set(oyente, adaptar(oyente));
      return agregar(envoltorios.get(oyente), ...resto);
    };
    evento.removeListener = (oyente) => quitar(envoltorios.get(oyente) ?? oyente);
    evento.hasListener = (oyente) => tiene(envoltorios.get(oyente) ?? oyente);
  };
  for (const evento of [api.runtime.onMessage, api.runtime.onMessageExternal]) {
    envolverEvento(evento, (oyente) => function (mensaje, remitente, responder) {
      return oyente.call(this, mensaje, conOrigen(remitente), responder);
    });
  }
  for (const evento of [api.runtime.onConnect, api.runtime.onConnectExternal]) {
    envolverEvento(evento, (oyente) => function (puerto) {
      conOrigen(puerto?.sender);
      return oyente.call(this, puerto);
    });
  }

  // ── Detalles menores ────────────────────────────────────────────────────
  for (const area of ["local", "sync", "session"]) {
    const almacen = api.storage?.[area];
    if (almacen && !almacen.getBytesInUse) {
      almacen.getBytesInUse = dual(async (claves = null) => {
        const datos = await almacen.get(claves);
        return new Blob([JSON.stringify(datos)]).size;
      });
    }
  }
  // Sin políticas de empresa, Chrome devuelve {} y Gecko tira un error.
  const gestionado = api.storage?.managed;
  if (gestionado) {
    const leer = gestionado.get.bind(gestionado);
    gestionado.get = dual(async (claves) => {
      try {
        return await leer(claves ?? null);
      } catch {
        return {};
      }
    });
  }
  // Chrome avisa si se bloquean las notificaciones de la extensión; en Gecko
  // el permiso se da al instalarla y no cambia.
  const notificaciones = api.notifications;
  if (notificaciones) {
    const sinEventos = () => ({ addListener() {}, removeListener() {}, hasListener: () => false, hasListeners: () => false });
    notificaciones.getPermissionLevel ??= dual(() => "granted");
    notificaciones.onPermissionLevelChanged ??= sinEventos();
    notificaciones.onShowSettings ??= sinEventos();
  }
  if (api.identity && !api.identity.getAuthToken) {
    api.identity.getAuthToken = dual(() => {
      throw new Error("Bruma: identity.getAuthToken (cuenta de Google) no existe fuera de Chrome.");
    });
  }
})();
