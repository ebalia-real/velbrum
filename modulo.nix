# Módulo NixOS del navegador Velbrum (ver README.md): instala el comando velbrum,
# su entrada en el menú, el paquete de idioma con la marca de Velbrum (servicio
# velbrum-idioma) y la actualización diaria de las extensiones de Chrome que
# Velbrum adaptó a Gecko.
#
# Para usarlo en cualquier PC con NixOS: copiar esta carpeta junto a
# configuration.nix y agregar   imports = [ ./velbrum/modulo.nix ];
{ config, lib, pkgs, ... }:
let
  # Idioma de la interfaz: el del sistema (i18n.defaultLocale), en el nombre
  # que usa Mozilla, con alternativas. «es_MX.UTF-8» → es-MX, es, es-ES.
  porDefecto = { es = "es-ES"; pt = "pt-PT"; zh = "zh-CN"; };
  local = builtins.head (lib.splitString "." config.i18n.defaultLocale);
  partes = lib.splitString "_" local;
  lengua = builtins.head partes;
  region = if builtins.length partes > 1 then builtins.elemAt partes 1 else null;
  idiomas =
    if lengua == "en" || lengua == "C" then [ ]
    else lib.unique (lib.optional (region != null) "${lengua}-${region}" ++ [ lengua ] ++ lib.optional (porDefecto ? ${lengua}) porDefecto.${lengua});

  cfg = config.velbrum;
  velbrum = import ./. {
    inherit pkgs idiomas;
    inherit (cfg) extensionesDeChrome dominiosLocales;
    repoActualizaciones = lib.optionalString cfg.actualizador.buscar cfg.actualizador.repositorio;
    carpetaVelbrum = cfg.actualizador.carpeta;
    comandoActualizar = cfg.actualizador.comando;
  };
