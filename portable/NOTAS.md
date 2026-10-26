## Descargas / Downloads

| Sistema | Instalador | Portable |
|---|---|---|
| **Windows** 10/11 (64 bits) | `velbrum-…-windows-x86_64-instalador.exe` | `velbrum-…-windows-x86_64-portable.zip` |
| **macOS** Apple Silicon (M1…) | `velbrum-…-macos-arm64.dmg` | `velbrum-…-macos-arm64-portable.zip` |
| **macOS** Intel | `velbrum-…-macos-x86_64.dmg` | `velbrum-…-macos-x86_64-portable.zip` |
| **Linux** Debian, Ubuntu, Mint… | `velbrum-…-linux-x86_64.deb` | `velbrum-…-linux-x86_64.AppImage` |
| **Linux** Fedora, openSUSE… | `velbrum-…-linux-x86_64.rpm` | `velbrum-…-linux-x86_64-portable.tar.gz` |
| **Linux** Arch, Manjaro… | `velbrum-…-linux-x86_64.pkg.tar.zst` | |
| **Android** 8 o posterior | `velbrum-…-android-arm64-v8a.apk` (teléfonos de 64 bits; `armeabi-v7a` para los de 32 bits, `x86_64` para emuladores y Chromebooks) | |
| **NixOS** | ver el README (módulo de NixOS, con actualizaciones firmadas) | |

- **Portable**: el perfil queda en la carpeta `datos`, al lado del programa (se puede llevar en un pendrive).
- **Windows** puede mostrar «Windows protegió su PC»: Velbrum no tiene una firma de código paga. «Más información» → «Ejecutar de todas formas».
- **macOS**: la primera vez, clic derecho en Velbrum.app → Abrir. Si dice que «está dañado»: `xattr -dr com.apple.quarantine /Applications/Velbrum.app`.
- **Linux**: necesita glibc 2.35 o más nueva (Ubuntu 22.04, Debian 12, Fedora 36 o posteriores).
- **Android**: la versión oficial de IronFox (firma del APK verificada contra su certificado) con los ajustes, la marca y la extensión de las tiendas de Velbrum, firmada con la clave de Velbrum; sumas en `SHA256SUMS-android`. La primera vez, Android pide permiso para instalar aplicaciones desde el navegador o el gestor de archivos.

Cada paquete es la versión oficial de LibreWolf para ese sistema (firma GPG de LibreWolf verificada al compilar) con los ajustes, la marca, la extensión de las tiendas y Tor (Tor Expert Bundle, firma de Tor Project verificada) de Velbrum. `SHA256SUMS` tiene las sumas de todos los archivos; el código está en la etiqueta firmada de esta versión.

*Each package is the official LibreWolf build for that system (LibreWolf's GPG signature checked at build time) plus Velbrum's settings, branding, store extension and Tor (Tor Expert Bundle, Tor Project signature checked). Windows may show a SmartScreen warning and macOS needs right-click → Open the first time: Velbrum has no paid code-signing certificate.*
