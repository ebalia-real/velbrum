// Velbrum: pide los permisos que Chrome concede al instalar y Gecko solo como
// opcionales (por ejemplo userScripts). Ver fondo.js.
const permisos = new URLSearchParams(location.search).get("permisos")?.split(",").filter(Boolean) ?? [];
document.getElementById("nombre").textContent = browser.runtime.getManifest().name;
document.getElementById("lista").textContent = permisos.join(", ");
document.getElementById("permitir").addEventListener("click", async () => {
  const estado = document.getElementById("estado");
  try {
    if (await browser.permissions.request({ permissions: permisos })) {
      estado.textContent = "Listo. Reiniciando la extensión…";
      setTimeout(() => browser.runtime.reload(), 800);
    } else {
      estado.textContent = "No se concedió el permiso. Podés volver a intentarlo.";
    }
  } catch (error) {
    estado.textContent = `No se pudo pedir el permiso: ${error.message}`;
  }
});
