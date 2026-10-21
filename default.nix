# Paquete del navegador Bruma (ver README.md): LibreWolf de nixpkgs con los
# ajustes de privacidad de Mullvad Browser, que además instala extensiones de
# Chrome (de la Chrome Web Store o de archivos .crx) adaptándolas a Gecko.
# No compila nada: usa el LibreWolf del caché de NixOS y se actualiza con
# nixpkgs (nix flake update).
{
  pkgs ? import <nixpkgs> { },
  # Paquetes de idioma de Mozilla, en orden de preferencia (por ejemplo
  # [ "es-MX" "es" "es-ES" ]); los arma modulo.nix con el idioma del sistema.
  idiomas ? [ ],
  # Donde los deja el servicio bruma-idioma (solo root puede escribir ahí).
  carpetaIdioma ? "/var/lib/bruma/idioma",
  # true: Bruma instala extensiones de Chrome adaptadas, que no pueden llevar
  # la firma de Mozilla (se aceptan extensiones sin firma, con el cartel de
  # confirmación). false: solo extensiones firmadas por Mozilla, sin la parte
  # de Chrome. Lo elige modulo.nix (opción bruma.extensionesDeChrome).
  extensionesDeChrome ? true,
  # Dominios que no van por el DNS cifrado sino por el del sistema (redes
  # locales y VPN con nombres propios); lo elige modulo.nix (opción
  # bruma.dominiosLocales).
  dominiosLocales ? [ "lan" "home" "home.arpa" "internal" "localdomain" ],
}:
let
  inherit (pkgs) lib;

  # ── Ícono ───────────────────────────────────────────────────────────────
  # De 16 a 32 px se usa una versión simplificada (iconos/bruma-chico.svg),
  # que se lee mejor en pestañas y en la barra de tareas.
  iconos = pkgs.runCommand "bruma-iconos" { nativeBuildInputs = [ pkgs.librsvg ]; } ''
    install -Dm644 ${./iconos/bruma.svg} $out/share/icons/hicolor/scalable/apps/bruma.svg
    for t in 16 24 32 48 64 96 128 256; do
      svg=${./iconos/bruma.svg}
      [ $t -le 32 ] && svg=${./iconos/bruma-chico.svg}
      mkdir -p $out/share/icons/hicolor/''${t}x''${t}/apps
      rsvg-convert -w $t -h $t $svg -o $out/share/icons/hicolor/''${t}x''${t}/apps/bruma.png
    done
  '';

  # ── Extensión propia: instala las extensiones de Chrome ─────────────────
  # Va en la carpeta de la aplicación (browser/extensions): se activa sola.
  xpiBruma = pkgs.runCommand "bruma-extension-xpi" { nativeBuildInputs = [ pkgs.zip ]; } ''
    mkdir -p fuente/iconos $out
    cp ${./extension/manifest.json} fuente/manifest.json
    cp ${./extension/background.js} fuente/background.js
    cp ${./extension/tienda.js} fuente/tienda.js
    cp ${./extension/edge.js} fuente/edge.js
    cp ${./extension/aviso.js} fuente/aviso.js
    for t in 48 96; do
      cp ${iconos}/share/icons/hicolor/''${t}x''${t}/apps/bruma.png fuente/iconos/bruma-$t.png
    done
    cd fuente
    zip -X -r -q $out/chrome@bruma.xpi .
    ${pkgs.unzip}/bin/unzip -l $out/chrome@bruma.xpi | grep -q " background.js$"
  '';

  # ── Fuentes de Mullvad Browser ──────────────────────────────────────────
  # Las páginas solo ven estas fuentes (las mismas que cualquier usuario de
  # Mullvad Browser), no las de la PC: así las fuentes no te distinguen. Se
  # copian para no depender del paquete entero de Mullvad Browser.
  fuentes = pkgs.runCommand "bruma-fuentes" { } ''
    origen=${pkgs.mullvad-browser}/share/mullvad-browser/fonts
    destino=$out/share/bruma/fuentes
    mkdir -p $destino
    cp $origen/*.ttf $origen/*.otf $origen/000_README.txt $destino/
    sed "s|<dir>$origen</dir>|<dir>$destino</dir>|" $origen/fonts.conf > $destino/fonts.conf
    grep -q "<dir>$destino</dir>" $destino/fonts.conf
    ! grep -q "$origen" $destino/fonts.conf
  '';

  # Qué fuente usa cada idioma (serif, sans-serif, monospace) y la lista de
  # fuentes permitidas, tal cual Mullvad Browser: sacado de sus preferencias
  # al compilar, para que siga igual cuando Mullvad se actualice.
  fuentesMullvadCfg = pkgs.runCommand "bruma-fuentes-mullvad.cfg" { nativeBuildInputs = [ pkgs.unzip ]; } ''
    unzip -p ${pkgs.mullvad-browser}/share/mullvad-browser/browser/omni.ja defaults/preferences/001-base-profile.js \
      | grep '^pref("font\.' | sed 's/^pref(/defaultPref(/' > lineas
    test "$(wc -l < lineas)" -gt 50
    grep -q '"font.system.whitelist"' lineas
    { echo; echo "/** [SECTION] FUENTES DE MULLVAD BROWSER (por idioma) */"; cat lineas; } > $out
  '';

  # ── LibreWolf + ajustes de Mullvad ──────────────────────────────────────
  librewolf = pkgs.librewolf-unwrapped;
  versionFirefox = builtins.head (lib.splitString "-" librewolf.version);
  # Versión de Chrome que Bruma dice ser al pedir extensiones a la tienda.
  versionChrome = pkgs.ungoogled-chromium.version;

  politicas = {
    # LibreWolf no deja instalar paquetes de idioma; Bruma sí, para tener la
    # interfaz en tu idioma. El paquete (con la marca de Bruma) lo prepara el
    # servicio bruma-idioma en una carpeta de root y lo instala esta política:
    # así no hace falta que Gecko cargue nada suelto del perfil.
    ExtensionSettings = {
      "*".allowed_types = [ "dictionary" "extension" "locale" "sitepermission" "theme" ];
    } // lib.optionalAttrs extensionesDeChrome {
      # La extensión de las tiendas también anda con «Siempre privado».
      "chrome@bruma".private_browsing = true;
    } // lib.listToAttrs (map (idioma: {
      name = "langpack-${idioma}@firefox.mozilla.org";
      value = {
        installation_mode = "force_installed";
        install_url = "file://${carpetaIdioma}/${idioma}.xpi";
      };
    }) idiomas);
  };

  # ── Marca: Bruma en lugar de LibreWolf ──────────────────────────────────
  # Se descomprimen los dos omni.ja de LibreWolf (el del navegador y el
  # general), se cambian logos, íconos y textos (marca/textos.py) y algunas
  # líneas de código (marca/codigo.py: «Acerca de», borrado de paquetes de
  # idioma…), y se vuelven a comprimir. Los íconos de las ventanas están fuera.
  marca = pkgs.runCommand "bruma-marca-${librewolf.version}"
    { nativeBuildInputs = [ pkgs.librsvg pkgs.imagemagick pkgs.unzip pkgs.zip pkgs.python3 ]; }
    ''
      # omni.ja es un zip «optimizado»: unzip avisa (código 1 o 2) pero lo
      # extrae bien; se comprueba que estén todos los archivos.
      desempacar() {
        unzip -q "$1" -d "$2" 2>/dev/null || [ $? -le 2 ]
        esperados=$(unzip -Z1 "$1" 2>/dev/null | grep -vc '/$' || true)
        extraidos=$(find "$2" -type f | wc -l)
        echo "$2: $extraidos de $esperados archivos"
        [ "$extraidos" -eq "$esperados" ]
        chmod -R u+w "$2"
      }
      desempacar ${librewolf}/lib/librewolf/browser/omni.ja omni
      desempacar ${librewolf}/lib/librewolf/omni.ja toolkit

      b=omni/chrome/browser/content/branding
      logo=${./iconos/bruma.svg}
      chico=${./iconos/bruma-chico.svg}
      test -f $b/icon32.png
      for t in 16 32 48 64 128; do
        if [ $t -le 32 ]; then svg=$chico; else svg=$logo; fi
        rsvg-convert -w $t -h $t $svg -o $b/icon$t.png
      done
      for nombre in about-logo about-logo-private; do
        rsvg-convert -w 192 -h 192 $logo -o $b/$nombre.png
        rsvg-convert -w 384 -h 384 $logo -o $b/$nombre@2x.png
      done
      cp $logo $b/about-logo.svg
      rsvg-convert -w 200 -h 200 $logo -o logo200.png
      magick -size 300x236 xc:none logo200.png -gravity center -composite $b/about.png
      cp ${./marca/nombre.svg} $b/firefox-wordmark.svg
      cp ${./marca/nombre.svg} $b/about-wordmark.svg
      # Los otros lobos: la sección de Ajustes que agrega LibreWolf, «Acerca
      # de» en Ajustes y la barra lateral, y about:debugging.
      cp ${./marca/simbolo.svg} omni/chrome/browser/skin/classic/browser/preferences/category-librewolf.svg
      cp $chico omni/chrome/browser/skin/classic/browser/sidebar/firefox.svg
      cp $logo omni/chrome/devtools/skin/images/aboutdebugging-firefox-librewolf.svg

      python3 -I ${./marca/textos.py} ${./marca} omni toolkit
      cp ${./marca/ajustes-bruma.sys.mjs} omni/chrome/browser/content/browser/ajustes-bruma.sys.mjs
      python3 -I ${./marca/codigo.py} omni toolkit

      mkdir -p $out/iconos
      (cd omni && zip -q -X -r $out/omni.ja .)
      (cd toolkit && zip -q -X -r $out/omni-general.ja .)
      for t in 16 32 48 64 128; do
        if [ $t -le 32 ]; then svg=$chico; else svg=$logo; fi
        rsvg-convert -w $t -h $t $svg -o $out/iconos/default$t.png
      done
    '';

  gecko =
    (pkgs.wrapFirefox librewolf {
      pname = "bruma-gecko";
      libName = "librewolf";
      wmClass = "bruma";
      # Como texto "${...}" para que se copie al store: con la ruta sola, el
      # wrapper la leería desde /etc/nixos y no se recompilaría al cambiarla.
      extraPrefsFiles = librewolf.extraPrefsFiles ++ [ "${./gecko/ajustes.cfg}" fuentesMullvadCfg ];
      extraPoliciesFiles = librewolf.extraPoliciesFiles;
      extraPolicies = politicas;
      # Dominios locales fuera del DNS cifrado (gecko/ajustes.cfg) y, sin
      # extensiones de Chrome, firma de Mozilla obligatoria, sin excepción.
      extraPrefs = ''
        defaultPref("network.trr.excluded-domains", ${builtins.toJSON (lib.concatStringsSep "," dominiosLocales)});
      '' + lib.optionalString (!extensionesDeChrome) ''
        lockPref("xpinstall.signatures.required", true);
      '';
    }).overrideAttrs
      (viejo: {
        buildCommand = viejo.buildCommand + lib.optionalString extensionesDeChrome ''
          mkdir -p "$out/lib/librewolf/browser/extensions"
          cp ${xpiBruma}/chrome@bruma.xpi "$out/lib/librewolf/browser/extensions/chrome@bruma.xpi"
        '' + ''

          # Marca de Bruma (ver «marca» arriba).
          rm "$out/lib/librewolf/browser/omni.ja" "$out/lib/librewolf/omni.ja"
          cp ${marca}/omni.ja "$out/lib/librewolf/browser/omni.ja"
          cp ${marca}/omni-general.ja "$out/lib/librewolf/omni.ja"
          # Sin «LibreWolf for NixOS» en «Acerca de», sin el acceso de LibreWolf
          # en el menú Ayuda y sin su nombre en el aviso de complementos.
          rm -f "$out/lib/librewolf/distribution/distribution.ini"
          politicas="$out/lib/librewolf/distribution/policies.json"
          jq 'del(.policies.SupportMenu)
              | .policies.ExtensionSettings["*"].blocked_install_message = "Bruma no permite instalar este complemento."' \
            "$politicas" > politicas.json
          mv politicas.json "$politicas"
          ! grep -qi librewolf "$politicas"
          for t in 16 32 48 64 128; do
            rm -f "$out/lib/librewolf/browser/chrome/icons/default/default$t.png"
            cp ${marca}/iconos/default$t.png "$out/lib/librewolf/browser/chrome/icons/default/"
          done
        '';
      });

  # ── Host de mensajería nativa ───────────────────────────────────────────
  manifiestoHost = pkgs.writeText "bruma.extensiones.json" (builtins.toJSON {
    name = "bruma.extensiones";
    description = "Bruma: instalar extensiones de Chrome";
    path = "@out@/libexec/bruma/host-extensiones";
    type = "stdio";
    allowed_extensions = [ "chrome@bruma" ];
  });

  menu = pkgs.makeDesktopItem {
    name = "bruma";
    desktopName = "Bruma";
    genericName = "Navegador web privado";
    comment = "Navegador privado con la protección de Mullvad Browser que también usa extensiones de Chrome";
    exec = "bruma %U";
    icon = "bruma";
    startupWMClass = "bruma";
    startupNotify = true;
    categories = [ "Network" "WebBrowser" ];
    keywords = [ "navegador" "internet" "web" "privado" "mullvad" "firefox" "chrome" "extensiones" ];
    mimeTypes = [
      "text/html"
      "application/xhtml+xml"
      "x-scheme-handler/http"
      "x-scheme-handler/https"
      "application/x-chrome-extension"
    ];
    actions = {
      nueva-ventana = { name = "Nueva ventana"; exec = "bruma --nueva-ventana"; };
      ventana-privada = { name = "Nueva ventana privada"; exec = "bruma --privada"; };
      ventana-tor = { name = "Nueva ventana privada con Tor"; exec = "bruma --tor"; };
      # Los interruptores de bordes y firmas están adentro del navegador
      # (botón «Bruma», marca/ajustes-bruma.sys.mjs) y en la terminal.
    };
  };

  # Las ventanas con Tor son otra instancia (clase bruma-tor): esta entrada
  # oculta hace que GNOME les ponga el ícono de Bruma y el nombre correcto.
  menuTor = pkgs.makeDesktopItem {
    name = "bruma-tor";
    desktopName = "Bruma con Tor";
    comment = "Ventana privada de Bruma que sale por Tor";
    exec = "bruma --tor %U";
    icon = "bruma";
    startupWMClass = "bruma-tor";
    noDisplay = true;
    categories = [ "Network" "WebBrowser" ];
  };
