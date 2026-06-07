"""Índice persistente basado en Árbol Binario de Búsqueda.

Implementa :class:`IndiceArbolBinario`, un BST indexado por ``id_Asada`` que se
persiste en un **segundo archivo binario** (``indice_arbol.dat``) usando
punteros lógicos, y que puede **cargarse en memoria** para realizar búsquedas
rápidas durante la ejecución.

Disposición del archivo de índice
----------------------------------
::

    [ cabecera: <q  -> posición lógica de la raíz (NULO si está vacío) ]
    [ nodo 0 ][ nodo 1 ] ... [ nodo n ]   (cada uno de tamaño NodoArbol.TAMANO)

La cabecera ocupa los primeros :data:`IndiceArbolBinario._TAMANO_CABECERA`
bytes; los nodos se agregan a continuación. La "posición lógica" de un nodo es
su desplazamiento en bytes dentro de este archivo, y es justamente el valor que
otros nodos guardan en ``pos_izquierdo`` / ``pos_derecho``.

Estrategia de balanceo
----------------------
La inserción individual (:meth:`insertar`) implementa un BST clásico sobre
disco. La reconstrucción masiva (:meth:`reconstruir`), usada por la
actualización incremental, inserta las llaves en **orden mediano-primero** a
partir de una lista ordenada, lo que produce un árbol balanceado y mantiene las
búsquedas en ``O(log n)`` incluso cuando los datos vienen ordenados por id.
"""

from __future__ import annotations

import os
import struct
from typing import Dict, Iterable, List, Optional, Tuple

from src.persistencia.nodo_arbol import NodoArbol


class _NodoMemoria:
    """Nodo del árbol cargado en memoria (representación en RAM).

    Refleja la estructura del árbol siguiendo los punteros lógicos del archivo,
    de modo que la búsqueda en memoria recorre un árbol real y no una simple
    tabla.
    """

    __slots__ = ("id_Asada", "posicion_registro", "izquierdo", "derecho")

    def __init__(self, id_asada: int, posicion_registro: int) -> None:
        self.id_Asada: int = id_asada
        self.posicion_registro: int = posicion_registro
        self.izquierdo: Optional["_NodoMemoria"] = None
        self.derecho: Optional["_NodoMemoria"] = None


