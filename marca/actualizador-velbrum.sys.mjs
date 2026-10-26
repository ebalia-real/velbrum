/* Velbrum: actualizador de los paquetes para Windows, macOS y Linux sin Nix
 * (portable/). En NixOS no se usa: ahí actualiza velbrum-actualizar con un
 * rebuild (host/actualizar.sh).
 *
 * Lo usa la barra de actualización de ajustes-velbrum.sys.mjs:
 * 1. buscar(): la última versión publicada en GitHub (releases/latest).
 * 2. preparar(): baja SHA256SUMS y su firma, verifica la firma con la clave de
 *    Velbrum que trae el paquete instalado (firmas/claves-permitidas, espacio
 *    de nombres «velbrum-paquetes»), baja el paquete de este sistema, verifica
 *    su suma y lo descomprime en <datos>/actualizacion. Si algo no coincide,
 *    no se instala nada.
 * 3. aplicar(): al cerrar Velbrum (enseguida, con «Reiniciar ahora»), un
 *    script (portable/actualizar/aplicar.sh o aplicar.ps1) espera a que se
 *    cierre, reemplaza los archivos del programa (nunca la carpeta «datos») o
 *    corre el instalador nuevo, y vuelve a abrir Velbrum. Si algo falla, deja
 *    la versión anterior.
 * 4. resultado(): al abrir de nuevo, cómo terminó.
 *
 * Qué se actualiza:
 * - Windows: el instalado (se corre el instalador nuevo, sin preguntas) y el
 *   portable (.zip);
 * - macOS: Velbrum.app, instalada o portable (.zip);
 * - Linux: el portable (.tar.gz) y el AppImage. Los .deb, .rpm y de Arch los
 *   actualiza el sistema: para esos, como para las carpetas en las que no se
 *   puede escribir, queda el botón «Descargar». */

const SISTEMA = Services.appinfo.OS; // "WINNT", "Darwin" o "Linux"
const WINDOWS = SISTEMA == "WINNT";
const MACOS = SISTEMA == "Darwin";
const ESPACIO_FIRMA = "velbrum-paquetes";
const VERSION_VALIDA = /^\d{4}\.\d{2}\.\d{2}(\.\d+)?$/;
// (VELBRUM_SERVIDOR_ACTUALIZACIONES solo sirve para probar con un servidor
// local: lo que baje de ahí igual tiene que estar firmado con la clave de
// Velbrum.)
const SERVIDOR = Services.env.get("VELBRUM_SERVIDOR_ACTUALIZACIONES") || "https://api.github.com";

let pendiente = null;
let aplicado = false;

function archivo(ruta) {
  const a = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsIFile);
  a.initWithPath(ruta);
  return a;
}

function existe(ruta) {
  try {
    return archivo(ruta).exists();
  } catch {
    return false;
  }
}

function carpetaActualizacion() {
  const datos = Services.env.get("VELBRUM_DATOS");
  return datos ? PathUtils.join(datos, "actualizacion") : null;
}

