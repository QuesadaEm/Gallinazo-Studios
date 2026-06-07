"""
IndiceGeografico — estructura jerárquica provincia→cantón→distrito→ASADAs.

Estructura de datos central del sistema. Vive en MEMORIA (construida a partir
del repositorio principal) y se persiste en el tercer archivo binario del
sistema (``data/indice_geografico.dat``) mediante punteros lógicos gracias a
:class:`~src.persistencia.indice_geografico_binario.IndiceGeograficoBinario`.

Las listas de hermanos se mantienen ordenadas alfabéticamente para que los
combos dependientes del GUI salgan ordenados sin trabajo extra.

INTEGRACIÓN:
    ``construir(repositorio)`` recorre el ``RepositorioBinario`` principal.
    Como los registros son de tamaño fijo, la posición de cada ASADA se calcula
    como ``índice * TAMANO_REGISTRO``. Esa posición es el puntero lógico que el
    servidor usa con ``repositorio.leer_registro(posicion)``.

    El actualizador invoca esto a través del callback ``al_regenerar(repo)``
    configurado en ``MotorConsulta``. Tras construir, se llama a
    ``persistir(ruta)`` para dejar el tercer archivo binario actualizado.
"""

from __future__ import annotations

import os
from typing import Iterable, List, Optional, Tuple

from src.geografia.nodos_geograficos import (
    NodoAsadaGeo,
    NodoCanton,
    NodoDistrito,
    NodoProvincia,
)
from src.modelo.asada import Asada


