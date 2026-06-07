"""Persistencia binaria del índice geográfico jerárquico (tercer archivo binario).

Implementa :class:`IndiceGeograficoBinario`, que serializa y deserializa la
estructura de listas enlazadas ``provincia → cantón → distrito → ASADAs`` en el
archivo ``data/indice_geografico.dat`` usando **punteros lógicos** (offsets de
bytes dentro del propio archivo).

Disposición del archivo
-----------------------
::

    [ Cabecera: 8 bytes  → primera_provincia_pos (int64, NULO=-1) ]
    [ Nodos de tipo provincia, cantón, distrito y hoja ASADA mezclados;
      cada nodo lleva sus punteros "siguiente" y "primer_hijo" como offsets ]

Tipos de nodo (identificados por el campo ``tipo_nodo``)
---------------------------------------------------------
* ``TIPO_PROVINCIA  = 1`` : nombre(60b) + primer_canton(8b) + siguiente(8b)
* ``TIPO_CANTON     = 2`` : nombre(60b) + primer_distrito(8b) + siguiente(8b)
* ``TIPO_DISTRITO   = 3`` : nombre(60b) + primer_asada(8b) + siguiente(8b)
* ``TIPO_ASADA      = 4`` : id_asada(8b) + pos_registro(8b) + siguiente(8b)

Para permitir un único recorrido secuencial sin conocer el tipo de antemano,
todos los nodos comienzan con un campo ``tipo_nodo`` (int64), seguido del
resto de sus campos. Esto hace que los tamaños sean:

* Nodos de nombre (provincia/cantón/distrito): 1×8 + 60 + 8 + 8 = 84 bytes
* Nodo ASADA: 1×8 + 8 + 8 + 8 = 32 bytes

Los punteros usan el valor ``NULO = -1`` para representar "sin nodo".
"""

from __future__ import annotations

import os
import struct
from typing import List, Optional, Tuple

from src.geografia.nodos_geograficos import (
    NodoAsadaGeo,
    NodoCanton,
    NodoDistrito,
    NodoProvincia,
)

# ---------------------------------------------------------------------------
# Constantes de tipo de nodo
# ---------------------------------------------------------------------------
TIPO_PROVINCIA = 1
TIPO_CANTON    = 2
TIPO_DISTRITO  = 3
TIPO_ASADA     = 4

#: Valor centinela para puntero nulo (sin hijo / sin siguiente).
NULO: int = -1

# ---------------------------------------------------------------------------
# Formatos struct (little-endian, tamaños estándar)
# ---------------------------------------------------------------------------
#: Cabecera: un solo int64 con la posición de la primera provincia.
_FMT_CABECERA = "<q"
_TAM_CABECERA = struct.calcsize(_FMT_CABECERA)

#: Nodo con nombre (provincia, cantón, distrito):
#:   tipo(8b) + nombre(60b) + primer_hijo(8b) + siguiente(8b) = 84 bytes
_FMT_NOMBRE = "<q60sqq"
_TAM_NOMBRE = struct.calcsize(_FMT_NOMBRE)

#: Nodo hoja de ASADA:
#:   tipo(8b) + id_asada(8b) + pos_registro(8b) + siguiente(8b) = 32 bytes
_FMT_ASADA = "<qqqq"
_TAM_ASADA = struct.calcsize(_FMT_ASADA)


