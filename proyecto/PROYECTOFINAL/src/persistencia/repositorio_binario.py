"""Archivo binario principal de registros (capa de persistencia física).

Implementa :class:`RepositorioBinario`, el repositorio físico de las ASADAS.
Almacena cada registro de **tamaño fijo** de forma secuencial, lo que permite
acceder a cualquier registro directamente mediante su *posición física* (el
desplazamiento en bytes dentro del archivo) sin necesidad de recorrer los
anteriores.

Estrategia de serialización
---------------------------
Se utiliza el módulo :mod:`struct` con un formato de longitud fija. Los campos
numéricos se empaquetan como enteros de 64 bits (``q``) y dobles (``d``); los
campos de texto se codifican en UTF-8 y se almacenan en bloques de bytes de
longitud fija (``Ns``), rellenados con ``\\x00`` o truncados de ser necesario.

Se usa orden de bytes *little-endian* explícito (``<``) con tamaños estándar
para que el archivo sea reproducible en cualquier plataforma; esto es
importante porque el archivo viajará entre el equipo servidor y el repositorio
Git del equipo.
"""

from __future__ import annotations

import os
import struct
from typing import Iterator, List, Optional, Tuple

from src.modelo.asada import Asada


class RepositorioBinario:
    """Repositorio físico de ASADAS sobre un archivo binario de registros fijos.

    Separa el *almacenamiento* de los datos de las *estructuras de indexación*
    (árbol BST e índice geográfico), de modo que los índices solo guardan
    posiciones hacia este archivo y no duplican la información.

    :ivar ruta: Ruta del archivo binario de registros (``registros.dat``).
    """

    #: Definición de los campos de texto: ``(nombre_atributo, bytes_maximos)``.
    _CAMPOS_TEXTO: Tuple[Tuple[str, int], ...] = (
        ("provincia", 60),
        ("canton", 60),
        ("distrito", 60),
        ("operador", 150),
        ("correo", 120),
        ("telefono", 30),
        ("fax", 30),
        ("tipoSistema", 60),
        ("codigoDTA", 20),
    )

    #: Formato struct: id_Asada (q), id_Objecto (q), coordenadaX/Y (d) + textos.
    _FORMATO: str = "<qqdd" + "".join(f"{tam}s" for _, tam in _CAMPOS_TEXTO)

    #: Tamaño en bytes de un registro (constante: registros de tamaño fijo).
    TAMANO_REGISTRO: int = struct.calcsize(_FORMATO)

    def __init__(self, ruta: str) -> None:
        """Inicializa el repositorio y garantiza que el archivo exista.

        :param ruta: Ruta del archivo binario de registros.
        """
        self.ruta: str = ruta
        directorio = os.path.dirname(os.path.abspath(ruta))
        os.makedirs(directorio, exist_ok=True)
        if not os.path.exists(self.ruta):
            open(self.ruta, "wb").close()

    # ------------------------------------------------------------------ #
    # Serialización                                                       #
    # ------------------------------------------------------------------ #
    def _empaquetar(self, asada: Asada) -> bytes:
        """Convierte una :class:`Asada` en su representación binaria fija.

        :param asada: Registro a serializar.
        :returns: Secuencia de bytes de longitud :data:`TAMANO_REGISTRO`.
        """
        textos: List[bytes] = []
        for nombre, tam in self._CAMPOS_TEXTO:
            crudo = getattr(asada, nombre, "").encode("utf-8")[:tam]
            textos.append(crudo)
        return struct.pack(
            self._FORMATO,
            asada.id_Asada,
            asada.id_Objecto,
            asada.coordenadaX,
            asada.coordenadaY,
            *textos,
        )

    def _desempaquetar(self, datos: bytes) -> Asada:
        """Reconstruye una :class:`Asada` desde su representación binaria.

        :param datos: Bloque de bytes de longitud :data:`TAMANO_REGISTRO`.
        :returns: La :class:`Asada` reconstruida.
        """
        valores = struct.unpack(self._FORMATO, datos)
        id_asada, id_objecto, coord_x, coord_y = valores[:4]
        textos = valores[4:]
        campos = {
            nombre: bruto.rstrip(b"\x00").decode("utf-8", errors="ignore")
            for (nombre, _), bruto in zip(self._CAMPOS_TEXTO, textos)
        }
        return Asada(
            id_Asada=id_asada,
            id_Objecto=id_objecto,
            coordenadaX=coord_x,
            coordenadaY=coord_y,
            **campos,
        )

    # ------------------------------------------------------------------ #
    # Escritura                                                           #
    # ------------------------------------------------------------------ #
    def escribir_registro(self, asada: Asada) -> int:
        """Agrega un registro al final del archivo y devuelve su posición.

        :param asada: Registro a almacenar.
        :returns: Posición física (desplazamiento en bytes) del registro
            escrito, que debe guardarse en los índices.
        """
        with open(self.ruta, "ab") as archivo:
            posicion = archivo.tell()
            archivo.write(self._empaquetar(asada))
        return posicion

    def reescribir(self, asadas: List[Asada]) -> List[Tuple[int, int]]:
        """Regenera por completo el archivo con la lista de ASADAS dada.

        Trunca el contenido previo y escribe todos los registros de forma
        secuencial. Es la operación que invoca la actualización incremental.

        :param asadas: Lista completa de ASADAS a persistir.
        :returns: Lista de pares ``(id_Asada, posicion)`` en el mismo orden de
            escritura, lista para alimentar la reconstrucción de los índices.
        """
        pares: List[Tuple[int, int]] = []
        with open(self.ruta, "wb") as archivo:
            for asada in asadas:
                posicion = archivo.tell()
                archivo.write(self._empaquetar(asada))
                pares.append((asada.id_Asada, posicion))
        return pares

    # ------------------------------------------------------------------ #
    # Lectura                                                             #
    # ------------------------------------------------------------------ #
    def leer_registro(self, posicion: int) -> Asada:
        """Lee el registro ubicado en una posición física concreta.

        Cada lectura abre su propio descriptor de archivo, por lo que la
        operación es segura ante accesos concurrentes de solo lectura (el
        servidor del Desarrollador B atiende varios clientes con hilos).

        :param posicion: Desplazamiento en bytes devuelto al escribir/indexar.
        :returns: La :class:`Asada` almacenada en esa posición.
        :raises ValueError: Si la posición no contiene un registro completo.
        """
        with open(self.ruta, "rb") as archivo:
            archivo.seek(posicion)
            datos = archivo.read(self.TAMANO_REGISTRO)
        if len(datos) != self.TAMANO_REGISTRO:
            raise ValueError(
                f"Posición inválida {posicion}: no hay un registro completo."
            )
        return self._desempaquetar(datos)

    def recorrer_todos(self) -> Iterator[Asada]:
        """Itera secuencialmente sobre todos los registros del archivo.

        :yields: Cada :class:`Asada` almacenada, en orden físico.
        """
        with open(self.ruta, "rb") as archivo:
            while True:
                datos = archivo.read(self.TAMANO_REGISTRO)
                if len(datos) < self.TAMANO_REGISTRO:
                    break
                yield self._desempaquetar(datos)

    def cantidad_registros(self) -> int:
        """Devuelve la cantidad de registros almacenados.

        :returns: Número de registros (tamaño del archivo / tamaño fijo).
        """
        return os.path.getsize(self.ruta) // self.TAMANO_REGISTRO