in
pkgs.runCommand "bruma-${versionFirefox}"
  {
    passthru = { inherit gecko xpiBruma; };
    meta = {
      description = "Navegador privado: LibreWolf con la privacidad de Mullvad y extensiones de Chrome";
      mainProgram = "bruma";
      platforms = [ "x86_64-linux" ];
    };
  }
  ''
    mkdir -p $out/bin $out/libexec/bruma $out/share/applications $out/share/bruma
    ln -s ${iconos}/share/icons $out/share/icons
    cp ${menu}/share/applications/*.desktop ${menuTor}/share/applications/*.desktop $out/share/applications/

    substitute ${./host/host-extensiones.py} $out/libexec/bruma/host-extensiones \
      --replace-fail @python@ ${pkgs.python3}/bin/python3 \
      --replace-fail @bruma@ $out/bin/bruma \
      --replace-fail @libexec@ $out/libexec/bruma
    chmod 555 $out/libexec/bruma/host-extensiones
    substitute ${manifiestoHost} $out/share/bruma/bruma.extensiones.json --replace-fail @out@ $out

    cp -r ${./host/compat} $out/libexec/bruma/compat
    substitute ${./host/extensiones_chrome.py} $out/libexec/bruma/extensiones_chrome.py \
      --replace-fail @versionChromium@ ${versionChrome} \
      --replace-fail @compat@ $out/libexec/bruma/compat
    # Cambio de país de la ventana con Tor (bruma --tor-pais).
    cp ${./host/tor-pais.py} $out/libexec/bruma/tor-pais.py
    ${pkgs.python3}/bin/python3 -I -m py_compile $out/libexec/bruma/extensiones_chrome.py $out/libexec/bruma/host-extensiones $out/libexec/bruma/tor-pais.py
    rm -rf $out/libexec/bruma/__pycache__

    # Paquete de idioma con la marca de Bruma (lo arma el lanzador).
    mkdir -p $out/libexec/bruma/marca
    cp ${./marca/idioma.py} $out/libexec/bruma/marca/idioma.py
    cp ${./marca/brand.ftl} $out/libexec/bruma/marca/brand.ftl
    cp ${./marca/brand.properties} $out/libexec/bruma/marca/brand.properties
    # Lo que corre el servicio de sistema bruma-idioma (modulo.nix).
    cat > $out/libexec/bruma/bruma-idioma <<EOF
    #!${pkgs.bash}/bin/bash
    exec ${pkgs.python3}/bin/python3 -I $out/libexec/bruma/marca/idioma.py ${carpetaIdioma} ${versionFirefox} $out/libexec/bruma/marca ${lib.escapeShellArgs idiomas}
    EOF
    chmod 555 $out/libexec/bruma/bruma-idioma

    substitute ${./lanzador.sh} $out/bin/bruma \
      --replace-fail @bash@ ${pkgs.bash}/bin/bash \
      --replace-fail @python@ ${pkgs.python3}/bin/python3 \
      --replace-fail @libexec@ $out/libexec/bruma \
      --replace-fail @gecko@ ${gecko}/bin/librewolf \
      --replace-fail @fuentes@ ${fuentes}/share/bruma/fuentes/fonts.conf \
      --replace-fail @manifiestoHost@ $out/share/bruma/bruma.extensiones.json \
      --replace-fail @extensionesDeChrome@ ${if extensionesDeChrome then "1" else "0"} \
      --replace-fail @notifySend@ ${pkgs.libnotify}/bin/notify-send \
      --replace-fail @tor@ ${pkgs.tor}/bin/tor \
      --replace-fail @torGeoip@ ${pkgs.tor.geoip} \
      --replace-fail @lanzador@ $out/bin/bruma
    chmod 555 $out/bin/bruma
    ${pkgs.bash}/bin/bash -n $out/bin/bruma
  ''
