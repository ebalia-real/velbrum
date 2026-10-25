#!/bin/sh
# Que el menú y los íconos de Velbrum aparezcan (o desaparezcan) sin reiniciar.
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
exit 0