class IndiceArbolBinario:
    """Árbol Binario de Búsqueda persistente indexado por ``id_Asada``.

    :ivar ruta: Ruta del archivo binario de índice (``indice_arbol.dat``).
    """

    #: La cabecera almacena un único entero de 64 bits: la raíz del árbol.
    _FORMATO_CABECERA: str = "<q"
    _TAMANO_CABECERA: int = struct.calcsize("<q")

    def __init__(self, ruta: str) -> None:
        """Inicializa el índice y crea el archivo con cabecera vacía si no existe.

        :param ruta: Ruta del archivo binario de índice.
        """
        self.ruta: str = ruta
        directorio = os.path.dirname(os.path.abspath(ruta))
        os.makedirs(directorio, exist_ok=True)
        if not os.path.exists(self.ruta) or os.path.getsize(self.ruta) < self._TAMANO_CABECERA:
            self._inicializar_archivo()
        # Caché en memoria (se llena con cargar_en_memoria()).
        self._raiz_memoria: Optional[_NodoMemoria] = None
        self._en_memoria: bool = False

    # ------------------------------------------------------------------ #
    # Utilidades de cabecera y nodos (nivel de archivo)                   #
    # ------------------------------------------------------------------ #
    def _inicializar_archivo(self) -> None:
        """Crea (o reinicia) el archivo con la cabecera apuntando a NULO."""
        with open(self.ruta, "wb") as archivo:
            archivo.write(struct.pack(self._FORMATO_CABECERA, NodoArbol.NULO))

    def _leer_raiz(self, archivo) -> int:
        """Lee la posición lógica de la raíz desde la cabecera."""
        archivo.seek(0)
        (raiz,) = struct.unpack(
            self._FORMATO_CABECERA, archivo.read(self._TAMANO_CABECERA)
        )
        return raiz

    def _escribir_raiz(self, archivo, posicion: int) -> None:
        """Actualiza la posición lógica de la raíz en la cabecera."""
        archivo.seek(0)
        archivo.write(struct.pack(self._FORMATO_CABECERA, posicion))

    def _leer_nodo(self, archivo, posicion: int) -> NodoArbol:
        """Lee y deserializa el nodo ubicado en una posición lógica."""
        archivo.seek(posicion)
        return NodoArbol.desempaquetar(archivo.read(NodoArbol.TAMANO))

    def _anexar_nodo(self, archivo, nodo: NodoArbol) -> int:
        """Agrega un nodo al final del archivo y devuelve su posición lógica."""
        archivo.seek(0, os.SEEK_END)
        posicion = archivo.tell()
        archivo.write(nodo.empaquetar())
        return posicion

    def _actualizar_puntero(self, archivo, posicion_padre: int, es_izquierdo: bool, valor: int) -> None:
        """Reescribe in situ el puntero izquierdo o derecho de un nodo.

        Evita reescribir el nodo completo: posiciona el descriptor sobre el
        campo exacto del puntero y escribe únicamente sus 8 bytes.

        :param posicion_padre: Posición lógica del nodo padre.
        :param es_izquierdo: ``True`` para el puntero izquierdo, ``False`` para
            el derecho.
        :param valor: Nueva posición lógica del hijo.
        """
        # Disposición de un nodo: [id_Asada][posicion_registro][izq][der]
        desplazamiento = 2 * 8 if es_izquierdo else 3 * 8
        archivo.seek(posicion_padre + desplazamiento)
        archivo.write(struct.pack("<q", valor))

    # ------------------------------------------------------------------ #
    # Inserción                                                           #
    # ------------------------------------------------------------------ #
    def _insertar_en(self, archivo, id_asada: int, posicion_registro: int) -> None:
        """Inserta un par (id, posición) operando sobre un archivo ya abierto.

        Mantiene la propiedad de BST. Si la llave ya existe, actualiza la
        posición física del registro asociado (caso de regeneración).
        """
        raiz = self._leer_raiz(archivo)
        nuevo = NodoArbol(id_asada, posicion_registro)

        if raiz == NodoArbol.NULO:
            posicion = self._anexar_nodo(archivo, nuevo)
            self._escribir_raiz(archivo, posicion)
            return

        actual = raiz
        while True:
            nodo = self._leer_nodo(archivo, actual)
            if id_asada < nodo.id_Asada:
                if nodo.pos_izquierdo == NodoArbol.NULO:
                    posicion = self._anexar_nodo(archivo, nuevo)
                    self._actualizar_puntero(archivo, actual, True, posicion)
                    return
                actual = nodo.pos_izquierdo
            elif id_asada > nodo.id_Asada:
                if nodo.pos_derecho == NodoArbol.NULO:
                    posicion = self._anexar_nodo(archivo, nuevo)
                    self._actualizar_puntero(archivo, actual, False, posicion)
                    return
                actual = nodo.pos_derecho
            else:
                # Llave duplicada: se actualiza la posición física del registro.
                archivo.seek(actual + 8)
                archivo.write(struct.pack("<q", posicion_registro))
                return

    def insertar(self, id_asada: int, posicion_registro: int) -> None:
        """Inserta o actualiza una entrada del índice y la persiste.

        Invalida la caché en memoria para forzar su recarga en la próxima
        búsqueda en memoria.

        :param id_asada: Llave de la ASADA.
        :param posicion_registro: Posición física del registro en el archivo
            principal.
        """
        with open(self.ruta, "r+b") as archivo:
            self._insertar_en(archivo, id_asada, posicion_registro)
        self._en_memoria = False
        self._raiz_memoria = None

    def reconstruir(self, pares: Iterable[Tuple[int, int]]) -> None:
        """Reconstruye el índice completo a partir de pares (id, posición).

        Reinicia el archivo y reinserta todas las llaves en orden
        mediano-primero para producir un árbol balanceado. Las llaves
        duplicadas conservan la última posición indicada.

        :param pares: Iterable de tuplas ``(id_Asada, posicion_registro)``.
        """
        # Deduplica por id_Asada conservando la última aparición y ordena.
        mapa: Dict[int, int] = {}
        for id_asada, posicion in pares:
            mapa[id_asada] = posicion
        ordenados: List[Tuple[int, int]] = sorted(mapa.items())

        self._inicializar_archivo()
        with open(self.ruta, "r+b") as archivo:
            # Inserción mediano-primero mediante una pila de rangos [lo, hi].
            pila: List[Tuple[int, int]] = [(0, len(ordenados) - 1)]
            while pila:
                lo, hi = pila.pop()
                if lo > hi:
                    continue
                medio = (lo + hi) // 2
                id_asada, posicion = ordenados[medio]
                self._insertar_en(archivo, id_asada, posicion)
                pila.append((lo, medio - 1))
                pila.append((medio + 1, hi))

        self._en_memoria = False
        self._raiz_memoria = None

    # ------------------------------------------------------------------ #
    # Búsqueda                                                            #
    # ------------------------------------------------------------------ #
    def buscar_en_disco(self, id_asada: int) -> Optional[int]:
        """Busca una llave recorriendo el árbol directamente sobre el disco.

        :param id_asada: Llave a buscar.
        :returns: La posición física del registro, o ``None`` si no existe.
        """
        with open(self.ruta, "rb") as archivo:
            actual = self._leer_raiz(archivo)
            while actual != NodoArbol.NULO:
                nodo = self._leer_nodo(archivo, actual)
                if id_asada == nodo.id_Asada:
                    return nodo.posicion_registro
                actual = nodo.pos_izquierdo if id_asada < nodo.id_Asada else nodo.pos_derecho
        return None

    def cargar_en_memoria(self) -> None:
        """Carga el árbol completo a memoria siguiendo sus punteros lógicos.

        Reconstruye en RAM un árbol de :class:`_NodoMemoria` equivalente al del
        disco, de modo que las búsquedas posteriores no toquen el archivo. Se
        recorre el árbol de forma iterativa para no depender del límite de
        recursión de Python.
        """
        with open(self.ruta, "rb") as archivo:
            raiz_pos = self._leer_raiz(archivo)
            if raiz_pos == NodoArbol.NULO:
                self._raiz_memoria = None
                self._en_memoria = True
                return

            nodo_disco = self._leer_nodo(archivo, raiz_pos)
            self._raiz_memoria = _NodoMemoria(
                nodo_disco.id_Asada, nodo_disco.posicion_registro
            )
            # Pila de (posición_en_disco, nodo_en_memoria_correspondiente).
            pila: List[Tuple[NodoArbol, _NodoMemoria]] = [(nodo_disco, self._raiz_memoria)]
            while pila:
                nodo_d, nodo_m = pila.pop()
                if nodo_d.pos_izquierdo != NodoArbol.NULO:
                    hijo_d = self._leer_nodo(archivo, nodo_d.pos_izquierdo)
                    nodo_m.izquierdo = _NodoMemoria(hijo_d.id_Asada, hijo_d.posicion_registro)
                    pila.append((hijo_d, nodo_m.izquierdo))
                if nodo_d.pos_derecho != NodoArbol.NULO:
                    hijo_d = self._leer_nodo(archivo, nodo_d.pos_derecho)
                    nodo_m.derecho = _NodoMemoria(hijo_d.id_Asada, hijo_d.posicion_registro)
                    pila.append((hijo_d, nodo_m.derecho))

        self._en_memoria = True

    def buscar(self, id_asada: int) -> Optional[int]:
        """Busca una llave usando el árbol en memoria (carga perezosa).

        Si el árbol aún no se ha cargado en memoria, lo carga automáticamente.
        Es el método de búsqueda recomendado en tiempo de ejecución por su
        rapidez (no realiza accesos a disco tras la carga inicial).

        :param id_asada: Llave a buscar.
        :returns: La posición física del registro, o ``None`` si no existe.
        """
        if not self._en_memoria:
            self.cargar_en_memoria()

        actual = self._raiz_memoria
        while actual is not None:
            if id_asada == actual.id_Asada:
                return actual.posicion_registro
            actual = actual.izquierdo if id_asada < actual.id_Asada else actual.derecho
        return None

    def cantidad_nodos(self) -> int:
        """Devuelve la cantidad de nodos almacenados en el índice.

        :returns: Número de nodos (tamaño útil del archivo / tamaño de nodo).
        """
        bytes_nodos = os.path.getsize(self.ruta) - self._TAMANO_CABECERA
        return max(0, bytes_nodos) // NodoArbol.TAMANO
