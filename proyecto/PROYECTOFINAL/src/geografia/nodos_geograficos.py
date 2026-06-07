"""
Nodos de la estructura geográfica jerárquica (Dev B).

La estructura es una **lista enlazada jerárquica de 4 niveles**:

    provincia → cantón → distrito → ASADAs

Cada nivel es una lista enlazada de "hermanos" (campo ``siguiente``) y apunta
al primer nodo del nivel inferior (campo ``primer_*``). Es la representación
clásica *primer-hijo / siguiente-hermano*, pero con un tipo de nodo por nivel
para que el código sea legible y el árbol de combos del GUI salga natural.

En MEMORIA los enlaces son referencias a objetos (``siguiente``, ``primer_*``).
Cuando se persista en el archivo binario (paso 6 del plan), esas referencias se
reemplazan por **punteros lógicos**: la posición (offset entero) del nodo
destino dentro del archivo ``data/indice_geografico.dat``. Por eso cada
``NodoAsadaGeo`` ya guarda ``posicion_registro``: el puntero lógico hacia el
**archivo principal** de Dev A (no a este índice), que es lo que permite, dado
un distrito, ir a leer el registro completo de cada ASADA sin duplicar datos.
"""

from __future__ import annotations

from typing import Optional


class NodoAsadaGeo:
    """Hoja del árbol: una ASADA dentro de un distrito."""

    def __init__(self, id_asada: str, posicion_registro: int) -> None:
        self.id_asada: str = id_asada
        # Puntero lógico al archivo PRINCIPAL de Dev A (posición del registro).
        self.posicion_registro: int = posicion_registro
        # Siguiente ASADA del mismo distrito.
        self.siguiente: Optional["NodoAsadaGeo"] = None


class NodoDistrito:
    """Tercer nivel: un distrito, cabeza de su lista de ASADAs."""

    def __init__(self, nombre: str) -> None:
        self.nombre: str = nombre
        self.primer_asada: Optional[NodoAsadaGeo] = None
        self.siguiente: Optional["NodoDistrito"] = None


class NodoCanton:
    """Segundo nivel: un cantón, cabeza de su lista de distritos."""

    def __init__(self, nombre: str) -> None:
        self.nombre: str = nombre
        self.primer_distrito: Optional[NodoDistrito] = None
        self.siguiente: Optional["NodoCanton"] = None


class NodoProvincia:
    """Primer nivel: una provincia, cabeza de su lista de cantones."""

    def __init__(self, nombre: str) -> None:
        self.nombre: str = nombre
        self.primer_canton: Optional[NodoCanton] = None
        self.siguiente: Optional["NodoProvincia"] = None
