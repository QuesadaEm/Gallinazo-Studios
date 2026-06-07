"""
Cliente de consultas (capa de red, Dev B).

Expone una API programática sencilla sobre el protocolo de sockets. La GUI
(``ventana_principal.py``) y cualquier script la usan sin preocuparse por el
manejo del socket ni por el formato de los mensajes.

Cada método envía una consulta y devuelve los datos ya desempaquetados, o
lanza :class:`ErrorConsulta` si el servidor respondió con error.
"""

from __future__ import annotations

import socket
from typing import Dict, List, Optional

from src.red.protocolo import Conexion, Protocolo


class ErrorConsulta(Exception):
    """El servidor respondió con un error a una consulta."""


class Cliente:
    """Cliente TCP que consulta al servidor de ASADAS."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5000) -> None:
        self.host = host
        self.port = port
        self._conexion: Optional[Conexion] = None

    # ------------------------------------------------------------------ #
    # Ciclo de vida                                                       #
    # ------------------------------------------------------------------ #
    def conectar(self) -> None:
        sock = socket.create_connection((self.host, self.port))
        self._conexion = Conexion(sock)

    def cerrar(self) -> None:
        if self._conexion is not None:
            try:
                self._conexion.enviar(Protocolo.consulta("salir"))
            except OSError:
                pass
            self._conexion.cerrar()
            self._conexion = None

    def __enter__(self) -> "Cliente":
        self.conectar()
        return self

    def __exit__(self, *_) -> None:
        self.cerrar()

    # ------------------------------------------------------------------ #
    # Consultas                                                           #
    # ------------------------------------------------------------------ #
    def _pedir(self, consulta: dict):
        if self._conexion is None:
            raise ErrorConsulta("El cliente no está conectado. Llamá a conectar().")
        self._conexion.enviar(consulta)
        respuesta = self._conexion.recibir()
        if respuesta is None:
            raise ErrorConsulta("El servidor cerró la conexión.")
        if not respuesta.get("ok"):
            raise ErrorConsulta(respuesta.get("error", "Error desconocido."))
        return respuesta.get("datos")

    def provincias(self) -> List[str]:
        return self._pedir(Protocolo.consulta("provincias"))

    def cantones(self, provincia: str) -> List[str]:
        return self._pedir(Protocolo.consulta("cantones", provincia=provincia))

    def distritos(self, provincia: str, canton: str) -> List[str]:
        return self._pedir(Protocolo.consulta("distritos", provincia=provincia, canton=canton))

    def asadas(self, provincia: str, canton: str, distrito: str) -> List[Dict]:
        return self._pedir(Protocolo.consulta(
            "asadas", provincia=provincia, canton=canton, distrito=distrito))

    def por_id(self, id_asada: int) -> Dict:
        return self._pedir(Protocolo.consulta("por_id", id=id_asada))
