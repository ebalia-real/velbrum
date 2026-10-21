# Módulo NixOS del navegador Bruma (ver README.md): instala el comando bruma,
# su entrada en el menú, el paquete de idioma con la marca de Bruma (servicio
# bruma-idioma) y la actualización diaria de las extensiones de Chrome que
# Bruma adaptó a Gecko.
#
# Para usarlo en cualquier PC con NixOS: copiar esta carpeta junto a
# configuration.nix y agregar   imports = [ ./bruma/modulo.nix ];
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

  cfg = config.bruma;
  bruma = import ./. {
    inherit pkgs idiomas;
    inherit (cfg) extensionesDeChrome dominiosLocales;
  };
in
{
  options.bruma.dominiosLocales = lib.mkOption {
    type = lib.types.listOf lib.types.str;
    default = [ "lan" "home" "home.arpa" "internal" "localdomain" ];
    example = [ "lan" "home" "home.arpa" "internal" "localdomain" "mi-vpn.example" ];
    description = ''
      Dominios que Bruma resuelve con el DNS del sistema en lugar del DNS
      cifrado (Quad9), porque solo existen en tu red: los de la red local y,
      si usás una VPN con nombres propios, los de esa VPN.
    '';
  };

  options.bruma.extensionesDeChrome = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = ''
      Instalar extensiones de Chrome (de la Chrome Web Store, de la tienda de
      Edge o de archivos .crx) adaptadas a Gecko. Como no pueden llevar la
      firma de Mozilla, Bruma acepta extensiones sin firma (siempre con el
      cartel de confirmación), y cada usuario puede igual exigir firmas
      cuando quiera con «bruma --exigir-firmas» (y volver con «bruma
      --permitir-sin-firma»). Con false, Bruma solo acepta extensiones
      firmadas por Mozilla (como Firefox), fijo para todos, y no ofrece la
      parte de Chrome.
    '';
  };

  config = {
    environment.systemPackages = [ bruma ];

    # Después de un rebuild, GNOME Shell no ve los cambios del menú (acciones,
    # textos de Bruma): vigila la carpeta vieja del store. Sí relee todo cuando
    # cambia algo en ~/.local/share/applications, así que en cada rebuild se
    # crea y se borra ahí un archivo vacío (oculto) y no hace falta cerrar
    # sesión. Corre con tu usuario (servicio nixos-activation).
    system.userActivationScripts.bruma-menu = {
      text = ''
        carpeta="$HOME/.local/share/applications"
        mkdir -p "$carpeta"
        printf '[Desktop Entry]\nType=Application\nName=Bruma\nExec=true\nNoDisplay=true\n' > "$carpeta/bruma-refrescar-menu.desktop"
        sleep 1
        rm -f "$carpeta/bruma-refrescar-menu.desktop"
      '';
      deps = [ ];
    };

    # Prepara en /var/lib/bruma/idioma el paquete de idioma de Mozilla con la
    # marca «Bruma», que después instala una política del navegador. Corre al
    # arrancar la PC y en cada rebuild que cambie Bruma (nueva versión de
    # LibreWolf); sin internet, se reintenta cada 10 minutos.
    systemd.services.bruma-idioma = lib.mkIf (idiomas != [ ]) {
      description = "Bruma: paquete de idioma con la marca Bruma";
      wantedBy = [ "multi-user.target" ];
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];
      restartTriggers = [ bruma ];
      startLimitIntervalSec = 0;
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${bruma}/libexec/bruma/bruma-idioma";
        Restart = "on-failure";
        RestartSec = "10min";
        StateDirectory = "bruma/idioma";
        StateDirectoryMode = "0755";
        UMask = "0022";
        # Solo baja un archivo y escribe en /var/lib/bruma.
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
    # listas para la próxima vez que se abra Bruma.
    systemd.user.services.bruma-actualizar-extensiones = lib.mkIf cfg.extensionesDeChrome {
      description = "Bruma: actualizar las extensiones de Chrome";
      unitConfig.ConditionPathExists = "%h/.local/share/bruma/gecko/extensions";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${bruma}/bin/bruma --actualizar-extensiones";
        Nice = 15;
        IOSchedulingClass = "idle";
      };
    };
    systemd.user.timers.bruma-actualizar-extensiones = lib.mkIf cfg.extensionesDeChrome {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
        RandomizedDelaySec = "1h";
      };
    };
  };
}