class IndiceGeograficoBinario:
    """Serializa y deserializa el índice geográfico en un archivo binario.

    Genera un **tercer archivo binario** (``data/indice_geografico.dat``)
    independiente del archivo de registros y del árbol BST. Su estructura
    replica fielmente la lista enlazada jerárquica que vive en memoria,
    reemplazando referencias de Python por punteros lógicos (offsets en bytes
    dentro del propio archivo).

    :ivar ruta: Ruta del archivo binario del índice geográfico.
    """

    def __init__(self, ruta: str) -> None:
        """Inicializa el índice y crea el directorio si no existe.

        :param ruta: Ruta del archivo binario (p. ej. ``data/indice_geografico.dat``).
        """
        self.ruta: str = ruta
        directorio = os.path.dirname(os.path.abspath(ruta))
        os.makedirs(directorio, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Serialización (escritura)                                           #
    # ------------------------------------------------------------------ #

    def serializar(self, primera_provincia: Optional[NodoProvincia]) -> None:
        """Persiste toda la estructura geográfica en el archivo binario.

        Realiza una escritura completa (trunca el contenido previo). El
        algoritmo recorre la estructura jerárquica en dos pasadas:

        1. **Cálculo de offsets**: recorre los nodos en el orden de escritura
           y asigna a cada uno su posición final dentro del archivo.
        2. **Escritura**: vuelve a recorrer el árbol y escribe cada nodo con
           los punteros ya calculados.

        :param primera_provincia: Cabeza de la lista de provincias del
            :class:`~src.geografia.indice_geografico.IndiceGeografico`.
        """
        # ------------------------------------------------------------------
        # Pasada 1: calcular offset de cada nodo en el orden de escritura.
        # El orden es BFS por nivel: todas las provincias, luego todos los
        # cantones (en orden de provincia), etc.  Esto permite reconstruir
        # la estructura completa desde el archivo en un solo recorrido.
        # ------------------------------------------------------------------
        provincias: List[NodoProvincia] = []
        cantones:   List[NodoCanton]   = []
        distritos:  List[NodoDistrito] = []
        hojas:      List[NodoAsadaGeo] = []

        p = primera_provincia
        while p is not None:
            provincias.append(p)
            c = p.primer_canton
            while c is not None:
                cantones.append(c)
                d = c.primer_distrito
                while d is not None:
                    distritos.append(d)
                    a = d.primer_asada
                    while a is not None:
                        hojas.append(a)
                        a = a.siguiente
                    d = d.siguiente
                c = c.siguiente
            p = p.siguiente

        # Asignar offsets según el orden de escritura.
        # Orden: [ cabecera ][ provincias ][ cantones ][ distritos ][ hojas ]
        offset_actual = _TAM_CABECERA
        offsets_provincia: dict = {}
        for nodo in provincias:
            offsets_provincia[id(nodo)] = offset_actual
            offset_actual += _TAM_NOMBRE

        offsets_canton: dict = {}
        for nodo in cantones:
            offsets_canton[id(nodo)] = offset_actual
            offset_actual += _TAM_NOMBRE

        offsets_distrito: dict = {}
        for nodo in distritos:
            offsets_distrito[id(nodo)] = offset_actual
            offset_actual += _TAM_NOMBRE

        offsets_hoja: dict = {}
        for nodo in hojas:
            offsets_hoja[id(nodo)] = offset_actual
            offset_actual += _TAM_ASADA

        # ------------------------------------------------------------------
        # Pasada 2: escribir el archivo.
        # ------------------------------------------------------------------
        with open(self.ruta, "wb") as f:
            # Cabecera: offset de la primera provincia (NULO si no hay ninguna)
            primera_prov_pos = offsets_provincia[id(provincias[0])] if provincias else NULO
            f.write(struct.pack(_FMT_CABECERA, primera_prov_pos))

            # Nodos de provincia
            for nodo in provincias:
                sig_pos  = offsets_provincia[id(nodo.siguiente)] if nodo.siguiente else NULO
                hijo_pos = offsets_canton[id(nodo.primer_canton)] if nodo.primer_canton else NULO
                f.write(struct.pack(
                    _FMT_NOMBRE,
                    TIPO_PROVINCIA,
                    nodo.nombre.encode("utf-8")[:60].ljust(60, b"\x00"),
                    hijo_pos,
                    sig_pos,
                ))

            # Nodos de cantón
            for nodo in cantones:
                sig_pos  = offsets_canton[id(nodo.siguiente)] if nodo.siguiente else NULO
                hijo_pos = offsets_distrito[id(nodo.primer_distrito)] if nodo.primer_distrito else NULO
                f.write(struct.pack(
                    _FMT_NOMBRE,
                    TIPO_CANTON,
                    nodo.nombre.encode("utf-8")[:60].ljust(60, b"\x00"),
                    hijo_pos,
                    sig_pos,
                ))

            # Nodos de distrito
            for nodo in distritos:
                sig_pos  = offsets_distrito[id(nodo.siguiente)] if nodo.siguiente else NULO
                hijo_pos = offsets_hoja[id(nodo.primer_asada)] if nodo.primer_asada else NULO
                f.write(struct.pack(
                    _FMT_NOMBRE,
                    TIPO_DISTRITO,
                    nodo.nombre.encode("utf-8")[:60].ljust(60, b"\x00"),
                    hijo_pos,
                    sig_pos,
                ))

            # Nodos hoja de ASADA
            for nodo in hojas:
                sig_pos = offsets_hoja[id(nodo.siguiente)] if nodo.siguiente else NULO
                f.write(struct.pack(
                    _FMT_ASADA,
                    TIPO_ASADA,
                    int(nodo.id_asada),
                    nodo.posicion_registro,
                    sig_pos,
                ))

    # ------------------------------------------------------------------ #
    # Deserialización (lectura)                                           #
    # ------------------------------------------------------------------ #

    def deserializar(self) -> Optional[NodoProvincia]:
        """Reconstruye la lista de provincias desde el archivo binario.

        Lee el archivo secuencialmente y reconstruye los nodos en memoria,
        siguiendo los punteros lógicos para enlazarlos en la misma jerarquía
        que tenían antes de serializar.

        :returns: El primer nodo de provincia, o ``None`` si el archivo está
            vacío o no existe.
        """
        if not os.path.exists(self.ruta) or os.path.getsize(self.ruta) < _TAM_CABECERA:
            return None

        with open(self.ruta, "rb") as f:
            contenido = f.read()

        if len(contenido) < _TAM_CABECERA:
            return None

        # Leer la cabecera para obtener el offset de la primera provincia.
        (primera_prov_pos,) = struct.unpack_from(_FMT_CABECERA, contenido, 0)
        if primera_prov_pos == NULO:
            return None

        # Construir un mapa offset → nodo Python a medida que se lee.
        # Se lee el archivo completo y se resuelven los punteros en una segunda
        # pasada, de modo que el orden físico de los nodos en el archivo no
        # importa para la reconstrucción.
        nodos_nombre: dict = {}  # offset → (tipo, nombre, hijo_pos, sig_pos)
        nodos_hoja:   dict = {}  # offset → (id_asada, pos_registro, sig_pos)

        offset = _TAM_CABECERA
        while offset < len(contenido):
            # Leer el campo tipo sin consumir el resto del nodo.
            if offset + 8 > len(contenido):
                break
            (tipo,) = struct.unpack_from("<q", contenido, offset)

            if tipo in (TIPO_PROVINCIA, TIPO_CANTON, TIPO_DISTRITO):
                if offset + _TAM_NOMBRE > len(contenido):
                    break
                _, nombre_b, hijo_pos, sig_pos = struct.unpack_from(_FMT_NOMBRE, contenido, offset)
                nombre = nombre_b.rstrip(b"\x00").decode("utf-8", errors="ignore")
                nodos_nombre[offset] = (tipo, nombre, hijo_pos, sig_pos)
                offset += _TAM_NOMBRE

            elif tipo == TIPO_ASADA:
                if offset + _TAM_ASADA > len(contenido):
                    break
                _, id_asada, pos_registro, sig_pos = struct.unpack_from(_FMT_ASADA, contenido, offset)
                nodos_hoja[offset] = (id_asada, pos_registro, sig_pos)
                offset += _TAM_ASADA
            else:
                # Nodo desconocido: detener la lectura.
                break

        # ------------------------------------------------------------------
        # Segunda pasada: construir los objetos Python encadenados.
        # ------------------------------------------------------------------
        def _reconstruir_provincia(pos: int) -> Optional[NodoProvincia]:
            if pos == NULO or pos not in nodos_nombre:
                return None
            tipo, nombre, hijo_pos, sig_pos = nodos_nombre[pos]
            nodo = NodoProvincia(nombre)
            nodo.primer_canton = _reconstruir_canton(hijo_pos)
            nodo.siguiente     = _reconstruir_provincia(sig_pos)
            return nodo

        def _reconstruir_canton(pos: int) -> Optional[NodoCanton]:
            if pos == NULO or pos not in nodos_nombre:
                return None
            tipo, nombre, hijo_pos, sig_pos = nodos_nombre[pos]
            nodo = NodoCanton(nombre)
            nodo.primer_distrito = _reconstruir_distrito(hijo_pos)
            nodo.siguiente       = _reconstruir_canton(sig_pos)
            return nodo

        def _reconstruir_distrito(pos: int) -> Optional[NodoDistrito]:
            if pos == NULO or pos not in nodos_nombre:
                return None
            tipo, nombre, hijo_pos, sig_pos = nodos_nombre[pos]
            nodo = NodoDistrito(nombre)
            nodo.primer_asada = _reconstruir_asada(hijo_pos)
            nodo.siguiente    = _reconstruir_distrito(sig_pos)
            return nodo

        def _reconstruir_asada(pos: int) -> Optional[NodoAsadaGeo]:
            if pos == NULO or pos not in nodos_hoja:
                return None
            id_asada, pos_registro, sig_pos = nodos_hoja[pos]
            nodo = NodoAsadaGeo(id_asada, pos_registro)
            nodo.siguiente = _reconstruir_asada(sig_pos)
            return nodo

        return _reconstruir_provincia(primera_prov_pos)

    # ------------------------------------------------------------------ #
    # Utilidades                                                          #
    # ------------------------------------------------------------------ #

    def existe(self) -> bool:
        """Indica si el archivo binario existe y tiene contenido.

        :returns: ``True`` si el archivo existe y su tamaño supera la cabecera.
        """
        return (
            os.path.exists(self.ruta)
            and os.path.getsize(self.ruta) > _TAM_CABECERA
        )

    def tamano_bytes(self) -> int:
        """Devuelve el tamaño en bytes del archivo binario.

        :returns: Tamaño en bytes, o 0 si el archivo no existe.
        """
        if not os.path.exists(self.ruta):
            return 0
        return os.path.getsize(self.ruta)
