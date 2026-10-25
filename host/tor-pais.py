"""Cambia el país de salida del Tor de la ventana con Tor de Velbrum.

Uso: python3 -I tor-pais.py SOCKET_CONTROL ARCHIVO_COOKIE PAIS
PAIS es un código de dos letras (de, nl, us…) o «auto» (cualquier país).

Habla con el puerto de control de Tor (un socket Unix que solo tu usuario
puede abrir, con autenticación por cookie): fija ExitNodes/StrictNodes y pide
circuitos nuevos (NEWNYM). Lo llama el lanzador («velbrum --tor-pais»), que
valida el código antes.
"""
import re
import socket
import sys


def main():
    control, archivo_cookie, pais = sys.argv[1:4]
    if pais != "auto" and not re.fullmatch(r"[a-z]{2}", pais):
        raise SystemExit("código de país inválido")
    with open(archivo_cookie, "rb") as f:
        cookie = f.read().hex()
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(15)
        s.connect(control)
        lector = s.makefile("rb")

        def pedir(orden):
            s.sendall(orden.encode() + b"\r\n")
            respuesta = lector.readline().decode(errors="replace").strip()
            if not respuesta.startswith("250"):
                raise SystemExit(f"Tor respondió: {respuesta}")

        pedir(f"AUTHENTICATE {cookie}")
        if pais == "auto":
            pedir("RESETCONF ExitNodes StrictNodes")
        else:
            pedir(f"SETCONF ExitNodes={{{pais}}} StrictNodes=1")
        pedir("SIGNAL NEWNYM")
        pedir("QUIT")


main()
