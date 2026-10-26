// Velbrum para Android: el cartel «Hay una versión nueva» abajo en la página
// (lo pone actualizar.js). Cerrado: la página no puede leerlo ni tocarlo. El
// botón «Actualizar» es un enlace al APK en las versiones de Velbrum en
// GitHub: la descarga la hace el navegador, y al abrirla Android pregunta si
// actualizar. Sin id ni marcas en la página (que no sepa que es Velbrum) y sin
// decirle a GitHub de qué sitio venís (noreferrer). La marca de «ya está» es
// del mundo aislado de la extensión, que la página no ve.
(async () => {
  if (globalThis.velbrumAvisoActualizacion) return;
  globalThis.velbrumAvisoActualizacion = true;
  const nueva = await browser.runtime.sendMessage({ accion: "actualizacion-datos" });
  const deGitHub = (url) => /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/releases\/download\/[^?#]+\.apk$/.test(url ?? "");
  if (!nueva || !deGitHub(nueva.apk)) {
    globalThis.velbrumAvisoActualizacion = false;
    return;
  }

  const anfitrion = document.createElement("div");
  const sombra = anfitrion.attachShadow({ mode: "closed" });
  sombra.innerHTML = `
    <style>
      :host { all: initial; position: fixed; left: 12px; right: 12px; bottom: 12px; z-index: 2147483647;
              font: 15px/1.45 system-ui, sans-serif; }
      .caja { background: #1b1450; color: #fff; border-radius: 16px; padding: 14px 16px;
              box-shadow: 0 8px 28px rgba(0,0,0,.35); max-width: 480px; margin: 0 auto; }
      .titulo { font-size: 12px; opacity: .8; margin-bottom: 4px; }
      .botones { display: flex; gap: 8px; margin-top: 12px; }
      a, button { flex: 1; font: inherit; font-weight: 600; border: 0; border-radius: 10px; padding: 10px 12px;
                  text-align: center; text-decoration: none; cursor: pointer; }
      a { background: #8573ff; color: #fff; }
      button { background: transparent; color: #fff; box-shadow: inset 0 0 0 1px rgba(255,255,255,.45); font-weight: 500; }
    </style>
    <div class="caja">
      <div class="titulo">Velbrum</div>
      <div class="texto"></div>
      <div class="botones"><a class="actualizar">Actualizar</a><button type="button" class="tarde">Más tarde</button></div>
    </div>`;
  const texto = sombra.querySelector(".texto");
  texto.textContent = `Hay una versión nueva de Velbrum: ${nueva.version} (tenés la ${nueva.actual}).`;
  const actualizar = sombra.querySelector(".actualizar");
  actualizar.href = nueva.apk;
  actualizar.rel = "noreferrer";
  actualizar.referrerPolicy = "no-referrer";
  actualizar.addEventListener("click", (evento) => {
    if (!evento.isTrusted) return evento.preventDefault();
    browser.runtime.sendMessage({ accion: "actualizacion-bajando" });
    texto.textContent =
      "Bajando la versión nueva. Cuando termine, tocá «Abrir» y después «Actualizar»: Android solo la " +
      "instala si está firmada con la misma clave que tu Velbrum.";
    setTimeout(() => sombra.querySelector(".botones").remove(), 0);
  });
  sombra.querySelector(".tarde").addEventListener("click", (evento) => {
    if (!evento.isTrusted) return;
    browser.runtime.sendMessage({ accion: "actualizacion-mas-tarde" });
    anfitrion.remove();
  });
  document.documentElement.append(anfitrion);
})();