// Cómo está instalado este Velbrum, o null si no lo puede actualizar solo
// (NixOS, un paquete viejo sin el actualizador).
export function instalacion() {
  const exe = Services.dirsvc.get("XREExeF", Ci.nsIFile);
  let recursos, destino, tipo, nombre;
  if (MACOS) {
    // Velbrum.app/Contents/MacOS/librewolf
    const app = exe.parent.parent.parent;
    recursos = PathUtils.join(app.path, "Contents", "Resources", "velbrum");
    destino = app.path;
    tipo = "app";
    const arq = Services.appinfo.XPCOMABI.startsWith("aarch64") ? "arm64" : "x86_64";
    nombre = v => `velbrum-${v}-macos-${arq}-portable.zip`;
  } else {
    // <raíz>/navegador/librewolf(.exe)
    const raiz = exe.parent.parent.path;
    recursos = destino = raiz;
    if (WINDOWS && existe(PathUtils.join(raiz, "unins000.exe"))) {
      tipo = "instalador";
      nombre = v => `velbrum-${v}-windows-x86_64-instalador.exe`;
    } else if (WINDOWS) {
      tipo = "carpeta";
      nombre = v => `velbrum-${v}-windows-x86_64-portable.zip`;
    } else if (Services.env.get("APPIMAGE")) {
      tipo = "archivo";
      destino = Services.env.get("APPIMAGE");
      nombre = v => `velbrum-${v}-linux-x86_64.AppImage`;
    } else if (existe(PathUtils.join(raiz, "portable"))) {
      tipo = "carpeta";
      nombre = v => `velbrum-${v}-linux-x86_64-portable.tar.gz`;
    } else {
      tipo = "sistema"; // .deb, .rpm o Arch: lo actualiza el gestor de paquetes
    }
  }
  const script = PathUtils.join(recursos, "actualizar", WINDOWS ? "aplicar.ps1" : "aplicar.sh");
  const claves = PathUtils.join(recursos, "firmas", "claves-permitidas");
  if (!carpetaActualizacion() || !existe(script) || !existe(claves)) {
    return null;
  }
  return { tipo, destino, nombre, script, claves };
}

// ¿Se puede escribir donde está instalado? (Si no, «Descargar».)
export async function sePuedeInstalar(inst) {
  if (!inst || inst.tipo == "sistema") {
    return false;
  }
  if (inst.tipo == "instalador") {
    return true; // se instala para el usuario, sin permisos de administrador
  }
  const prueba = PathUtils.join(PathUtils.parent(inst.destino), `.velbrum-prueba-${Date.now()}`);
  try {
    await IOUtils.write(prueba, new Uint8Array(0));
    await IOUtils.remove(prueba);
    return true;
  } catch {
    return false;
  }
}

// La última versión publicada, si tiene sus sumas firmadas y el paquete de
// este sistema: {version, recursos: {nombre: url}}.
export async function buscar(ventana, repo, inst) {
  const respuesta = await ventana.fetch(`${SERVIDOR}/repos/${repo}/releases/latest`, {
    credentials: "omit",
    cache: "no-store",
  });
  if (!respuesta.ok) {
    throw new Error(`GitHub respondió ${respuesta.status}`);
  }
  const datos = await respuesta.json();
  const etiqueta = String(datos.tag_name || "");
  const version = etiqueta.slice(1);
  if (!etiqueta.startsWith("v") || !VERSION_VALIDA.test(version)) {
    return null;
  }
  const recursos = {};
  for (const r of datos.assets || []) {
    recursos[String(r.name)] = String(r.browser_download_url);
  }
  if (!recursos.SHA256SUMS || !recursos["SHA256SUMS.sig"]) {
    return null; // todavía sin firmar: se ofrece cuando esté
  }
  if (inst.nombre && !recursos[inst.nombre(version)]) {
    return null;
  }
  return { version, recursos };
}

// ── Firma SSH (ssh-keygen -Y sign) ───────────────────────────────────────
// Formato: PROTOCOL.sshsig de OpenSSH. Solo claves ed25519.
function lector(bytes) {
  let i = 0;
  return {
    u32() {
      if (i + 4 > bytes.length) {
        throw new Error("firma cortada");
      }
      const v = ((bytes[i] << 24) | (bytes[i + 1] << 16) | (bytes[i + 2] << 8) | bytes[i + 3]) >>> 0;
      i += 4;
      return v;
    },
    crudo(n) {
      if (i + n > bytes.length) {
        throw new Error("firma cortada");
      }
      const v = bytes.subarray(i, i + n);
      i += n;
      return v;
    },
    cadena() {
      return this.crudo(this.u32());
    },
    alFinal() {
      return i == bytes.length;
    },
  };
}

function cadenaSSH(bytes) {
  const salida = new Uint8Array(4 + bytes.length);
  new DataView(salida.buffer).setUint32(0, bytes.length);
  salida.set(bytes, 4);
  return salida;
}

function unir(partes) {
  const salida = new Uint8Array(partes.reduce((n, p) => n + p.length, 0));
  let i = 0;
  for (const p of partes) {
    salida.set(p, i);
    i += p.length;
  }
  return salida;
}

const texto = t => new TextEncoder().encode(t);
const iguales = (a, b) => a.length == b.length && a.every((x, i) => x == b[i]);
const base64 = t => Uint8Array.from(atob(t), c => c.charCodeAt(0));

// Las claves de claves-permitidas que pueden firmar paquetes.
function clavesPermitidas(contenido) {
  const claves = [];
  for (const linea of contenido.split("\n")) {
    const m = linea.match(/^\S+\s+namespaces="([^"]*)"\s+ssh-ed25519\s+([A-Za-z0-9+/=]+)/);
    if (m && m[1].split(",").includes(ESPACIO_FIRMA)) {
      claves.push(base64(m[2]));
    }
  }
  return claves;
}

export async function verificarFirma(ventana, mensaje, firmaArmada, contenidoClaves) {
  const cuerpo = firmaArmada
    .replace(/-----BEGIN SSH SIGNATURE-----|-----END SSH SIGNATURE-----|\s/g, "");
  const l = lector(base64(cuerpo));
  if (new TextDecoder().decode(l.crudo(6)) != "SSHSIG" || l.u32() != 1) {
    throw new Error("la firma no tiene el formato de ssh-keygen");
  }
  const clave = l.cadena();
  const espacio = l.cadena();
  const reservado = l.cadena();
  const algoritmo = new TextDecoder().decode(l.cadena());
  const firma = lector(l.cadena());
  if (!l.alFinal()) {
    throw new Error("la firma tiene datos de más");
  }
  if (new TextDecoder().decode(espacio) != ESPACIO_FIRMA) {
    throw new Error("la firma no es de un paquete de Velbrum");
  }
  if (!clavesPermitidas(contenidoClaves).some(c => iguales(c, clave))) {
    throw new Error("la firma no es de una clave de Velbrum");
  }
  const lc = lector(clave);
  if (new TextDecoder().decode(lc.cadena()) != "ssh-ed25519") {
    throw new Error("clave de un tipo no admitido");
  }
  const publica = lc.cadena();
  if (new TextDecoder().decode(firma.cadena()) != "ssh-ed25519") {
    throw new Error("firma de un tipo no admitido");
  }
  const bytesFirma = firma.cadena();
  const resumen = { sha512: "SHA-512", sha256: "SHA-256" }[algoritmo];
  if (!resumen || publica.length != 32 || bytesFirma.length != 64) {
    throw new Error("firma no admitida");
  }
  const subtle = ventana.crypto.subtle;
  const hash = new Uint8Array(await subtle.digest(resumen, mensaje));
  const firmado = unir([
    texto("SSHSIG"),
    cadenaSSH(espacio),
    cadenaSSH(reservado),
    cadenaSSH(texto(algoritmo)),
    cadenaSSH(hash),
  ]);
  const llave = await subtle.importKey("raw", publica, { name: "Ed25519" }, false, ["verify"]);
  if (!(await subtle.verify({ name: "Ed25519" }, llave, bytesFirma, firmado))) {
    throw new Error("la firma no es válida");
  }
}

// ── Bajar, verificar y descomprimir ──────────────────────────────────────
async function bajarTexto(ventana, url) {
  const r = await ventana.fetch(url, { credentials: "omit", cache: "no-store" });
  if (!r.ok) {
    throw new Error(`no se pudo bajar ${url} (${r.status})`);
  }
  return new Uint8Array(await r.arrayBuffer());
}

