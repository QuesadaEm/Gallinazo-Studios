"""API pública de consulta (capa de aplicación / fachada).

Implementa :class:`MotorConsulta`, el **único punto de entrada** que el
servidor de sockets del Desarrollador B debe utilizar. Oculta los detalles de
las capas inferiores (ingesta, persistencia e indexación) detrás de una
interfaz estable y sencilla.

Concurrencia
------------
Tras :meth:`MotorConsulta.iniciar`, el índice queda cargado en memoria y el
archivo de registros se consulta abriendo un descriptor por lectura, por lo que
las operaciones de consulta son seguras para ser invocadas desde múltiples
hilos de solo lectura. La operación de escritura :meth:`actualizar_datos` debe
ejecutarse únicamente desde el equipo central y no de forma concurrente con
ella misma.
"""

from __future__ import annotations

import os
import threading
from typing import List, Optional

from src.ingesta.actualizador import ActualizadorIncremental, GanchoRegeneracion
from src.ingesta.cliente_aresep import URL_ARESEP, ClienteAresep
from src.modelo.asada import Asada
from src.persistencia.indice_arbol import IndiceArbolBinario
from src.persistencia.repositorio_binario import RepositorioBinario


class MotorConsulta:
    """Fachada de consulta del motor de persistencia e indexación.

    :ivar repositorio: Repositorio binario principal.
    :ivar indice: Índice de árbol binario por ``id_Asada``.
    :ivar actualizador: Mecanismo de actualización incremental.
    """

    def __init__(
        self,
        directorio_datos: str = "data",
        url_endpoint: str = URL_ARESEP,
        origen_local: Optional[str] = None,
        al_regenerar: Optional[GanchoRegeneracion] = None,
    ) -> None:
        """Configura el motor con sus rutas y dependencias.

        :param directorio_datos: Carpeta donde residen los archivos binarios.
        :param url_endpoint: URL del endpoint REST de ARESEP.
        :param origen_local: Archivo JSON local para operar sin conexión.
        :param al_regenerar: Callback que el Desarrollador B usa para
            reconstruir el índice geográfico tras una actualización.
        """
        os.makedirs(directorio_datos, exist_ok=True)
        ruta_registros      = os.path.join(directorio_datos, "registros.dat")
        ruta_indice         = os.path.join(directorio_datos, "indice_arbol.dat")
        ruta_metadata       = os.path.join(directorio_datos, "metadata_sync.json")
        # Tercer archivo binario: índice geográfico con listas enlazadas.
        self.ruta_indice_geo: str = os.path.join(directorio_datos, "indice_geografico.dat")

        self.repositorio: RepositorioBinario = RepositorioBinario(ruta_registros)
        self.indice: IndiceArbolBinario = IndiceArbolBinario(ruta_indice)
        cliente = ClienteAresep(url=url_endpoint, origen_local=origen_local)
        self.actualizador: ActualizadorIncremental = ActualizadorIncremental(
            cliente=cliente,
            repositorio=self.repositorio,
            indice=self.indice,
            ruta_metadata=ruta_metadata,
            al_regenerar=al_regenerar,
        )
        self._candado_actualizacion = threading.Lock()

    # ------------------------------------------------------------------ #
    # Ciclo de vida                                                       #
    # ------------------------------------------------------------------ #
    def iniciar(self, sincronizar_si_vacio: bool = True) -> None:
        """Prepara el motor para atender consultas.

        Carga el índice en memoria. Si no existen registros y
        ``sincronizar_si_vacio`` es ``True``, intenta una primera
        sincronización con ARESEP.

        :param sincronizar_si_vacio: Si debe descargar datos cuando el
            repositorio está vacío.
        """
        if sincronizar_si_vacio and self.repositorio.cantidad_registros() == 0:
            self.actualizar_datos()
        else:
            self.indice.cargar_en_memoria()

    # ------------------------------------------------------------------ #
    # API pública de consulta                                             #
    # ------------------------------------------------------------------ #
    def buscar_por_id(self, id_asada: int) -> Optional[int]:
        """Busca una ASADA por su identificador y devuelve su posición física.

        :param id_asada: Identificador de la ASADA.
        :returns: La posición física del registro en el archivo principal, o
            ``None`` si la ASADA no existe.
        """
        return self.indice.buscar(id_asada)

    def obtener_asada(self, id_asada: int) -> Optional[Asada]:
        """Obtiene el registro completo de una ASADA por su identificador.

        :param id_asada: Identificador de la ASADA.
        :returns: La :class:`Asada` correspondiente, o ``None`` si no existe.
        """
        posicion = self.buscar_por_id(id_asada)
        if posicion is None:
            return None
        return self.repositorio.leer_registro(posicion)

    def obtener_todas(self) -> List[Asada]:
        """Devuelve todas las ASADAS almacenadas en el repositorio.

        :returns: Lista con todas las :class:`Asada` (en orden físico).
        """
        return list(self.repositorio.recorrer_todos())

    def actualizar_datos(self, forzar: bool = False) -> bool:
        """Ejecuta la actualización incremental contra ARESEP.

        Es una operación de escritura: se serializa con un candado para evitar
        regeneraciones simultáneas. Solo debe invocarse desde el equipo central.

        :param forzar: Si es ``True``, regenera aunque no haya cambios remotos.
        :returns: ``True`` si los datos se regeneraron; ``False`` si ya estaban
            al día.
        """
        with self._candado_actualizacion:
            return self.actualizador.sincronizar(forzar=forzar)
