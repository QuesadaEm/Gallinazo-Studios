"""Cliente del endpoint REST de ARESEP (capa de ingesta).

Implementa :class:`ClienteAresep`, responsable de descargar el JSON de datos
abiertos de ARESEP, calcular una huella para detectar cambios y convertir la
respuesta en objetos :class:`~src.modelo.asada.Asada`.

El servicio de ARESEP responde en formato **OData v4**: un objeto JSON con las
llaves ``metadata`` y ``value``, donde ``value`` contiene la lista de ASADAS.
:meth:`ClienteAresep.parsear` extrae esa lista y también contempla, por
robustez, los formatos de arreglo directo y de envoltorio ``"d"`` (WCF antiguo).

Para facilitar las pruebas y el desarrollo sin conexión, el cliente acepta un
``origen_local``: si se indica, lee el JSON desde un archivo en disco en lugar
de realizar la petición HTTP.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

try:  # ``requests`` es opcional cuando solo se usa el modo sin conexión.
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

from src.modelo.asada import Asada

#: Endpoint oficial de datos abiertos de ARESEP para ubicación de ASADAS.
URL_ARESEP: str = (
    "https://datos.aresep.go.cr/ws.datosabiertos/Services/IA/"
    "Asadas.svc/ObtenerInformacionUbicacionAsadas"
)


@dataclass(frozen=True)
class MetadataRemota:
    """Metadatos asociados a una descarga, usados para la sincronización.

    :ivar huella: Hash SHA-256 del contenido crudo descargado.
    :ivar fecha: Marca de tiempo (UTC) en que se obtuvieron los datos.
    :ivar fecha_modificacion: Fecha de modificación oficial que ARESEP publica
        en ``metadata.date``; ``None`` si no viene.
    :ivar last_modified: Cabecera ``Last-Modified`` remota, si el servidor la
        proporciona; ``None`` en caso contrario.
    :ivar cantidad: Cantidad de registros descargados.
    """

    huella: str
    fecha: str
    fecha_modificacion: Optional[str]
    last_modified: Optional[str]
    cantidad: int


class ClienteAresep:
    """Descarga y parsea la información de ASADAS desde ARESEP.

    :ivar url: URL del endpoint REST.
    :ivar tiempo_espera: Tiempo máximo de espera de la petición (segundos).
    :ivar origen_local: Ruta a un archivo JSON local para uso sin conexión.
    """

    def __init__(
        self,
        url: str = URL_ARESEP,
        tiempo_espera: float = 30.0,
        origen_local: Optional[str] = None,
    ) -> None:
        """Inicializa el cliente.

        :param url: URL del endpoint REST de ARESEP.
        :param tiempo_espera: Tiempo máximo de espera por la respuesta HTTP.
        :param origen_local: Si se indica, los datos se leen de este archivo en
            vez de realizar la petición HTTP (útil para pruebas y desarrollo).
        """
        self.url: str = url
        self.tiempo_espera: float = tiempo_espera
        self.origen_local: Optional[str] = origen_local
        self._ultimo_last_modified: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Descarga                                                            #
    # ------------------------------------------------------------------ #
    def descargar_crudo(self) -> bytes:
        """Descarga la respuesta cruda del endpoint (o del archivo local).

        :returns: Contenido de la respuesta en bytes.
        :raises RuntimeError: Si la descarga falla o ``requests`` no está
            disponible en modo en línea.
        """
        if self.origen_local is not None:
            with open(self.origen_local, "rb") as archivo:
                return archivo.read()

        if requests is None:  # pragma: no cover
            raise RuntimeError(
                "La librería 'requests' no está instalada y no se indicó "
                "'origen_local'. Instale requests o use el modo sin conexión."
            )

        try:
            respuesta = requests.get(self.url, timeout=self.tiempo_espera)
            respuesta.raise_for_status()
        except requests.RequestException as error:  # pragma: no cover
            raise RuntimeError(f"Error al descargar datos de ARESEP: {error}") from error

        self._ultimo_last_modified = respuesta.headers.get("Last-Modified")
        return respuesta.content

    # ------------------------------------------------------------------ #
    # Parseo                                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extraer_lista(documento: Any) -> List[dict]:
        """Obtiene la lista de registros sin importar el envoltorio del JSON.

        :param documento: Estructura ya deserializada del JSON.
        :returns: Lista de diccionarios, cada uno una ASADA cruda.
        :raises ValueError: Si no se encuentra una lista de registros.
        """
        if isinstance(documento, list):
            return documento
        if isinstance(documento, dict):
            # ARESEP responde en formato OData v4: la lista va en "value".
            if isinstance(documento.get("value"), list):
                return documento["value"]
            # Algunos servicios WCF antiguos envuelven en "d".
            if isinstance(documento.get("d"), list):
                return documento["d"]
            # Último recurso: la primera lista que aparezca en el objeto.
            for valor in documento.values():
                if isinstance(valor, list):
                    return valor
        raise ValueError("La respuesta de ARESEP no contiene una lista de registros.")

    def parsear(self, crudo: bytes) -> List[Asada]:
        """Convierte la respuesta cruda en una lista de :class:`Asada`.

        :param crudo: Contenido en bytes devuelto por :meth:`descargar_crudo`.
        :returns: Lista de ASADAS construidas desde el JSON.
        :raises ValueError: Si el contenido no es JSON válido o no trae lista.
        """
        try:
            documento = json.loads(crudo.decode("utf-8", errors="ignore"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Respuesta JSON inválida de ARESEP: {error}") from error
        registros = self._extraer_lista(documento)
        return [Asada.desde_dict(registro) for registro in registros]

    @staticmethod
    def _extraer_metadata(documento: Any) -> dict:
        """Devuelve el objeto ``metadata`` del JSON (vacío si no existe)."""
        if isinstance(documento, dict) and isinstance(documento.get("metadata"), dict):
            return documento["metadata"]
        return {}

    def obtener_fecha_modificacion(self, crudo: bytes) -> Optional[str]:
        """Extrae la fecha de modificación oficial publicada por ARESEP.

        ARESEP la entrega en ``metadata.date`` (p. ej.
        ``"2019-11-12T14:15:53.000"``). Es la señal preferida para la detección
        de cambios de la actualización incremental.

        :param crudo: Contenido en bytes devuelto por :meth:`descargar_crudo`.
        :returns: La fecha como cadena, o ``None`` si no viene en la respuesta.
        """
        try:
            documento = json.loads(crudo.decode("utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return None
        fecha = self._extraer_metadata(documento).get("date")
        return str(fecha) if fecha is not None else None

    # ------------------------------------------------------------------ #
    # Operaciones de alto nivel                                           #
    # ------------------------------------------------------------------ #
    def descargar_asadas(self) -> List[Asada]:
        """Descarga y parsea las ASADAS en un solo paso.

        :returns: Lista de ASADAS obtenidas del endpoint.
        """
        return self.parsear(self.descargar_crudo())

    @staticmethod
    def calcular_huella(crudo: bytes) -> str:
        """Calcula la huella SHA-256 del contenido crudo.

        :param crudo: Contenido en bytes a resumir.
        :returns: Huella hexadecimal de 64 caracteres.
        """
        return hashlib.sha256(crudo).hexdigest()

    def obtener_metadata(self, crudo: Optional[bytes] = None) -> MetadataRemota:
        """Construye los metadatos de la descarga actual.

        :param crudo: Contenido ya descargado; si es ``None``, se descarga.
        :returns: :class:`MetadataRemota` con huella, fecha y cantidad.
        """
        if crudo is None:
            crudo = self.descargar_crudo()
        cantidad = len(self._extraer_lista(json.loads(crudo.decode("utf-8", "ignore"))))
        return MetadataRemota(
            huella=self.calcular_huella(crudo),
            fecha=datetime.now(timezone.utc).isoformat(),
            fecha_modificacion=self.obtener_fecha_modificacion(crudo),
            last_modified=self._ultimo_last_modified,
            cantidad=cantidad,
        )
