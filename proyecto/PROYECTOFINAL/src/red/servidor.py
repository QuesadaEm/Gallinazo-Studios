"""
Servidor de consultas concurrente (capa de red, Dev B).

Atiende a múltiples clientes a la vez usando **un hilo por cliente**
(:class:`ManejadorCliente`, subclase de ``threading.Thread``). Cada hilo solo
hace operaciones de SOLO LECTURA sobre estructuras compartidas:

  - el `MotorConsulta` de Dev A (búsqueda por id; abre su propio descriptor de
    archivo por lectura, así que es seguro entre hilos), y
  - el `IndiceGeografico` de Dev B (inmutable tras construirse).

Por eso no hacen falta locks para las consultas. La única operación de
escritura (actualizar datos) ya está serializada con un candado dentro del
MotorConsulta y no la expone el servidor.
"""

from __future__ import annotations

import socket
import threading
from typing import Tuple

from src.api.motor_consulta import MotorConsulta
from src.geografia.indice_geografico import IndiceGeografico
from src.red.protocolo import Conexion, Protocolo, TIPOS_VALIDOS


class ManejadorCliente(threading.Thread):
    """Hilo que atiende todas las consultas de un cliente."""

    def __init__(self, sock: socket.socket, direccion: Tuple[str, int],
                 motor: MotorConsulta, indice_geo: IndiceGeografico) -> None:
        super().__init__(daemon=True)
        self.conexion = Conexion(sock)
        self.direccion = direccion
        self.motor = motor
        self.indice_geo = indice_geo

    def run(self) -> None:
        print(f"[+] Cliente conectado desde {self.direccion}")
        try:
            while True:
                consulta = self.conexion.recibir()
                if consulta is None:                 # el cliente cerró
                    break
                if consulta.get("tipo") == "salir":
                    break
                respuesta = self._despachar(consulta)
                self.conexion.enviar(respuesta)
        except Exception as error:                   # nunca tumbar el hilo en silencio
            try:
                self.conexion.enviar(Protocolo.respuesta_error(str(error)))
            except OSError:
                pass
        finally:
            self.conexion.cerrar()
            print(f"[-] Cliente {self.direccion} desconectado")

    # ------------------------------------------------------------------ #
    def _despachar(self, consulta: dict) -> dict:
        """Ejecuta la consulta y devuelve la respuesta del protocolo."""
        tipo = consulta.get("tipo")
        if tipo not in TIPOS_VALIDOS:
            return Protocolo.respuesta_error(f"Tipo de consulta desconocido: {tipo!r}")

        if tipo == "provincias":
            return Protocolo.respuesta_ok(tipo, self.indice_geo.provincias())

        if tipo == "cantones":
            prov = consulta.get("provincia", "")
            return Protocolo.respuesta_ok(tipo, self.indice_geo.cantones_de(prov))

        if tipo == "distritos":
            prov = consulta.get("provincia", "")
            cant = consulta.get("canton", "")
            return Protocolo.respuesta_ok(tipo, self.indice_geo.distritos_de(prov, cant))

        if tipo == "por_id":
            try:
                id_asada = int(consulta.get("id"))
            except (TypeError, ValueError):
                return Protocolo.respuesta_error("El campo 'id' debe ser un entero.")
            asada = self.motor.obtener_asada(id_asada)
            if asada is None:
                return Protocolo.respuesta_error(f"No existe la ASADA con id {id_asada}.")
            return Protocolo.respuesta_ok(tipo, asada.a_dict())

        if tipo == "asadas":
            prov = consulta.get("provincia", "")
            cant = consulta.get("canton", "")
            dist = consulta.get("distrito", "")
            # El índice geográfico da (id, posición). La posición es el puntero
            # lógico al archivo principal: leemos cada registro directamente.
            registros = []
            for _id, posicion in self.indice_geo.asadas_de(prov, cant, dist):
                asada = self.motor.repositorio.leer_registro(posicion)
                registros.append(asada.a_dict())
            return Protocolo.respuesta_ok(tipo, registros)

        return Protocolo.respuesta_error(f"Tipo no implementado: {tipo!r}")


class Servidor:
    """Servidor TCP que acepta clientes y lanza un hilo por cada uno."""

    def __init__(self, motor: MotorConsulta, indice_geo: IndiceGeografico,
                 host: str = "0.0.0.0", port: int = 5000) -> None:
        self.motor = motor
        self.indice_geo = indice_geo
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._activo = False

    def preparar(self) -> int:
        """Crea el socket, hace bind y listen. Devuelve el puerto real usado."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.listen(10)
        self.port = self._socket.getsockname()[1]   # resuelve puerto 0 -> real
        return self.port

    def servir(self) -> None:
        """Bucle principal: acepta conexiones y lanza un hilo por cliente."""
        self._activo = True
        print(f"Servidor escuchando en {self.host}:{self.port}")
        while self._activo:
            try:
                sock, direccion = self._socket.accept()
            except OSError:
                break                                # socket cerrado por detener()
            ManejadorCliente(sock, direccion, self.motor, self.indice_geo).start()

    def iniciar(self) -> None:
        """Prepara y sirve (bloquea). Atajo para uso normal."""
        self.preparar()
        self.servir()

    def detener(self) -> None:
        """Detiene el bucle de aceptación y cierra el socket de escucha."""
        self._activo = False
        if self._socket:
            self._socket.close()
