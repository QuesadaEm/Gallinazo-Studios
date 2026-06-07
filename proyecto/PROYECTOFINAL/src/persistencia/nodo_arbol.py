"""Nodo del Árbol Binario de Búsqueda persistente.

Define :class:`NodoArbol`, la unidad de almacenamiento del índice por
``id_Asada``. Cada nodo guarda, además de su llave, la **posición física** del
registro dentro del archivo principal y los **punteros lógicos** (posiciones en
bytes dentro del propio archivo de índice) hacia sus hijos izquierdo y derecho.

Un puntero lógico con valor :data:`NodoArbol.NULO` indica la ausencia de hijo.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class NodoArbol:
    """Nodo serializable de un BST persistido en archivo binario.

    :ivar id_Asada: Llave de ordenamiento del árbol (identificador de ASADA).
    :ivar posicion_registro: Posición física del registro en ``registros.dat``.
    :ivar pos_izquierdo: Puntero lógico al hijo izquierdo (o :data:`NULO`).
    :ivar pos_derecho: Puntero lógico al hijo derecho (o :data:`NULO`).
    """

    #: Formato struct de un nodo: cuatro enteros de 64 bits, little-endian.
    FORMATO: ClassVar[str] = "<qqqq"

    #: Valor que representa un puntero nulo (hijo inexistente).
    NULO: ClassVar[int] = -1

    #: Tamaño en bytes de un nodo serializado (constante).
    TAMANO: ClassVar[int] = struct.calcsize("<qqqq")

    id_Asada: int
    posicion_registro: int
    pos_izquierdo: int = -1
    pos_derecho: int = -1

    def empaquetar(self) -> bytes:
        """Serializa el nodo a bytes de longitud :data:`TAMANO`.

        :returns: Representación binaria del nodo.
        """
        return struct.pack(
            self.FORMATO,
            self.id_Asada,
            self.posicion_registro,
            self.pos_izquierdo,
            self.pos_derecho,
        )

    @classmethod
    def desempaquetar(cls, datos: bytes) -> "NodoArbol":
        """Reconstruye un nodo desde su representación binaria.

        :param datos: Bloque de bytes de longitud :data:`TAMANO`.
        :returns: El :class:`NodoArbol` reconstruido.
        """
        id_asada, pos_reg, izq, der = struct.unpack(cls.FORMATO, datos)
        return cls(
            id_Asada=id_asada,
            posicion_registro=pos_reg,
            pos_izquierdo=izq,
            pos_derecho=der,
        )
