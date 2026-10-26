// Velbrum para Android: extensiones de Chrome → complementos de Gecko, dentro
// del navegador. Es la misma conversión que host/extensiones_chrome.py en la
// PC (en Android no hay mensajería nativa para correr ese programa): baja la
// extensión de la tienda de Chrome o de la de Edge, verifica la firma del
// autor (CRX3), adapta el manifiesto y agrega la capa de compatibilidad
// (compat/, la misma host/compat de la PC). Las listas de permisos y claves
// de Chrome salen de host/extensiones_chrome.py (tablas.json, lo arma
// android/reempaquetar.py), así las dos conversiones no se separan.
//
// Diferencias con la PC: no hay sufijos anteriores (@chrome.bruma), ni
// interruptor de firmas, ni actualización diaria de las convertidas (se
// actualizan volviendo a tocar «Agregar a Velbrum» en la tienda).

const VERSION_CHROMIUM = "@versionChromium@";
const SUFIJO_ID = "@chrome.velbrum";
const URL_TIENDA = "https://clients2.google.com/service/update2/crx";
const URL_EDGE = "https://edge.microsoft.com/extensionwebstorebase/v1/crx";
const CDN_EDGE = "msedgeextensions.sf.tlu.dl.delivery.mp.microsoft.com";
const SERVIDORES_CONSULTA = new Set(["clients2.google.com", "edge.microsoft.com"]);
const NOMBRES_TIENDAS = { chrome: "la tienda de Chrome", edge: "la tienda de Edge" };
const URL_SIN_ACTUALIZACIONES = "https://localhost/velbrum/sin-actualizaciones.json";
const SERVIDOR_AMO = "addons.mozilla.org";
const API_AMO = `https://${SERVIDOR_AMO}/api/v5/addons/addon/`;
const RE_SLUG = /^[a-z0-9][a-z0-9_-]{0,99}$/;
const RE_IMPORT_SCRIPTS = /\bimportScripts\s*\(([^)]*)\)/g;
const RE_TEXTO = /(['"])((?:\\.|(?!\1).)*)\1/g;
const RE_COMODIN_CHROME = /\{\w+:\w+\}/;

class ErrorExtension extends Error {}

const recurso = (ruta) => browser.runtime.getURL(ruta);
let tablasCargadas = null;
// SIN_EQUIVALENTE, EMULADOS, CLAVES_DE_CHROME, VERSION_COMPAT… de la PC.
const tablas = () => (tablasCargadas ??= fetch(recurso("tablas.json")).then((r) => r.json()));
const codificar = (texto) => new TextEncoder().encode(texto);
const decodificar = (bytes) => new TextDecoder("utf-8").decode(bytes);

// ── Red ────────────────────────────────────────────────────────────────────
async function leerConLimite(flujo, maximo, donde) {
  const lector = flujo.getReader();
  const partes = [];
  let total = 0;
  for (;;) {
    const { done, value } = await lector.read();
    if (done) break;
    total += value.length;
    if (total > maximo) {
      lector.cancel().catch(() => {});
      throw new ErrorExtension(`lo que mandó ${donde} es demasiado grande`);
    }
    partes.push(value);
  }
  const salida = new Uint8Array(total);
  let i = 0;
  for (const parte of partes) {
    salida.set(parte, i);
    i += parte.length;
  }
  return salida;
}

// Descarga `url`; con `soloHttps`, no acepta http ni redirecciones a http.
async function pedir(url, donde = NOMBRES_TIENDAS.chrome, soloHttps = true) {
  const { MAXIMO_DESCARGA } = await tablas();
  const esquema = new URL(url).protocol;
  if (esquema !== "https:" && (soloHttps || esquema !== "http:")) {
    throw new ErrorExtension(`dirección no permitida para ${donde}: ${url}`);
  }
  const mayor = VERSION_CHROMIUM.split(".")[0];
  let respuesta;
  try {
    respuesta = await fetch(url, {
      credentials: "omit",
      cache: "no-store",
      headers: {
        "User-Agent": `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${mayor}.0.0.0 Safari/537.36`,
      },
    });
  } catch (error) {
    throw new ErrorExtension(`no pude conectarme con ${donde}: ${error.message}`);
  }
  if (soloHttps && new URL(respuesta.url).protocol !== "https:") {
    throw new ErrorExtension(`${donde} redirigió a una dirección sin https`);
  }
  if (!respuesta.ok) throw new ErrorExtension(`no pude conectarme con ${donde}: HTTP ${respuesta.status}`);
  return leerConLimite(respuesta.body, MAXIMO_DESCARGA, donde);
}

async function sha256(datos) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", datos));
}
const hex = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");

// (versión, url, sha256) de la última versión en la tienda, o null.
async function consultar(idChrome, version = "0.0.0.0", tienda = "chrome") {
  const x = encodeURIComponent(`id=${idChrome}&v=${version}&uc`);
  const url =
    tienda === "edge"
      ? `${URL_EDGE}?prodversion=${VERSION_CHROMIUM}&prod=chromiumcrx&prodchannel=&x=${x}`
      : `${URL_TIENDA}?prodversion=${VERSION_CHROMIUM}&acceptformat=crx3&x=${x}`;
  if (!SERVIDORES_CONSULTA.has(new URL(url).hostname)) {
    throw new ErrorExtension(`servidor no permitido para ${NOMBRES_TIENDAS[tienda]}`);
  }
  const xml = new DOMParser().parseFromString(decodificar(await pedir(url, NOMBRES_TIENDAS[tienda])), "text/xml");
  if (xml.getElementsByTagName("parsererror").length) {
    throw new ErrorExtension(`${NOMBRES_TIENDAS[tienda]} respondió algo inesperado`);
  }
  for (const nodo of xml.getElementsByTagName("*")) {
    if (nodo.localName !== "updatecheck") continue;
    if (nodo.getAttribute("status") === "ok" && nodo.getAttribute("codebase")) {
      return [nodo.getAttribute("version"), nodo.getAttribute("codebase"), nodo.getAttribute("hash_sha256")];
    }
    return null;
  }
  return null;
}

// Baja el CRX que indicó la tienda y comprueba que sea el que anunció.
async function descargar(url, hashSha256, tienda) {
  const intentos = [url];
  const partes = new URL(url);
  if (partes.protocol === "http:") {
    const segura = new URL(url);
    segura.protocol = "https:";
    if (partes.hostname.endsWith(".tlu.dl.delivery.mp.microsoft.com")) segura.host = CDN_EDGE;
    intentos.unshift(segura.href);
    if (!hashSha256) intentos.length = 1; // sin hash no hay cómo verificar lo que llega por http
  }
  let datos = null;
  let fallo = null;
  for (const intento of intentos) {
    try {
      datos = await pedir(intento, NOMBRES_TIENDAS[tienda], !hashSha256);
      break;
    } catch (error) {
      fallo = error;
    }
  }
  if (!datos) throw fallo;
  if (hashSha256 && hex(await sha256(datos)) !== hashSha256.toLowerCase()) {
    throw new ErrorExtension(`lo que bajé de ${NOMBRES_TIENDAS[tienda]} no es lo que anunció (el hash no coincide)`);
  }
  return datos;
}

// ── Versiones oficiales para Firefox (addons.mozilla.org) ──────────────────
let equivalentesCargados = null;
async function equivalente(idChrome, tienda = "chrome") {
  equivalentesCargados ??= fetch(recurso("equivalentes.json"))
    .then((r) => r.json())
    .catch(() => []);
  const tabla = await equivalentesCargados;
  return (
    (Array.isArray(tabla) ? tabla : []).find(
      (fila) => fila && tienda in NOMBRES_TIENDAS && fila[tienda] === idChrome && RE_SLUG.test(String(fila.amo ?? "")),
    ) ?? null
  );
}

function archivoAmo(respuesta) {
  let version, url, hash, compatible, publico;
  try {
    const datos = JSON.parse(decodificar(respuesta));
    version = datos.current_version;
    ({ url, hash } = version.file);
    compatible = "firefox" in (version.compatibility || {});
    publico = datos.status === "public" && !datos.is_disabled;
  } catch {
    throw new ErrorExtension("addons.mozilla.org respondió algo inesperado");
  }
  if (!publico || !compatible) throw new ErrorExtension("la versión para Firefox ya no está disponible en addons.mozilla.org");
  const partes = new URL(String(url));
  if (partes.protocol !== "https:" || partes.hostname !== SERVIDOR_AMO) {
    throw new ErrorExtension(`addons.mozilla.org indicó una dirección no permitida: ${url}`);
  }
  const [algoritmo, suma] = String(hash).split(":");
  if (algoritmo !== "sha256" || !/^[0-9a-f]{64}$/.test(suma ?? "")) {
    throw new ErrorExtension("addons.mozilla.org no indicó el hash del archivo");
  }
  return [String(version.version ?? ""), String(url), suma];
}

// La versión oficial para Firefox, firmada por Mozilla (Gecko verifica esa
// firma al instalarla).
async function prepararFirefox(idChrome, tienda) {
  const fila = await equivalente(idChrome, tienda);
  if (!fila) throw new ErrorExtension(`la extensión ${idChrome} no tiene una versión para Firefox conocida`);
  const [version, url, suma] = archivoAmo(await pedir(`${API_AMO}${fila.amo}/`, SERVIDOR_AMO));
  const xpi = await pedir(url, SERVIDOR_AMO);
  if (hex(await sha256(xpi)) !== suma) {
    throw new ErrorExtension("lo que bajé de addons.mozilla.org no es lo que anunció (el hash no coincide)");
  }
  return {
    xpi: xpi.buffer,
    archivo: `${fila.amo}.xpi`,
    info: { id_chrome: idChrome, tienda, amo: fila.amo, nombre: fila.nombre || fila.amo, version, avisos: [] },
  };
}

// ── Firma CRX3 ─────────────────────────────────────────────────────────────
// «Cr24», versión 3, una cabecera protobuf con las firmas y el zip. El ID son
// los primeros 16 bytes del SHA-256 de la clave pública del autor; la firma
// (RSA PKCS#1 v1.5 con SHA-256) cubre la cabecera firmada y todo el zip.
const PREFIJO_FIRMA = codificar("CRX3 SignedData\0");
const DIGESTINFO_SHA256 = Uint8Array.from("3031300d060960864801650304020105000420".match(/../g), (h) => parseInt(h, 16));
const OID_RSA = "2a864886f70d010101";

function varint(datos, i) {
  let valor = 0;
  let desplazamiento = 0;
  for (;;) {
    if (i >= datos.length) throw new RangeError("protobuf cortado");
    const byte = datos[i++];
    valor += (byte & 0x7f) * 2 ** desplazamiento;
    if (!(byte & 0x80)) return [valor, i];
    desplazamiento += 7;
  }
}

// Campos «length-delimited» de un mensaje protobuf: [[campo, bytes], …].
function camposProtobuf(datos) {
  const campos = [];
  let i = 0;
  while (i < datos.length) {
    let clave;
    [clave, i] = varint(datos, i);
    const campo = Math.floor(clave / 8);
    const tipo = clave & 7;
    if (tipo === 0) [, i] = varint(datos, i);
    else if (tipo === 1) i += 8;
    else if (tipo === 5) i += 4;
    else if (tipo === 2) {
      let largo;
      [largo, i] = varint(datos, i);
      if (i + largo > datos.length) throw new RangeError("protobuf cortado");
      campos.push([campo, datos.subarray(i, i + largo)]);
      i += largo;
    } else break;
  }
  return campos;
}
const comoMapa = (campos) => new Map(campos);

const aLetras = (digest) => Array.from(hex(digest.subarray(0, 16)), (c) => String.fromCharCode(97 + parseInt(c, 16))).join("");

// Un elemento DER desde `i`: [etiqueta, contenido, posición siguiente].
function der(datos, i) {
  if (i + 2 > datos.length) throw new RangeError("DER cortado");
  const etiqueta = datos[i];
  let largo = datos[i + 1];
  i += 2;
  if (largo & 0x80) {
    const n = largo & 0x7f;
    if (!(n > 0 && n <= 4)) throw new RangeError("DER inválido");
    largo = 0;
    for (let j = 0; j < n; j++) largo = largo * 256 + datos[i + j];
    i += n;
  }
  if (i + largo > datos.length) throw new RangeError("DER cortado");
  return [etiqueta, datos.subarray(i, i + largo), i + largo];
}

const entero = (bytes) => (bytes.length ? BigInt(`0x${hex(bytes)}`) : 0n);

// [n, e] de una clave pública RSA en formato SubjectPublicKeyInfo.
function claveRsa(spki) {
  const [etiqueta, secuencia] = der(spki, 0);
  const [, algoritmo, i] = der(secuencia, 0);
  const [, oid] = der(algoritmo, 0);
  if (etiqueta !== 0x30 || hex(oid) !== OID_RSA) return null;
  const [etiquetaBits, bits] = der(secuencia, i);
  if (etiquetaBits !== 0x03 || !bits.length || bits[0] !== 0) return null;
  const [, rsa] = der(bits.subarray(1), 0);
  const [, n, j] = der(rsa, 0);
  const [, e] = der(rsa, j);
  return [entero(n), entero(e)];
}

function potenciaModular(base, exponente, modulo) {
  let resultado = 1n;
  base %= modulo;
  while (exponente > 0n) {
    if (exponente & 1n) resultado = (resultado * base) % modulo;
    exponente >>= 1n;
    base = (base * base) % modulo;
  }
  return resultado;
}

async function firmaRsaValida(spki, firma, mensaje) {
  let clave;
  try {
    clave = claveRsa(spki);
  } catch {
    return false;
  }
  if (!clave) return false;
  const [n, e] = clave;
  const k = Math.ceil(n.toString(2).length / 8);
  // Como Chrome: claves de 1024 bits o más (las viejas, como Google Translate
  // o Tampermonkey, todavía firman con 1024).
  if (k < 128 || firma.length !== k || e < 3n) return false;
  const recuperado = potenciaModular(entero(firma), e, n).toString(16).padStart(k * 2, "0");
  const relleno = k - 3 - DIGESTINFO_SHA256.length - 32;
  const esperado = `0001${"ff".repeat(relleno)}00${hex(DIGESTINFO_SHA256)}${hex(await sha256(mensaje))}`;
  return recuperado === esperado;
}

// Comprueba la firma del autor de un CRX3 y devuelve [ID, zip].
async function verificarCrx(datos) {
  const texto = decodificar(datos.subarray(0, 4));
  if (texto !== "Cr24") throw new ErrorExtension("no es una extensión de Chrome (CRX)");
  let cabecera, archivoZip, pruebas, firmado, crxId;
  try {
    const vista = new DataView(datos.buffer, datos.byteOffset, datos.byteLength);
    const version = vista.getUint32(4, true);
    const largo = vista.getUint32(8, true);
    if (version !== 3) throw new ErrorExtension(`formato CRX${version}: no tiene una firma que Velbrum pueda verificar`);
    cabecera = datos.subarray(12, 12 + largo);
    archivoZip = datos.subarray(12 + largo);
    if (cabecera.length !== largo) throw new ErrorExtension("el CRX está cortado");
    pruebas = [];
    firmado = new Uint8Array();
    for (const [campo, valor] of camposProtobuf(cabecera)) {
      if (campo === 2) pruebas.push(comoMapa(camposProtobuf(valor)));
      else if (campo === 10000) firmado = valor;
    }
    crxId = comoMapa(camposProtobuf(firmado)).get(1) ?? new Uint8Array();
  } catch (error) {
    if (error instanceof ErrorExtension) throw error;
    throw new ErrorExtension("el CRX está dañado");
  }
  if (crxId.length !== 16) throw new ErrorExtension("el CRX no dice de qué extensión es");
  const largoFirmado = new Uint8Array(4);
  new DataView(largoFirmado.buffer).setUint32(0, firmado.length, true);
  const mensaje = unir([PREFIJO_FIRMA, largoFirmado, firmado, archivoZip]);
  for (const prueba of pruebas) {
    const clave = prueba.get(1) ?? new Uint8Array();
    const firma = prueba.get(2) ?? new Uint8Array();
    const id = (await sha256(clave)).subarray(0, 16);
    if (hex(id) === hex(crxId) && (await firmaRsaValida(clave, firma, mensaje))) {
      return [aLetras(crxId), archivoZip];
    }
  }
  throw new ErrorExtension("la firma del CRX no es válida: fue modificado o no es de quien dice ser");
}

function unir(partes) {
  const salida = new Uint8Array(partes.reduce((total, p) => total + p.length, 0));
  let i = 0;
  for (const parte of partes) {
    salida.set(parte, i);
    i += parte.length;
  }
  return salida;
}

// ── Zip ────────────────────────────────────────────────────────────────────
async function porFlujo(datos, transformacion, maximo) {
  const flujo = new Blob([datos]).stream().pipeThrough(transformacion);
  return leerConLimite(flujo, maximo, "la extensión");
}

// Ruta normalizada como os.path.normpath (sin «/» al principio).
function normalizar(ruta) {
  const partes = [];
  for (const parte of ruta.split("/")) {
    if (!parte || parte === ".") continue;
    if (parte === ".." && partes.length && partes[partes.length - 1] !== "..") partes.pop();
    else partes.push(parte);
  }
  return partes.join("/") || ".";
}

// El nombre de un archivo del zip, o null si es peligroso: ruta absoluta,
// «..», barra invertida o caracteres de control.
function nombreSeguro(nombre) {
  // eslint-disable-next-line no-control-regex
  if (!nombre || nombre.startsWith("/") || nombre.includes("\\") || /[\x00-\x1f]/.test(nombre)) return null;
  const limpio = normalizar(nombre);
  if (limpio === "." || limpio === ".." || limpio.split("/").includes("..")) return null;
  return limpio;
}

// Map nombre → bytes, sin rutas peligrosas ni «bombas zip».
async function leerZip(datos) {
  const { MAXIMO_ARCHIVOS, MAXIMO_DESCOMPRIMIDO } = await tablas();
  const v = new DataView(datos.buffer, datos.byteOffset, datos.byteLength);
  let fin = -1;
  for (let i = datos.length - 22; i >= Math.max(0, datos.length - 22 - 65535); i--) {
    if (v.getUint32(i, true) === 0x06054b50) {
      fin = i;
      break;
    }
  }
  if (fin < 0) throw new ErrorExtension("el CRX descargado está dañado");
  const total = v.getUint16(fin + 10, true);
  const inicio = v.getUint32(fin + 16, true);
  if (total === 0xffff || inicio === 0xffffffff) throw new ErrorExtension("el CRX descargado está dañado");
  if (total > MAXIMO_ARCHIVOS) throw new ErrorExtension("la extensión tiene demasiados archivos");
  const entradas = [];
  let i = inicio;
  let suma = 0;
  for (let n = 0; n < total; n++) {
    if (i + 46 > datos.length || v.getUint32(i, true) !== 0x02014b50) throw new ErrorExtension("el CRX descargado está dañado");
    const entrada = {
      banderas: v.getUint16(i + 8, true),
      metodo: v.getUint16(i + 10, true),
      comprimido: v.getUint32(i + 20, true),
      tamano: v.getUint32(i + 24, true),
      local: v.getUint32(i + 42, true),
      nombre: decodificar(datos.subarray(i + 46, i + 46 + v.getUint16(i + 28, true))),
    };
    i += 46 + v.getUint16(i + 28, true) + v.getUint16(i + 30, true) + v.getUint16(i + 32, true);
    if (entrada.nombre.endsWith("/")) continue;
    suma += entrada.tamano;
    entradas.push(entrada);
  }
  if (suma > MAXIMO_DESCOMPRIMIDO) throw new ErrorExtension("la extensión es demasiado grande descomprimida");
  const archivos = new Map();
  for (const entrada of entradas) {
    const nombre = nombreSeguro(entrada.nombre);
    if (nombre === null) throw new ErrorExtension(`la extensión tiene un archivo con ruta peligrosa: '${entrada.nombre}'`);
    if (entrada.banderas & 1) throw new ErrorExtension("el CRX descargado está dañado (cifrado)");
    const local = entrada.local;
    if (local + 30 > datos.length || v.getUint32(local, true) !== 0x04034b50) throw new ErrorExtension("el CRX descargado está dañado");
    const desde = local + 30 + v.getUint16(local + 26, true) + v.getUint16(local + 28, true);
    const crudo = datos.subarray(desde, desde + entrada.comprimido);
    let contenido;
    if (entrada.metodo === 0) contenido = crudo.slice();
    else if (entrada.metodo === 8) contenido = await porFlujo(crudo, new DecompressionStream("deflate-raw"), entrada.tamano);
    else throw new ErrorExtension("el CRX descargado está dañado (compresión desconocida)");
    if (contenido.length !== entrada.tamano) throw new ErrorExtension("el CRX descargado está dañado");
    archivos.set(nombre, contenido);
  }
  return archivos;
}

const TABLA_CRC = (() => {
  const tabla = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    tabla[n] = c >>> 0;
  }
  return tabla;
})();
function crc32(datos) {
  let c = 0xffffffff;
  for (const b of datos) c = TABLA_CRC[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

// Zip con los archivos en el orden dado ([[nombre, bytes], …]).
async function armarZip(archivos) {
  const partes = [];
  const central = [];
  let posicion = 0;
  for (const [nombre, datos] of archivos) {
    const bytesNombre = codificar(nombre);
    let metodo = 8;
    let comprimido = await porFlujo(datos, new CompressionStream("deflate-raw"), Infinity);
    if (comprimido.length >= datos.length) {
      metodo = 0;
      comprimido = datos;
    }
    const crc = crc32(datos);
    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true);
    local.setUint16(6, 0x0800, true); // nombres en UTF-8
    local.setUint16(8, metodo, true);
    local.setUint16(10, 0, true); // 1980-01-01 00:00
    local.setUint16(12, 0x21, true);
    local.setUint32(14, crc, true);
    local.setUint32(18, comprimido.length, true);
    local.setUint32(22, datos.length, true);
    local.setUint16(26, bytesNombre.length, true);
    local.setUint16(28, 0, true);
    const cabecera = new DataView(new ArrayBuffer(46));
    cabecera.setUint32(0, 0x02014b50, true);
    cabecera.setUint16(4, 20, true);
    cabecera.setUint16(6, 20, true);
    for (let i = 6; i < 28; i += 2) cabecera.setUint16(i + 2, local.getUint16(i, true), true);
    cabecera.setUint32(42, posicion, true);
    partes.push(new Uint8Array(local.buffer), bytesNombre, comprimido);
    central.push(new Uint8Array(cabecera.buffer), bytesNombre);
    posicion += 30 + bytesNombre.length + comprimido.length;
  }
  const tamanoCentral = central.reduce((t, p) => t + p.length, 0);
  const fin = new DataView(new ArrayBuffer(22));
  fin.setUint32(0, 0x06054b50, true);
  fin.setUint16(8, archivos.length, true);
  fin.setUint16(10, archivos.length, true);
  fin.setUint32(12, tamanoCentral, true);
  fin.setUint32(16, posicion, true);
  return unir([...partes, ...central, new Uint8Array(fin.buffer)]);
}

// ── Conversión ─────────────────────────────────────────────────────────────
// JSON con comentarios y comas finales, como acepta Chrome.
function jsonTolerante(texto) {
  texto = texto.replace(/^﻿/, "");
  try {
    return JSON.parse(texto);
  } catch {}
  let salida = "";
  let enTexto = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (enTexto) {
      salida += c;
      if (c === "\\") salida += texto[++i] ?? "";
      else if (c === '"') enTexto = false;
    } else if (c === '"') {
      enTexto = true;
      salida += c;
    } else if (texto.startsWith("//", i)) {
      const fin = texto.indexOf("\n", i);
      i = (fin < 0 ? texto.length : fin) - 1;
    } else if (texto.startsWith("/*", i)) {
      const fin = texto.indexOf("*/", i + 2);
      i = (fin < 0 ? texto.length : fin + 2) - 1;
    } else {
      salida += c;
    }
  }
  try {
    return JSON.parse(salida.replace(/,(\s*[}\]])/g, "$1"));
  } catch {
    throw new ErrorExtension("el manifiesto de la extensión no es JSON válido");
  }
}

