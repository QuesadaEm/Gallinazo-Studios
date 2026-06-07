"""Actualización incremental de la información (capa de ingesta).

Implementa :class:`ActualizadorIncremental`, que verifica si los datos remotos
de ARESEP cambiaron desde la última sincronización y, de ser así, **regenera
por completo** el archivo principal de registros y el índice de árbol binario.

La detección de cambios se basa en una huella SHA-256 del contenido remoto
(complementada con la cabecera ``Last-Modified`` cuando ARESEP la entrega), lo
que es robusto aun si el servicio no expone una fecha de modificación fiable.

Para no acoplar este módulo con la estructura geográfica del Desarrollador B,
la regeneración admite un *callback* opcional (``al_regenerar``) que recibe el
repositorio ya actualizado; el equipo lo usa para que el actualizador dispare
la reconstrucción del índice geográfico y se mantenga la consistencia de los
tres archivos.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Callable, List, Optional

from src.ingesta.cliente_aresep import ClienteAresep
from src.modelo.asada import Asada
from src.persistencia.indice_arbol import IndiceArbolBinario
from src.persistencia.repositorio_binario import RepositorioBinario

#: Firma del callback que se invoca tras regenerar los datos base.
GanchoRegeneracion = Callable[[RepositorioBinario], None]


class ActualizadorIncremental:
    """Sincroniza las estructuras locales con los datos remotos de ARESEP.

    :ivar cliente: Cliente para descargar datos de ARESEP.
    :ivar repositorio: Repositorio binario principal a regenerar.
    :ivar indice: Índice de árbol binario a reconstruir.
    :ivar ruta_metadata: Archivo JSON con el estado de la última sincronización.
    """

    def __init__(
        self,
        cliente: ClienteAresep,
        repositorio: RepositorioBinario,
        indice: IndiceArbolBinario,
        ruta_metadata: str,
        al_regenerar: Optional[GanchoRegeneracion] = None,
    ) -> None:
        """Inicializa el actualizador.

        :param cliente: Cliente de ARESEP.
        :param repositorio: Repositorio binario principal.
        :param indice: Índice de árbol binario.
        :param ruta_metadata: Ruta del archivo de metadatos de sincronización.
        :param al_regenerar: Callback opcional invocado tras regenerar los
            datos base (lo usa el Desarrollador B para reconstruir el índice
            geográfico).
        """
        self.cliente: ClienteAresep = cliente
        self.repositorio: RepositorioBinario = repositorio
        self.indice: IndiceArbolBinario = indice
        self.ruta_metadata: str = ruta_metadata
        self._al_regenerar: Optional[GanchoRegeneracion] = al_regenerar

    # ------------------------------------------------------------------ #
    # Estado de sincronización                                            #
    # ------------------------------------------------------------------ #
    def _cargar_metadata_local(self) -> Optional[dict]:
        """Lee el archivo de metadatos local, si existe.

        :returns: Diccionario con el estado guardado, o ``None``.
        """
        if not os.path.exists(self.ruta_metadata):
            return None
        try:
            with open(self.ruta_metadata, "r", encoding="utf-8") as archivo:
                return json.load(archivo)
        except (json.JSONDecodeError, OSError):
            return None

    def _guardar_metadata_local(self, huella: str, cantidad: int, last_modified: Optional[str], fecha_modificacion: Optional[str] = None) -> None:
        """Persiste el estado de la sincronización actual.

        :param huella: Huella SHA-256 del contenido sincronizado.
        :param cantidad: Cantidad de registros sincronizados.
        :param last_modified: Cabecera ``Last-Modified`` remota, si la hubo.
        :param fecha_modificacion: Fecha oficial ``metadata.date`` de ARESEP.
        """
        directorio = os.path.dirname(os.path.abspath(self.ruta_metadata))
        os.makedirs(directorio, exist_ok=True)
        estado = {
            "huella": huella,
            "fecha_modificacion": fecha_modificacion,
            "cantidad_registros": cantidad,
            "last_modified_remoto": last_modified,
            "ultima_sincronizacion": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.ruta_metadata, "w", encoding="utf-8") as archivo:
            json.dump(estado, archivo, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    # Detección de cambios                                                #
    # ------------------------------------------------------------------ #
    def hay_cambios(self, crudo: Optional[bytes] = None) -> bool:
        """Indica si los datos remotos difieren de la última sincronización.

        Usa como señal primaria la **fecha de modificación oficial**
        (``metadata.date`` de ARESEP) y, como respaldo robusto, la **huella
        SHA-256** del contenido. Hay cambios si nunca se sincronizó, si la fecha
        oficial cambió, o si la huella cambió.

        :param crudo: Contenido remoto ya descargado; si es ``None``, se
            descarga internamente.
        :returns: ``True`` si corresponde regenerar las estructuras.
        """
        if crudo is None:
            crudo = self.cliente.descargar_crudo()
        huella_remota = self.cliente.calcular_huella(crudo)
        fecha_remota = self.cliente.obtener_fecha_modificacion(crudo)
        metadata = self._cargar_metadata_local()
        if metadata is None:
            return True
        fecha_cambio = (
            fecha_remota is not None
            and metadata.get("fecha_modificacion") != fecha_remota
        )
        huella_cambio = metadata.get("huella") != huella_remota
        return fecha_cambio or huella_cambio

    # ------------------------------------------------------------------ #
    # Regeneración                                                        #
    # ------------------------------------------------------------------ #
    def regenerar_todo(self, asadas: Optional[List[Asada]] = None, crudo: Optional[bytes] = None) -> int:
        """Regenera el archivo principal y el índice de árbol binario.

        Reescribe el repositorio completo y reconstruye el índice de forma
        balanceada. Si se configuró ``al_regenerar``, se invoca al final para
        que la estructura geográfica también se reconstruya y los tres archivos
        queden consistentes.

        :param asadas: Lista de ASADAS a persistir; si es ``None`` se descargan.
        :param crudo: Contenido remoto crudo, para calcular la huella; si es
            ``None`` y se descargan los datos, se obtiene en el proceso.
        :returns: Cantidad de registros regenerados.
        """
        if asadas is None:
            if crudo is None:
                crudo = self.cliente.descargar_crudo()
            asadas = self.cliente.parsear(crudo)

        pares = self.repositorio.reescribir(asadas)
        self.indice.reconstruir(pares)
        self.indice.cargar_en_memoria()

        if self._al_regenerar is not None:
            self._al_regenerar(self.repositorio)

        huella = self.cliente.calcular_huella(crudo) if crudo is not None else ""
        last_modified = getattr(self.cliente, "_ultimo_last_modified", None)
        fecha_modificacion = (
            self.cliente.obtener_fecha_modificacion(crudo) if crudo is not None else None
        )
        if huella:
            self._guardar_metadata_local(huella, len(asadas), last_modified, fecha_modificacion)
        return len(asadas)

    def sincronizar(self, forzar: bool = False) -> bool:
        """Descarga una vez y regenera solo si hay cambios.

        Es el punto de entrada recomendado: descarga el contenido remoto una
        única vez, decide si hay cambios y, en caso afirmativo (o si se
        ``forzar``), regenera todas las estructuras.

        :param forzar: Si es ``True``, regenera aunque no haya cambios.
        :returns: ``True`` si se regeneraron los datos; ``False`` si ya estaban
            actualizados.
        """
        crudo = self.cliente.descargar_crudo()
        if not forzar and not self.hay_cambios(crudo):
            return False
        asadas = self.cliente.parsear(crudo)
        self.regenerar_todo(asadas=asadas, crudo=crudo)
        return True
