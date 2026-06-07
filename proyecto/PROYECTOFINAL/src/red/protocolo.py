"""
Protocolo de comunicación cliente-servidor (capa de red, Dev B).

El protocolo es **JSON delimitado por saltos de línea**: cada mensaje es un
objeto JSON en una sola línea terminada en ``\\n``. Esto resuelve el problema
clásico de TCP (los mensajes pueden llegar partidos o pegados en un mismo
``recv``), porque leemos exactamente hasta el siguiente ``\\n``.

Formato de CONSULTA (cliente → servidor):
    {"tipo": "por_id",     "id": 50}
    {"tipo": "provincias"}
    {"tipo": "cantones",   "provincia": "Alajuela"}
    {"tipo": "distritos",  "provincia": "Alajuela", "canton": "San Carlos"}
    {"tipo": "asadas",     "provincia": ..., "canton": ..., "distrito": ...}
    {"tipo": "salir"}

Formato de RESPUESTA (servidor → cliente):
    {"ok": true,  "tipo": ..., "datos": <lo que corresponda>}
    {"ok": false, "error": "mensaje"}
"""

from __future__ import annotations

import json
import socket
from typing import Any, Optional

# Tipos de consulta válidos (el servidor rechaza cualquier otro).
TIPOS_VALIDOS = {"por_id", "provincias", "cantones", "distritos", "asadas", "salir"}


class Protocolo:
    """Serializa y deserializa mensajes (sin tocar el socket)."""

    @staticmethod
    def serializar(objeto: dict) -> bytes:
        """Convierte un dict en una línea JSON lista para enviar."""
        return (json.dumps(objeto, ensure_ascii=False) + "\n").encode("utf-8")

    @staticmethod
    def deserializar(linea: bytes) -> dict:
        """Convierte una línea JSON recibida en un dict."""
        return json.loads(linea.decode("utf-8"))

    # Atajos legibles para construir mensajes -------------------------------
    @staticmethod
    def consulta(tipo: str, **parametros: Any) -> dict:
        return {"tipo": tipo, **parametros}

    @staticmethod
    def respuesta_ok(tipo: str, datos: Any) -> dict:
        return {"ok": True, "tipo": tipo, "datos": datos}

    @staticmethod
    def respuesta_error(mensaje: str) -> dict:
        return {"ok": False, "error": mensaje}


class Conexion:
    """Envuelve un socket TCP y habla el protocolo (con framing por líneas).

    Mantiene un búfer interno para reconstruir mensajes completos aunque TCP
    los entregue partidos o combinados.
    """

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._buffer = b""

    def enviar(self, objeto: dict) -> None:
        """Envía un mensaje (dict) completo."""
        self.sock.sendall(Protocolo.serializar(objeto))

    def recibir(self) -> Optional[dict]:
        """Lee un mensaje completo. Devuelve ``None`` si la conexión se cerró."""
        while b"\n" not in self._buffer:
            try:
                chunk = self.sock.recv(4096)
            except OSError:
                return None
            if not chunk:                       # el otro extremo cerró
                return None
            self._buffer += chunk
        linea, self._buffer = self._buffer.split(b"\n", 1)
        if not linea.strip():                   # ignora líneas vacías
            return self.recibir()
        try:
            return Protocolo.deserializar(linea)
        except json.JSONDecodeError:
            return {"ok": False, "error": "JSON inválido"}

    def cerrar(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass
