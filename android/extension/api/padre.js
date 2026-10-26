/* global ExtensionAPI, ChromeUtils, IOUtils, PathUtils, Services */
// Velbrum para Android: instala un XPI con el cartel de la aplicación
// («¿Agregar …?» con sus permisos), como cuando se instala uno de
// addons.mozilla.org. Corre en el proceso principal; solo la puede usar la
// extensión de Velbrum, que viene integrada en la aplicación (las «experiment
// APIs» son solo para complementos privilegiados).
"use strict";

this.velbrum = class extends ExtensionAPI {
  getAPI() {
    return {
      velbrum: {
        async instalar(datos, nombre) {
          const { IFAddonUtils } = ChromeUtils.importESModule("moz-src:///ironfox/utils/IFAddonUtils.sys.mjs");
          const carpeta = PathUtils.join(PathUtils.profileDir, "velbrum", "extensiones");
          const ruta = PathUtils.join(carpeta, nombre);
          const uri = Services.io.newURI(PathUtils.toFileURI(ruta));
          // El interruptor «Permitir la instalación de complementos» de Ajustes.
          if (!IFAddonUtils.canInstallAddon(uri.spec)) return false;
          await IOUtils.makeDirectory(carpeta, { permissions: 0o700 });
          await IOUtils.write(ruta, new Uint8Array(datos), { tmpPath: `${ruta}.nuevo` });
          // Sin esperar: termina cuando respondés el cartel.
          IFAddonUtils.installAddon(uri).catch((error) => console.error("Velbrum: instalación", error));
          return true;
        },
        async buscarActualizaciones() {
          return Services.prefs.getBoolPref("velbrum.actualizaciones", true);
        },
      },
    };
  }
};