const dirname = (ruta) => (ruta.includes("/") ? ruta.slice(0, ruta.lastIndexOf("/")) : "");
function resolver(base, relativa) {
  if (relativa.startsWith("/")) return normalizar(relativa);
  return normalizar(`${dirname(base)}/${relativa}`);
}
const texto = (archivos, ruta) => decodificar(archivos.get(ruta) ?? new Uint8Array());

// Los importScripts('a.js', ...) del service worker, en orden y recursivos.
function scriptsImportados(archivos, script, vistos = new Set()) {
  let resultado = [];
  let dinamicos = false;
  for (const llamada of texto(archivos, script).matchAll(RE_IMPORT_SCRIPTS)) {
    const argumentos = llamada[1].trim();
    const textos = [...argumentos.matchAll(RE_TEXTO)].map((m) => m[2]);
    if (!textos.length && argumentos) dinamicos = true;
    for (const t of textos) {
      const ruta = resolver(script, t);
      if (archivos.has(ruta) && !vistos.has(ruta)) {
        vistos.add(ruta);
        const [internos, din] = scriptsImportados(archivos, ruta, vistos);
        resultado = [...resultado, ...internos, ruta];
        dinamicos ||= din;
      }
    }
  }
  return [resultado, dinamicos];
}

// Fragmentos («chunks») de webpack que el service worker carga con
// importScripts(ruta calculada): se cargan antes (ver la versión de la PC).
function fragmentosWebpack(archivos, sw, yaIncluidos, manifiesto) {
  const codigo = texto(archivos, sw);
  const globales = new Set(
    [...codigo.matchAll(/(?:self|globalThis|this)(?:\.|\[["'])(webpackChunk[\w$]*)/g)].map((m) => m[1]),
  );
  if (!globales.size) return [globales, []];
  const usadosEnOtroLado = new Set();
  for (const [ruta] of archivos) {
    if (/\.html?$/.test(ruta)) {
      for (const m of texto(archivos, ruta).matchAll(/<script[^>]+src=["']([^"']+)/g)) usadosEnOtroLado.add(resolver(ruta, m[1]));
    }
  }
  for (const c of manifiesto.content_scripts || []) {
    for (const js of c.js || []) usadosEnOtroLado.add(normalizar(js));
  }
  const carpeta = dirname(sw);
  const fragmentos = [];
  for (const ruta of [...archivos.keys()].sort()) {
    if (dirname(ruta) !== carpeta || ruta === sw || yaIncluidos.includes(ruta) || usadosEnOtroLado.has(ruta) || !ruta.endsWith(".js")) {
      continue;
    }
    const inicio = decodificar(archivos.get(ruta).subarray(0, 4096));
    if ([...globales].some((g) => inicio.includes(g)) && inicio.includes(".push(")) fragmentos.push(ruta);
  }
  return [globales, fragmentos];
}

// El HTML con <script src=…> al principio del <head> (o del todo).
function conScriptPrimero(html, src) {
  let t = decodificar(html);
  const etiqueta = `<script src="${src}"></script>`;
  if (t.includes(etiqueta)) return html;
  let hecho = false;
  t = t.replace(/(<head(?:\s[^>]*)?>)/i, (m) => {
    hecho = true;
    return m + etiqueta;
  });
  return codificar(hecho ? t : etiqueta + t);
}

// Copia del CSS de un script de contenido dentro de una capa (@layer), para
// que pierda ante el de la página como en Chrome (ver css_en_capa en la PC).
function cssEnCapa(archivos, ruta, capa) {
  ruta = ruta.replace(/^\/+/, "");
  const datos = archivos.get(ruta);
  if (!datos) return ruta;
  let t;
  try {
    t = new TextDecoder("utf-8", { fatal: true }).decode(datos);
  } catch {
    return ruta;
  }
  if (/@(import|namespace)\b/i.test(t)) return ruta;
  t = t.replace(/^﻿/, "").replace(/^\s*@charset\s+"[^"]*"\s*;/i, "");
  const copia = `${ruta.toLowerCase().endsWith(".css") ? ruta.slice(0, -4) : ruta}.velbrum-capa.css`;
  archivos.set(copia, codificar(`@layer ${capa} {\n${t}\n}\n`));
  return copia;
}

async function adaptarManifiesto(m, idChrome, archivos) {
  const T = await tablas();
  const avisos = [];
  const nombre = m.name ?? idChrome;

  for (const clave of T.CLAVES_DE_CHROME) {
    if (!(clave in m)) continue;
    if (clave === "sandbox") avisos.push("usa páginas «sandbox» (eval); en Gecko corren sin ese permiso");
    if (clave === "side_panel") continue;
    delete m[clave];
  }
  if ("author" in m && typeof m.author !== "string") delete m.author;

  for (const campo of ["permissions", "optional_permissions"]) {
    if (!Array.isArray(m[campo])) continue;
    const quitados = m[campo].filter(
      (p) => typeof p === "string" && (T.SIN_EQUIVALENTE.includes(p) || T.EMULADOS.includes(p) || p.startsWith("chrome://")),
    );
    m[campo] = m[campo].filter((p) => !quitados.includes(p));
    for (const permiso of quitados) {
      if (T.EMULADOS.includes(permiso)) avisos.push(`usa chrome.${permiso}: Velbrum lo emula`);
      else if (!permiso.startsWith("chrome://")) avisos.push(`pide el permiso «${permiso}», que Gecko no tiene`);
    }
  }
  const permisosAPedir = T.SOLO_OPCIONALES.filter((p) => (m.permissions || []).includes(p)).sort();
  if (permisosAPedir.length) {
    m.permissions = m.permissions.filter((p) => !permisosAPedir.includes(p));
    m.optional_permissions = [...new Set([...(m.optional_permissions || []), ...permisosAPedir])].sort();
    for (const permiso of permisosAPedir) {
      avisos.push(`necesita el permiso «${permiso}»: Velbrum te lo pide con un botón al instalarla`);
    }
  }

  // Fondo: service worker → página de fondo con la capa de compatibilidad.
  const fondo = m.background || {};
  let paginaDeFondo = null;
  const compat = ["velbrum-compat/fondo.js", "velbrum-compat/config.js"];
  const config = { fragmentos: [], permisos: permisosAPedir };
  if ("service_worker" in fondo) {
    const sw = normalizar(fondo.service_worker);
    let [importados, dinamicos] = scriptsImportados(archivos, sw);
    if (dinamicos) {
      const [globales, fragmentos] = fragmentosWebpack(archivos, sw, importados, m);
      if (fragmentos.length) {
        config.fragmentos = [...globales].sort();
        importados = [...fragmentos, ...importados];
      } else if (globales.size) {
        avisos.push("el service worker carga scripts con rutas calculadas; puede fallar");
      }
    }
    config.sw = sw;
    const nuevo = { scripts: [...compat, ...importados, sw] };
    if (fondo.type === "module") nuevo.type = "module";
    m.background = nuevo;
  } else if ("scripts" in fondo) {
    fondo.scripts = [...compat, ...fondo.scripts];
  } else if ("page" in fondo) {
    const pagina = normalizar(fondo.page);
    paginaDeFondo = pagina;
    if (archivos.has(pagina)) {
      for (const js of [...compat].reverse()) archivos.set(pagina, conScriptPrimero(archivos.get(pagina), `/${js}`));
    }
  }

  // Las demás páginas de la extensión llevan compat/pagina.js primero.
  for (const ruta of [...archivos.keys()]) {
    if (/\.html?$/i.test(ruta) && ruta !== paginaDeFondo) {
      archivos.set(ruta, conScriptPrimero(archivos.get(ruta), "/velbrum-compat/pagina.js"));
    }
  }

  // Panel lateral de Chrome → barra lateral de Gecko.
  const panel = (m.side_panel || {}).default_path;
  delete m.side_panel;
  if (panel && !("sidebar_action" in m)) {
    const accion = m.action || m.browser_action || {};
    m.sidebar_action = { default_panel: panel, default_title: accion.default_title ?? nombre };
    const icono = accion.default_icon || m.icons;
    if (icono) m.sidebar_action.default_icon = icono;
  }

  if ("options_page" in m) {
    const pagina = m.options_page;
    delete m.options_page;
    m.options_ui ??= { page: pagina, open_in_tab: true };
  }
  if (m.options_ui && typeof m.options_ui === "object") delete m.options_ui.chrome_style;

  if (m.incognito === "split") m.incognito = "spanning";

  const reemplazos = m.chrome_url_overrides || {};
  for (const pagina of Object.keys(reemplazos)) {
    if (pagina === "newtab") continue;
    delete reemplazos[pagina];
    avisos.push(`reemplaza la página chrome://${pagina}, que Gecko no permite cambiar`);
  }

  for (const c of m.content_scripts || []) {
    delete c.match_origin_as_fallback;
    if (c.js?.length && c.world !== "MAIN") {
      c.js = ["velbrum-compat/contenido.js", ...c.js.filter((j) => j !== "velbrum-compat/contenido.js")];
    }
    if (c.css?.length) c.css = c.css.filter((css) => typeof css === "string").map((css) => cssEnCapa(archivos, css, T.CAPA_CSS));
  }

  const permisos = m.permissions || [];
  if (permisos.includes("webRequestAuthProvider") && !permisos.includes("webRequestBlocking")) {
    permisos.push("webRequestBlocking");
  }

  avisos.push(...adaptarBuscador(m, archivos));

  if (m.background) {
    archivos.set("velbrum-compat/config.js", codificar(`__velbrumConfigurar(${JSON.stringify(config)});\n`));
  } else if (permisosAPedir.length) {
    m.background = { scripts: compat };
    archivos.set("velbrum-compat/config.js", codificar(`__velbrumConfigurar(${JSON.stringify(config)});\n`));
  }

  m.browser_specific_settings = {
    gecko: { id: idChrome + SUFIJO_ID, strict_min_version: "128.0", update_url: URL_SIN_ACTUALIZACIONES },
  };

  // APIs de Chrome que aparecen en el código y Gecko no tiene.
  const reApi = new RegExp(`\\bchrome\\.(${T.APIS_SIN_EQUIVALENTE.join("|")})\\.`, "g");
  const usadas = new Set();
  for (const [ruta] of archivos) {
    if (/\.m?js$/.test(ruta)) for (const u of texto(archivos, ruta).matchAll(reApi)) usadas.add(u[1]);
  }
  for (const api of [...usadas].sort()) avisos.push(`usa chrome.${api}, que Gecko no tiene: esa parte puede no funcionar`);

  return [m, [...new Set(avisos)].sort()];
}

// El buscador que agrega la extensión (chrome_settings_overrides): Gecko exige
// nombre y una URL https, y no entiende los comodines de Chrome y de Edge.
function adaptarBuscador(m, archivos) {
  const ajustes = m.chrome_settings_overrides;
  const buscador = ajustes && typeof ajustes === "object" ? ajustes.search_provider : null;
  if (!buscador || typeof buscador !== "object") return [];
  delete buscador.prepopulated_id;
  const url = traducir(m, archivos, buscador.search_url);
  if (typeof url !== "string" || !url.startsWith("https://") || RE_COMODIN_CHROME.test(url)) {
    delete ajustes.search_provider;
    if (!Object.keys(ajustes).length) delete m.chrome_settings_overrides;
    return ["cambia el buscador de una forma que Gecko no acepta: esa parte no se aplica"];
  }
  const sugerencias = traducir(m, archivos, buscador.suggest_url);
  if (
    sugerencias !== undefined &&
    sugerencias !== null &&
    (typeof sugerencias !== "string" || !sugerencias.startsWith("https://") || RE_COMODIN_CHROME.test(sugerencias))
  ) {
    delete buscador.suggest_url;
    delete buscador.suggest_url_get_params;
    delete buscador.suggest_url_post_params;
  }
  if (!buscador.name) {
    const partes = new URL(url).hostname.split(".");
    const base = partes.length > 1 ? partes[partes.length - 2] : partes[0];
    buscador.name = base ? base[0].toUpperCase() + base.slice(1).toLowerCase() : m.name ?? "";
  }
  return [];
}

function traducir(m, archivos, valor) {
  if (typeof valor !== "string" || !/^__MSG_\w+__$/.test(valor)) return valor;
  return nombreLegible({ name: valor }, archivos, [m.default_locale ?? "en", "en"]);
}

// El nombre de la extensión, resolviendo __MSG_clave__ con sus traducciones.
function nombreLegible(manifiesto, archivos, idiomas = null) {
  const nombre = manifiesto.name ?? "";
  const m = /^__MSG_(\w+)__$/.exec(nombre);
  if (!m) return nombre;
  for (const idioma of idiomas ?? ["es", "es_419", manifiesto.default_locale ?? "en", "en"]) {
    const datos = archivos.get(`_locales/${idioma}/messages.json`);
    if (!datos) continue;
    let mensajes;
    try {
      mensajes = Object.fromEntries(Object.entries(jsonTolerante(decodificar(datos))).map(([k, v]) => [k.toLowerCase(), v]));
    } catch {
      continue;
    }
    const mensaje = mensajes[m[1].toLowerCase()]?.message;
    if (mensaje) return mensaje;
  }
  return nombre;
}

function reemplazarBytes(datos, de, a) {
  const buscado = codificar(de);
  const nuevo = codificar(a);
  const partes = [];
  let desde = 0;
  for (let i = 0; i <= datos.length - buscado.length; i++) {
    let igual = true;
    for (let j = 0; j < buscado.length; j++) {
      if (datos[i + j] !== buscado[j]) {
        igual = false;
        break;
      }
    }
    if (igual) {
      partes.push(datos.subarray(desde, i), nuevo);
      i += buscado.length - 1;
      desde = i + 1;
    }
  }
  if (!partes.length) return datos;
  partes.push(datos.subarray(desde));
  return unir(partes);
}

// CRX de la tienda → [XPI, manifiesto, avisos, nombre].
async function convertir(datosCrx, idChrome, tienda = "chrome") {
  const T = await tablas();
  const [idFirmado, archivoZip] = await verificarCrx(datosCrx);
  if (idFirmado !== idChrome) throw new ErrorExtension(`el CRX es de otra extensión (${idFirmado}), no de ${idChrome}`);
  const archivos = await leerZip(archivoZip);
  if (!archivos.has("manifest.json")) throw new ErrorExtension("la extensión no tiene manifest.json");
  if ([...archivos.keys()].some((n) => n.startsWith("velbrum-compat/"))) {
    throw new ErrorExtension("la extensión ya tiene una carpeta velbrum-compat");
  }
  let manifiesto = jsonTolerante(decodificar(archivos.get("manifest.json")));
  archivos.delete("manifest.json");
  if (![2, 3].includes(manifiesto.manifest_version)) throw new ErrorExtension("la extensión usa una versión de manifiesto desconocida");
  if (manifiesto.app) throw new ErrorExtension("es una «app» de Chrome, no una extensión");
  const nombre = nombreLegible(manifiesto, archivos);
  let avisos;
  [manifiesto, avisos] = await adaptarManifiesto(manifiesto, idChrome, archivos);

  // «chrome-extension:» casi siempre se refiere a sus propias páginas; en
  // Gecko el esquema es «moz-extension:».
  for (const [ruta, contenido] of archivos) {
    if (/\.(m?js|html?|css|json)$/.test(ruta)) archivos.set(ruta, reemplazarBytes(contenido, "chrome-extension:", "moz-extension:"));
  }
  for (const archivo of T.ARCHIVOS_COMPAT) {
    const r = await fetch(recurso(`compat/${archivo}`));
    archivos.set(`velbrum-compat/${archivo}`, new Uint8Array(await r.arrayBuffer()));
  }
  const ahora = new Date();
  const dos = (n) => String(n).padStart(2, "0");
  archivos.set(
    "velbrum-compat/origen.json",
    codificar(
      JSON.stringify(
        {
          id_chrome: idChrome,
          tienda,
          nombre,
          version: manifiesto.version,
          convertida: `${ahora.getFullYear()}-${dos(ahora.getMonth() + 1)}-${dos(ahora.getDate())} ${dos(ahora.getHours())}:${dos(ahora.getMinutes())}`,
          compat: T.VERSION_COMPAT,
          avisos,
        },
        null,
        1,
      ),
    ),
  );
  const entradas = [["manifest.json", codificar(JSON.stringify(manifiesto, null, 1))]];
  for (const ruta of [...archivos.keys()].sort()) entradas.push([ruta, archivos.get(ruta)]);
  return [await armarZip(entradas), manifiesto, avisos, nombre];
}

// Baja la extensión de la tienda (`tienda`: «chrome» o «edge») y la convierte.
async function preparar(idChrome, tienda) {
  const ultima = await consultar(idChrome, "0.0.0.0", tienda);
  if (!ultima) throw new ErrorExtension(`${NOMBRES_TIENDAS[tienda]} no tiene la extensión ${idChrome} (o no es pública)`);
  const [version, url, suma] = ultima;
  const datos = await descargar(url, suma, tienda);
  const [xpi, manifiesto, avisos, nombre] = await convertir(datos, idChrome, tienda);
  return {
    xpi: xpi.buffer,
    archivo: `${idChrome}${SUFIJO_ID}.xpi`,
    info: { id_chrome: idChrome, tienda, nombre, version: manifiesto.version ?? version, avisos },
  };
}