class IndiceGeografico:
    """Índice jerárquico de ASADAS por división política.

    La estructura vive en RAM y se construye leyendo el repositorio binario
    principal. Opcionalmente se persiste en ``data/indice_geografico.dat``
    mediante :meth:`persistir` y se restaura desde ese archivo con
    :meth:`cargar_desde_binario`, evitando reconstruir desde el repositorio
    principal en arranques subsecuentes.

    :ivar primera_provincia: Cabeza de la lista enlazada de provincias.
    """

    def __init__(self) -> None:
        self.primera_provincia: Optional[NodoProvincia] = None

    # ------------------------------------------------------------------ #
    # Construcción                                                        #
    # ------------------------------------------------------------------ #
    def construir(self, repositorio) -> "IndiceGeografico":
        """Reconstruye el índice completo desde el repositorio principal de A.

        :param repositorio: ``RepositorioBinario`` (o mock) cuyo
            ``recorrer_todos()`` produce objetos ``Asada`` en orden físico.
        :returns: ``self`` (para encadenar).
        """
        self.primera_provincia = None
        # Tamaño fijo de registro -> posición = índice * TAMANO_REGISTRO.
        tam = getattr(repositorio, "TAMANO_REGISTRO", 1)
        for indice, asada in enumerate(repositorio.recorrer_todos()):
            self.insertar(asada, indice * tam)
        return self

    def insertar(self, asada: Asada, posicion_registro: int) -> None:
        """Ubica una ASADA en su provincia/cantón/distrito, creándolos si faltan."""
        provincia = self._obtener_o_crear_provincia(asada.provincia)
        canton = self._obtener_o_crear_canton(provincia, asada.canton)
        distrito = self._obtener_o_crear_distrito(canton, asada.distrito)
        self._agregar_asada(distrito, asada.id_Asada, posicion_registro)

    # ------------------------------------------------------------------ #
    # Inserción ordenada en las listas enlazadas                          #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _insertar_ordenado(cabeza, nodo, nombre_attr: str = "nombre"):
        """Inserta `nodo` en una lista de hermanos manteniéndola ordenada.

        Devuelve la (posiblemente nueva) cabeza de la lista.
        """
        clave = getattr(nodo, nombre_attr).lower()
        if cabeza is None or getattr(cabeza, nombre_attr).lower() > clave:
            nodo.siguiente = cabeza
            return nodo
        actual = cabeza
        while actual.siguiente is not None and getattr(actual.siguiente, nombre_attr).lower() <= clave:
            actual = actual.siguiente
        nodo.siguiente = actual.siguiente
        actual.siguiente = nodo
        return cabeza

    def _obtener_o_crear_provincia(self, nombre: str) -> NodoProvincia:
        actual = self.primera_provincia
        while actual is not None:
            if actual.nombre == nombre:
                return actual
            actual = actual.siguiente
        nuevo = NodoProvincia(nombre)
        self.primera_provincia = self._insertar_ordenado(self.primera_provincia, nuevo)
        return nuevo

    def _obtener_o_crear_canton(self, provincia: NodoProvincia, nombre: str) -> NodoCanton:
        actual = provincia.primer_canton
        while actual is not None:
            if actual.nombre == nombre:
                return actual
            actual = actual.siguiente
        nuevo = NodoCanton(nombre)
        provincia.primer_canton = self._insertar_ordenado(provincia.primer_canton, nuevo)
        return nuevo

    def _obtener_o_crear_distrito(self, canton: NodoCanton, nombre: str) -> NodoDistrito:
        actual = canton.primer_distrito
        while actual is not None:
            if actual.nombre == nombre:
                return actual
            actual = actual.siguiente
        nuevo = NodoDistrito(nombre)
        canton.primer_distrito = self._insertar_ordenado(canton.primer_distrito, nuevo)
        return nuevo

    @staticmethod
    def _agregar_asada(distrito: NodoDistrito, id_asada: int, posicion_registro: int) -> None:
        # Evita duplicar la misma ASADA si se reconstruye dos veces.
        actual = distrito.primer_asada
        while actual is not None:
            if actual.id_asada == id_asada:
                actual.posicion_registro = posicion_registro
                return
            actual = actual.siguiente
        nodo = NodoAsadaGeo(id_asada, posicion_registro)
        nodo.siguiente = distrito.primer_asada
        distrito.primer_asada = nodo

    # ------------------------------------------------------------------ #
    # Consultas (alimentan los combos dependientes del GUI)               #
    # ------------------------------------------------------------------ #
    def provincias(self) -> List[str]:
        """Lista de nombres de provincia, en orden alfabético."""
        return [p.nombre for p in self._recorrer(self.primera_provincia)]

    def cantones_de(self, provincia: str) -> List[str]:
        """Cantones de una provincia."""
        nodo = self._buscar(self.primera_provincia, provincia)
        if nodo is None:
            return []
        return [c.nombre for c in self._recorrer(nodo.primer_canton)]

    def distritos_de(self, provincia: str, canton: str) -> List[str]:
        """Distritos de un cantón dentro de una provincia.

        Se exige la provincia porque los nombres de cantón se repiten entre
        provincias (p. ej. 'Central'), así que filtrar solo por cantón daría
        resultados incorrectos en los combos dependientes.
        """
        nodo_prov = self._buscar(self.primera_provincia, provincia)
        if nodo_prov is None:
            return []
        nodo_cant = self._buscar(nodo_prov.primer_canton, canton)
        if nodo_cant is None:
            return []
        return [d.nombre for d in self._recorrer(nodo_cant.primer_distrito)]

    def asadas_de(self, provincia: str, canton: str, distrito: str) -> List[Tuple[int, int]]:
        """ASADAS de un distrito, como pares ``(id_Asada, posicion_registro)``.

        La posición es el puntero lógico al archivo principal de Dev A; con ella
        el servidor lee el registro completo (``repositorio.leer_registro``).
        """
        nodo_prov = self._buscar(self.primera_provincia, provincia)
        if nodo_prov is None:
            return []
        nodo_cant = self._buscar(nodo_prov.primer_canton, canton)
        if nodo_cant is None:
            return []
        nodo_dist = self._buscar(nodo_cant.primer_distrito, distrito)
        if nodo_dist is None:
            return []
        resultado = []
        asada = nodo_dist.primer_asada
        while asada is not None:
            resultado.append((asada.id_asada, asada.posicion_registro))
            asada = asada.siguiente
        return resultado

    def total_asadas(self) -> int:
        """Cantidad total de ASADAS indexadas (útil para pruebas y diagnóstico)."""
        total = 0
        for p in self._recorrer(self.primera_provincia):
            for c in self._recorrer(p.primer_canton):
                for d in self._recorrer(c.primer_distrito):
                    a = d.primer_asada
                    while a is not None:
                        total += 1
                        a = a.siguiente
        return total

    # ------------------------------------------------------------------ #
    # Persistencia binaria (tercer archivo binario del sistema)           #
    # ------------------------------------------------------------------ #

    def persistir(self, ruta: str) -> None:
        """Serializa la estructura jerárquica en el tercer archivo binario.

        Delega en :class:`~src.persistencia.indice_geografico_binario.IndiceGeograficoBinario`
        para escribir ``data/indice_geografico.dat`` con punteros lógicos. Se
        invoca automáticamente al final de :meth:`construir` si se pasa
        ``ruta_binario``.

        :param ruta: Ruta del archivo de salida (p. ej. ``data/indice_geografico.dat``).
        """
        # Importación diferida para evitar dependencia circular en módulos
        # que solo usan IndiceGeografico en modo RAM.
        from src.persistencia.indice_geografico_binario import IndiceGeograficoBinario
        IndiceGeograficoBinario(ruta).serializar(self.primera_provincia)

    def cargar_desde_binario(self, ruta: str) -> bool:
        """Restaura la estructura desde el tercer archivo binario.

        Si el archivo existe y contiene datos, sustituye la estructura en
        memoria con la reconstruida desde el archivo, evitando recorrer el
        repositorio principal. Es el camino rápido de arranque cuando los
        datos ya están sincronizados.

        :param ruta: Ruta del archivo binario del índice geográfico.
        :returns: ``True`` si la carga fue exitosa; ``False`` si el archivo
            no existe o está vacío.
        """
        from src.persistencia.indice_geografico_binario import IndiceGeograficoBinario
        binario = IndiceGeograficoBinario(ruta)
        if not binario.existe():
            return False
        primera = binario.deserializar()
        if primera is None:
            return False
        self.primera_provincia = primera
        return True

    # ------------------------------------------------------------------ #
    # Utilidades internas                                                 #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _recorrer(cabeza):
        """Itera una lista de hermanos enlazada por ``siguiente``."""
        actual = cabeza
        while actual is not None:
            yield actual
            actual = actual.siguiente

    @staticmethod
    def _buscar(cabeza, nombre: str):
        """Busca un nodo por nombre en una lista de hermanos."""
        actual = cabeza
        while actual is not None:
            if actual.nombre == nombre:
                return actual
            actual = actual.siguiente
        return None


