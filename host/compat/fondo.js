// Velbrum: compatibilidad de extensiones de Chrome en Velbrum (motor Gecko).
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
          // Como en Chrome: el error queda en runtime.lastError mientras corre
          // el callback.
          const anterior = Object.getOwnPropertyDescriptor(api.runtime, "lastError");
          try {
            Object.defineProperty(api.runtime, "lastError", {
              value: { message: String(error?.message ?? error) },
              configurable: true,
            });
          } catch {
            console.error("Velbrum (compatibilidad Chrome):", error);
          }
          try {
            callback(undefined);
          } finally {
            try {
              if (anterior) Object.defineProperty(api.runtime, "lastError", anterior);
              else delete api.runtime.lastError;
            } catch {}
          }
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
  // Lo llama velbrum-compat/config.js, que arma el conversor para cada extensión.
  g.__velbrumConfigurar = ({ fragmentos = [], permisos = [], sw = null } = {}) => {
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
    script.onerror = () => console.error(`Velbrum: importScripts no pudo cargar ${url}`);
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
  // El propio service worker y su registro (self.serviceWorker,
  // self.registration): MetaMask, por ejemplo, arranca cuando ve
  // serviceWorker.state === "activated".
  if (!("serviceWorker" in g)) {
    const propio = new EventTarget();
    Object.defineProperties(propio, {
      state: { value: "activated", enumerable: true },
      scriptURL: { get: () => baseSW, enumerable: true },
    });
    propio.onstatechange = propio.onerror = null;
    propio.postMessage = () => {};
    g.serviceWorker = propio;
  }
  if (!("registration" in g)) {
    const registro = new EventTarget();
    Object.assign(registro, {
      scope: `${location.origin}/`,
      active: g.serviceWorker,
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
      showNotification: async (titulo, opciones = {}) => {
        await navegador.notifications?.create({
          type: "basic",
          title: String(titulo),
          message: String(opciones.body ?? ""),
          ...(opciones.icon ? { iconUrl: String(opciones.icon) } : {}),
        });
      },
    });
    g.registration = registro;
  }

  // ── Mensajes entre las páginas de la extensión y el «service worker» ────
  // En Chrome, la ventana emergente, las opciones o el documento oculto le
  // escriben al fondo con navigator.serviceWorker.controller.postMessage, y el
  // fondo les contesta con clients.matchAll() → client.postMessage. En Gecko
  // esas páginas no tienen navigator.serviceWorker: velbrum-compat/pagina.js
  // arma uno que entrega los mensajes acá, y acá cada página es un «client».
  const esPuerto = (x) => Object.prototype.toString.call(x) === "[object MessagePort]";
  const listaDeTransferencia = (t) => (Array.isArray(t) ? t : Array.isArray(t?.transfer) ? t.transfer : []);
  const clientesPorVentana = new WeakMap();
  const cliente = (vista) => {
    let c = clientesPorVentana.get(vista);
    if (!c) {
      c = {
        id: vista.__velbrumSW.id,
        type: "window",
        get url() {
          return vista.location.href;
        },
        get frameType() {
          return vista === vista.top ? "top-level" : "nested";
        },
        get visibilityState() {
          return vista.document.visibilityState;
        },
        get focused() {
          return vista.document.hasFocus();
        },
        postMessage(mensaje, transferir) {
          vista.__velbrumSW.entregar(mensaje, listaDeTransferencia(transferir));
        },
        focus: async () => {
          vista.focus();
          return c;
        },
        navigate: async (url) => {
          vista.location.href = new URL(url, vista.location.href).href;
          return c;
        },
      };
      clientesPorVentana.set(vista, c);
    }
    return c;
  };
  const vistas = () => {
    const todas = new Set(navegador.extension.getViews?.() || []);
    if (documentoOculto?.contentWindow) todas.add(documentoOculto.contentWindow);
    return [...todas].filter((v) => {
      try {
        return v !== g && !v.closed && v.__velbrumSW;
      } catch {
        return false; // ventana ya cerrada
      }
    });
  };
  g.__velbrumSW = {
    get scriptURL() {
      return baseSW;
    },
    recibir(vista, mensaje, transferir) {
      const transferencia = listaDeTransferencia(transferir);
      const { data, ports } = g.structuredClone(
        { data: mensaje, ports: transferencia.filter(esPuerto) },
        { transfer: transferencia },
      );
      const evento = new MessageEvent("message", { data, ports, origin: location.origin });
      Object.defineProperty(evento, "source", { value: cliente(vista) });
      evento.waitUntil = () => {};
      g.dispatchEvent(evento);
    },
  };
  {
    const clientes = (g.clients ??= {});
    clientes.claim ??= () => Promise.resolve();
    clientes.matchAll = async ({ type = "window" } = {}) =>
      type === "window" || type === "all" ? vistas().map(cliente) : [];
    clientes.get = async (id) => vistas().map(cliente).find((c) => c.id === id);
    clientes.openWindow ??= async (url) => {
      await navegador.tabs.create({ url: new URL(url, baseSW).href });
      return null;
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
        console.error(`Velbrum: error en el evento ${tipo} del service worker:`, error);
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
        url: navegador.runtime.getURL(`velbrum-compat/permisos.html?permisos=${faltan.join(",")}`),
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
  // Gecko tiene runtime.getContexts, pero no conoce el documento oculto
  // emulado y rechaza el tipo OFFSCREEN_DOCUMENT: se suman los dos.
  {
    const tiposDeGecko = Object.values(navegador.runtime.ContextType || {});
    const delNavegador = navegador.runtime.getContexts?.bind(navegador.runtime);
    try {
      api.runtime.ContextType = {
        TAB: "TAB",
        POPUP: "POPUP",
        BACKGROUND: "BACKGROUND",
        SIDE_PANEL: "SIDE_PANEL",
        ...(api.runtime.ContextType || {}),
        OFFSCREEN_DOCUMENT: "OFFSCREEN_DOCUMENT",
      };
    } catch {}
    const emulados = () =>
      documentoOculto
        ? [
            {
              contextType: "OFFSCREEN_DOCUMENT",
              contextId: "velbrum-documento-oculto",
              documentUrl: documentoOculto.src,
              documentOrigin: location.origin,
              incognito: false,
              frameId: -1,
              tabId: -1,
              windowId: -1,
            },
          ]
        : [];
    api.runtime.getContexts = dual(async (filtro = {}) => {
      const tipos = filtro.contextTypes;
      let propios = [];
      if (delNavegador) {
        const conocidos = tipos?.filter((t) => tiposDeGecko.includes(t));
        if (!tipos || conocidos.length) {
          propios = await delNavegador(tipos ? { ...filtro, contextTypes: conocidos } : filtro);
        }
      }
      const coincide = (c) =>
        (!tipos || tipos.includes(c.contextType)) &&
        (!filtro.documentUrls || filtro.documentUrls.includes(c.documentUrl)) &&
        (!filtro.documentOrigins || filtro.documentOrigins.includes(c.documentOrigin));
      return [...propios, ...emulados().filter(coincide)];
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

  // ── Scripts de contenido: la capa de compatibilidad va primero ──────────
  // (velbrum-compat/contenido.js; el conversor ya la agrega a los del
  // manifiesto, acá se suma a los que la extensión registra o inyecta.)
  const CONTENIDO = "velbrum-compat/contenido.js";
  const sinCompat = (js) => (Array.isArray(js) ? js.filter((r) => String(r).replace(/^\//, "") !== CONTENIDO) : js);
  const conCompat = (js, mundo) =>
    mundo === "MAIN" || !Array.isArray(js) || !js.length ? js : [CONTENIDO, ...sinCompat(js)];
  // (En Gecko chrome.X y browser.X pueden ser el mismo objeto: se guardan las
  // funciones originales antes de reemplazarlas.)
  const scripting = api.scripting;
  const scriptingOriginal = {};
  for (const nombre of ["registerContentScripts", "updateContentScripts", "getRegisteredContentScripts", "executeScript"]) {
    if (navegador.scripting?.[nombre]) scriptingOriginal[nombre] = navegador.scripting[nombre].bind(navegador.scripting);
  }
  if (scripting) {
    for (const nombre of ["registerContentScripts", "updateContentScripts"]) {
      if (!scriptingOriginal[nombre]) continue;
      scripting[nombre] = dual((scripts) =>
        scriptingOriginal[nombre]((scripts || []).map((s) => (s?.js ? { ...s, js: conCompat(s.js, s.world) } : s))),
      );
    }
    if (scriptingOriginal.getRegisteredContentScripts) {
      scripting.getRegisteredContentScripts = dual(async (filtro) =>
        (await scriptingOriginal.getRegisteredContentScripts(filtro)).map((s) =>
          s.js ? { ...s, js: sinCompat(s.js) } : s,
        ),
      );
    }
    if (scriptingOriginal.executeScript) {
      scripting.executeScript = dual((opciones) =>
        scriptingOriginal.executeScript(
          opciones?.files ? { ...opciones, files: conCompat(opciones.files, opciones.world) } : opciones,
        ),
      );
    }
  }

  // ── declarativeNetRequest: reglas con condiciones que Gecko no tiene ────
  // (por ejemplo responseHeaders, de Chrome 128): Gecko rechaza la llamada
  // entera y la extensión no arranca. Se omiten solo esas reglas.
  const dnr = api.declarativeNetRequest;
  for (const nombre of ["updateDynamicRules", "updateSessionRules"]) {
    const original = navegador.declarativeNetRequest?.[nombre]?.bind(navegador.declarativeNetRequest);
    if (!dnr?.[nombre] || !original) continue;
    dnr[nombre] = dual(async (opciones = {}) => {
      const reglas = [...(opciones.addRules || [])];
      for (;;) {
        try {
          return await original({ ...opciones, addRules: reglas });
        } catch (error) {
          const texto = String(error?.message ?? error);
          const regla = /addRules\.(\d+)\./.exec(texto);
          if (!regla || Number(regla[1]) >= reglas.length || !/Unexpected property|Invalid enumeration/.test(texto)) {
            throw error;
          }
          console.warn(`Velbrum: se omite una regla de declarativeNetRequest que Gecko no entiende (${texto})`);
          reglas.splice(Number(regla[1]), 1);
        }
      }
    });
  }

  // ── Detalles menores ────────────────────────────────────────────────────
  // Funciones de la ventana que el código copia a otro objeto y llama desde
  // ahí: en Gecko fallan si no se llaman sobre la ventana.
  for (const nombre of ["requestIdleCallback", "cancelIdleCallback", "requestAnimationFrame", "cancelAnimationFrame"]) {
    if (typeof g[nombre] === "function") g[nombre] = g[nombre].bind(g);
  }
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
      throw new Error("Velbrum: identity.getAuthToken (cuenta de Google) no existe fuera de Chrome.");
    });
  }
})();