// Baja a un archivo de a pedazos y devuelve su SHA-256 (hex).
async function bajarArchivo(ventana, url, ruta, progreso) {
  const r = await ventana.fetch(url, { credentials: "omit", cache: "no-store" });
  if (!r.ok) {
    throw new Error(`no se pudo bajar el paquete (${r.status})`);
  }
  const total = Number(r.headers.get("content-length")) || 0;
  const hash = Cc["@mozilla.org/security/hash;1"].createInstance(Ci.nsICryptoHash);
  hash.init(hash.SHA256);
  await IOUtils.write(ruta, new Uint8Array(0));
  const leer = r.body.getReader();
  let pedazos = [];
  let juntado = 0;
  let bajado = 0;
  const volcar = async () => {
    if (juntado) {
      await IOUtils.write(ruta, unir(pedazos), { mode: "append" });
      pedazos = [];
      juntado = 0;
    }
  };
  for (;;) {
    const { done, value } = await leer.read();
    if (done) {
      break;
    }
    hash.update(value, value.length);
    pedazos.push(value);
    juntado += value.length;
    bajado += value.length;
    if (juntado >= 8 * 1024 * 1024) {
      await volcar();
    }
    if (total) {
      progreso(bajado / total);
    }
  }
  await volcar();
  return Array.from(hash.finish(false), c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("");
}

function correr(programa, argumentos) {
  return new Promise((resolver, rechazar) => {
    const proceso = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
    proceso.init(archivo(programa));
    proceso.startHidden = true;
    proceso.runwAsync(argumentos, argumentos.length, {
      observe(_sujeto, tema) {
        if (tema == "process-finished" && proceso.exitValue == 0) {
          resolver();
        } else {
          rechazar(new Error(`${PathUtils.filename(programa)} salió con ${proceso.exitValue}`));
        }
      },
    });
  });
}

async function descomprimir(paquete, carpeta) {
  if (MACOS) {
    // ditto conserva los enlaces, permisos y la firma de la app.
    await correr("/usr/bin/ditto", ["-x", "-k", paquete, carpeta]);
    return PathUtils.join(carpeta, "Velbrum Portable", "Velbrum.app");
  }
  if (WINDOWS) {
    // tar.exe viene con Windows 10 (1803) y 11, y descomprime .zip.
    const tar = PathUtils.join(Services.dirsvc.get("SysD", Ci.nsIFile).path, "tar.exe");
    await correr(tar, ["-xf", paquete, "-C", carpeta]);
  } else {
    const tar = ["/usr/bin/tar", "/bin/tar"].find(existe);
    if (!tar) {
      throw new Error("no encontré tar");
    }
    await correr(tar, ["-xzf", paquete, "-C", carpeta]);
  }
  return PathUtils.join(carpeta, "Velbrum");
}

// Deja la versión nueva lista para aplicar(). progreso(texto) va contando.
export async function preparar(ventana, inst, encontrada, progreso) {
  const carpeta = carpetaActualizacion();
  pendiente = null;
  await IOUtils.remove(carpeta, { recursive: true, ignoreAbsent: true });
  await IOUtils.makeDirectory(carpeta, { permissions: 0o700 });

  progreso("Verificando la firma…");
  const sumas = await bajarTexto(ventana, encontrada.recursos.SHA256SUMS);
  const firma = new TextDecoder().decode(await bajarTexto(ventana, encontrada.recursos["SHA256SUMS.sig"]));
  await verificarFirma(ventana, sumas, firma, await IOUtils.readUTF8(inst.claves));
  // El nombre del paquete lleva la versión: así la firma también cubre la
  // versión (nadie puede ofrecer un paquete viejo como si fuera nuevo).
  const nombre = inst.nombre(encontrada.version);
  const linea = new TextDecoder()
    .decode(sumas)
    .split("\n")
    .map(l => l.trim().split(/\s+\*?/))
    .find(([, n]) => n == nombre);
  if (!linea || !/^[0-9a-f]{64}$/.test(linea[0])) {
    throw new Error(`SHA256SUMS no tiene ${nombre}`);
  }

  const paquete = PathUtils.join(carpeta, nombre);
  let ultimo = -1;
  const suma = await bajarArchivo(ventana, encontrada.recursos[nombre], paquete, parte => {
    const porcentaje = Math.floor(parte * 100);
    if (porcentaje != ultimo) {
      ultimo = porcentaje;
      progreso(`Bajando Velbrum ${encontrada.version}… ${porcentaje} %`);
    }
  });
  if (suma != linea[0]) {
    await IOUtils.remove(paquete, { ignoreAbsent: true });
    throw new Error("el paquete bajado no coincide con su suma firmada");
  }

  let nueva = paquete;
  if (inst.tipo == "carpeta" || inst.tipo == "app") {
    progreso("Descomprimiendo…");
    const destino = PathUtils.join(carpeta, "nueva");
    await IOUtils.makeDirectory(destino);
    nueva = await descomprimir(paquete, destino);
    const lanzador = MACOS
      ? PathUtils.join(nueva, "Contents", "MacOS", "velbrum")
      : PathUtils.join(nueva, WINDOWS ? "velbrum.exe" : "velbrum");
    if (!(await IOUtils.exists(lanzador))) {
      throw new Error("el paquete no tiene el formato esperado");
    }
    await IOUtils.remove(paquete);
  } else if (inst.tipo == "archivo") {
    await IOUtils.setPermissions(paquete, 0o755);
  }
  // El script se corre desde acá: el del programa se va a reemplazar.
  const script = PathUtils.join(carpeta, PathUtils.filename(inst.script));
  await IOUtils.copy(inst.script, script);
  pendiente = { version: encontrada.version, tipo: inst.tipo, nueva, destino: inst.destino, script };
  await IOUtils.writeJSON(PathUtils.join(carpeta, "pendiente.json"), pendiente);
  return pendiente;
}

export function hayPendiente() {
  return Boolean(pendiente) && !aplicado;
}

// Arranca el script que instala la versión preparada cuando se cierre
// Velbrum (relanzar: después la vuelve a abrir). Hay que cerrar Velbrum
// enseguida.
export function aplicar(relanzar) {
  if (!pendiente || aplicado) {
    return false;
  }
  const pid = String(Services.appinfo.processID);
  let programa, argumentos;
  if (WINDOWS) {
    programa = PathUtils.join(
      Services.dirsvc.get("SysD", Ci.nsIFile).path, "WindowsPowerShell", "v1.0", "powershell.exe"
    );
    argumentos = [
      "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
      "-File", pendiente.script,
      "-Modo", pendiente.tipo, "-Proceso", pid, "-Nueva", pendiente.nueva,
      "-Destino", pendiente.destino, "-Relanzar", relanzar ? "1" : "0",
    ];
  } else {
    programa = "/bin/sh";
    argumentos = [pendiente.script, pendiente.tipo, pid, pendiente.nueva, pendiente.destino, relanzar ? "1" : "0"];
  }
  const proceso = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
  proceso.init(archivo(programa));
  proceso.startHidden = true;
  proceso.runwAsync(argumentos, argumentos.length);
  aplicado = true;
  return true;
}

// Cómo terminó la última actualización (al abrir Velbrum de nuevo):
// {version, error} o null. Después borra la carpeta.
export async function resultado() {
  const carpeta = carpetaActualizacion();
  if (!carpeta) {
    return null;
  }
  let texto;
  try {
    texto = (await IOUtils.readUTF8(PathUtils.join(carpeta, "resultado"))).trim();
  } catch {
    return null; // nada aplicado (o el script todavía no terminó)
  }
  let version = "";
  try {
    version = (await IOUtils.readJSON(PathUtils.join(carpeta, "pendiente.json"))).version;
  } catch {}
  let registro = "";
  try {
    registro = await IOUtils.readUTF8(PathUtils.join(carpeta, "registro.txt"));
  } catch {}
  await IOUtils.remove(carpeta, { recursive: true, ignoreAbsent: true });
  if (texto == "ok") {
    return { version, error: null };
  }
  if (registro) {
    console.warn("Velbrum: registro de la actualización\n" + registro);
  }
  return { version, error: texto.replace(/^error:?\s*/, "") || "error desconocido" };
}