in
{
  options.velbrum.actualizador = {
    buscar = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Que Velbrum busque una vez por día si hay una versión nueva (firmada) en
        GitHub y ofrezca instalarla (pide la contraseña de administrador) y
        reiniciar. Con false no se conecta a GitHub; igual ofrece reiniciar
        cuando un rebuild instala una versión nueva.
      '';
    };
    repositorio = lib.mkOption {
      type = lib.types.str;
      default = "ebalia-real/velbrum";
      description = "Repositorio de GitHub (dueño/nombre) del que salen las versiones de Velbrum.";
    };
    carpeta = lib.mkOption {
      type = lib.types.str;
      default = "/etc/nixos/velbrum";
      description = "La carpeta de Velbrum (un clon de git) que el actualizador lleva a la versión nueva.";
    };
    comando = lib.mkOption {
      type = lib.types.str;
      default = "/run/current-system/sw/bin/nixos-rebuild switch";
      example = "/run/current-system/sw/bin/nixos-rebuild switch --flake /etc/nixos#mi-pc";
      description = "Comando (como root) que aplica la versión nueva después de actualizar la carpeta.";
    };
  };

  options.velbrum.dominiosLocales = lib.mkOption {
    type = lib.types.listOf lib.types.str;
    default = [ "lan" "home" "home.arpa" "internal" "localdomain" ];
    example = [ "lan" "home" "home.arpa" "internal" "localdomain" "mi-vpn.example" ];
    description = ''
      Dominios que Velbrum resuelve con el DNS del sistema en lugar del DNS
      cifrado (Quad9), porque solo existen en tu red: los de la red local y,
      si usás una VPN con nombres propios, los de esa VPN.
    '';
  };

  options.velbrum.extensionesDeChrome = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = ''
      Instalar extensiones de Chrome (de la Chrome Web Store, de la tienda de
      Edge o de archivos .crx) adaptadas a Gecko. Como no pueden llevar la
      firma de Mozilla, Velbrum acepta extensiones sin firma (siempre con el
      cartel de confirmación), y cada usuario puede igual exigir firmas
      cuando quiera con «velbrum --exigir-firmas» (y volver con «velbrum
      --permitir-sin-firma»). Con false, Velbrum solo acepta extensiones
      firmadas por Mozilla (como Firefox), fijo para todos, y no ofrece la
      parte de Chrome.
    '';
  };

  config = {
    environment.systemPackages = [ velbrum ];

    # Después de un rebuild, GNOME Shell no ve los cambios del menú (acciones,
    # textos de Velbrum): vigila la carpeta vieja del store. Sí relee todo cuando
    # cambia algo en ~/.local/share/applications, así que en cada rebuild se
    # crea y se borra ahí un archivo vacío (oculto) y no hace falta cerrar
    # sesión. Corre con tu usuario (servicio nixos-activation).
    system.userActivationScripts.velbrum-menu = {
      text = ''
        carpeta="$HOME/.local/share/applications"
        mkdir -p "$carpeta"
        printf '[Desktop Entry]\nType=Application\nName=Velbrum\nExec=true\nNoDisplay=true\n' > "$carpeta/velbrum-refrescar-menu.desktop"
        sleep 1
        rm -f "$carpeta/velbrum-refrescar-menu.desktop"
        # Velbrum antes se llamaba Bruma: si estaba anclado en la barra de
        # GNOME con el nombre viejo, queda anclado con el nuevo.
        if command -v gsettings > /dev/null; then
          favoritos=$(gsettings get org.gnome.shell favorite-apps 2> /dev/null || true)
          case "$favoritos" in
            *"'bruma.desktop'"*)
              gsettings set org.gnome.shell favorite-apps "$(printf '%s' "$favoritos" | sed "s/'bruma.desktop'/'velbrum.desktop'/")" || true ;;
          esac
        fi
      '';
      deps = [ ];
    };

    # Prepara en /var/lib/velbrum/idioma el paquete de idioma de Mozilla con la
    # marca «Velbrum», que después instala una política del navegador. Corre al
    # arrancar la PC y en cada rebuild que cambie Velbrum (nueva versión de
    # LibreWolf); sin internet, se reintenta cada 10 minutos.
    # Velbrum antes se llamaba Bruma: la carpeta vieja del paquete de idioma
    # ya no se usa.
    systemd.tmpfiles.rules = [ "R /var/lib/bruma - - - - -" ];

    systemd.services.velbrum-idioma = lib.mkIf (idiomas != [ ]) {
      description = "Velbrum: paquete de idioma con la marca Velbrum";
      wantedBy = [ "multi-user.target" ];
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];
      restartTriggers = [ velbrum ];
      startLimitIntervalSec = 0;
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${velbrum}/libexec/velbrum/velbrum-idioma";
        Restart = "on-failure";
        RestartSec = "10min";
        StateDirectory = "velbrum/idioma";
        StateDirectoryMode = "0755";
        UMask = "0022";
        # Solo baja un archivo y escribe en /var/lib/velbrum.
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        NoNewPrivileges = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = [ "AF_INET" "AF_INET6" "AF_UNIX" ];
        RestrictNamespaces = true;
        LockPersonality = true;
        SystemCallArchitectures = "native";
        CapabilityBoundingSet = "";
      };
    };

    # Las extensiones de Chrome convertidas no se actualizan solas desde la
    # tienda de Chrome: esto busca versiones nuevas una vez por día y las deja
    # listas para la próxima vez que se abra Velbrum.
    systemd.user.services.velbrum-actualizar-extensiones = lib.mkIf cfg.extensionesDeChrome {
      description = "Velbrum: actualizar las extensiones de Chrome";
      unitConfig.ConditionPathExists = "%h/.local/share/velbrum/gecko/extensions";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${velbrum}/bin/velbrum --actualizar-extensiones";
        Nice = 15;
        IOSchedulingClass = "idle";
      };
    };
    systemd.user.timers.velbrum-actualizar-extensiones = lib.mkIf cfg.extensionesDeChrome {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
        RandomizedDelaySec = "1h";
      };
    };
  };
}