# ---------------------------------------------------------------------- #
# Mock de repositorio para desarrollar/probar sin archivos binarios       #
# ---------------------------------------------------------------------- #
class RepositorioMock:
    """Repositorio falso en memoria con la MISMA interfaz que usa Dev B.

    Imita a ``RepositorioBinario``: ``recorrer_todos()`` entrega objetos
    ``Asada`` y expone ``TAMANO_REGISTRO`` (aquí 1, para que las posiciones
    sean 0, 1, 2, ... y se lean fácil en las pruebas).
    """

    TAMANO_REGISTRO = 1

    def __init__(self, asadas: Iterable[Asada]) -> None:
        self._asadas: List[Asada] = list(asadas)

    def recorrer_todos(self):
        return iter(self._asadas)

    def leer_registro(self, posicion: int) -> Asada:
        return self._asadas[posicion]


if __name__ == "__main__":
    # Demo autosuficiente con datos de ejemplo (formato del modelo de Dev A).
    datos = [
        Asada(id_Asada=1790, provincia="Alajuela", canton="San Carlos", distrito="Pital", operador="ASADA Cuestillas", coordenadaX=490866.06, coordenadaY=1098368.55),
        Asada(id_Asada=205, provincia="Alajuela", canton="San Carlos", distrito="La Fortuna", operador="ASADA La Fortuna", coordenadaX=470000.0, coordenadaY=1145000.0),
        Asada(id_Asada=311, provincia="Alajuela", canton="San Carlos", distrito="Aguas Zarcas", operador="ASADA Aguas Zarcas", coordenadaX=480000.0, coordenadaY=1150000.0),
        Asada(id_Asada=42, provincia="San José", canton="Curridabat", distrito="Tirrases", operador="ASADA Tirrases", coordenadaX=500000.0, coordenadaY=1095000.0),
    ]
    indice = IndiceGeografico().construir(RepositorioMock(datos))
    print("Total ASADAS:", indice.total_asadas())
    print("Provincias:", indice.provincias())
    print("Cantones de Alajuela:", indice.cantones_de("Alajuela"))
    print("Distritos de Alajuela > San Carlos:", indice.distritos_de("Alajuela", "San Carlos"))
    print("ASADAS de ...San Carlos > Pital:", indice.asadas_de("Alajuela", "San Carlos", "Pital"))
