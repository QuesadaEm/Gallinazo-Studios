"""Modelo de dominio del sistema: la entidad ``Asada``.

Este módulo define el **contrato de datos compartido** entre el Desarrollador A
(motor de persistencia e indexación) y el Desarrollador B (red, geografía y
GUI). Cualquier cambio en los nombres o tipos de los atributos de :class:`Asada`
debe acordarse entre ambos integrantes, porque tanto el archivo binario
principal como el protocolo de sockets dependen de esta estructura.

Los nombres de los atributos se mantienen idénticos a las llaves entregadas por
el endpoint de ARESEP (``id_Asada``, ``coordenadaX``, etc.) para minimizar la
traducción entre el JSON remoto y el modelo interno.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Mapping


def _a_entero(valor: Any, predeterminado: int = 0) -> int:
    """Convierte ``valor`` a ``int`` de forma tolerante.

    ARESEP puede entregar los identificadores como número o como cadena. Esta
    función normaliza ambos casos y, ante un valor inválido o nulo, devuelve
    ``predeterminado`` en lugar de lanzar una excepción.

    :param valor: Valor crudo proveniente del JSON.
    :param predeterminado: Valor a retornar si la conversión falla.
    :returns: El entero equivalente, o ``predeterminado``.
    """
    if valor is None:
        return predeterminado
    try:
        return int(str(valor).strip())
    except (ValueError, TypeError):
        return predeterminado


def _a_flotante(valor: Any, predeterminado: float = 0.0) -> float:
    """Convierte ``valor`` a ``float`` de forma tolerante.

    Acepta separador decimal tanto ``.`` como ``,`` (usual en datos locales).

    :param valor: Valor crudo proveniente del JSON.
    :param predeterminado: Valor a retornar si la conversión falla.
    :returns: El flotante equivalente, o ``predeterminado``.
    """
    if valor is None:
        return predeterminado
    try:
        return float(str(valor).strip().replace(",", "."))
    except (ValueError, TypeError):
        return predeterminado


def _a_texto(valor: Any) -> str:
    """Normaliza ``valor`` a una cadena sin espacios sobrantes."""
    if valor is None:
        return ""
    return str(valor).strip()


@dataclass
class Asada:
    """Representa una ASADA (registro completo del sistema).

    Es un :class:`dataclasses.dataclass` para obtener de forma automática el
    constructor, ``__repr__`` y la comparación por valor. Esta clase **no**
    contiene lógica de persistencia ni de red: es un objeto de transferencia de
    datos puro (capa de dominio).

    :ivar id_Asada: Identificador único de la ASADA. Llave del árbol BST.
    :ivar id_Objecto: Identificador interno del objeto en ARESEP.
    :ivar provincia: Nombre de la provincia.
    :ivar canton: Nombre del cantón.
    :ivar distrito: Nombre del distrito.
    :ivar operador: Nombre del operador del acueducto.
    :ivar correo: Correo de contacto.
    :ivar telefono: Teléfono de contacto.
    :ivar fax: Fax de contacto.
    :ivar tipoSistema: Tipo de sistema de acueducto.
    :ivar codigoDTA: Código de división territorial administrativa.
    :ivar coordenadaX: Coordenada X en el sistema CRTM05 (metros).
    :ivar coordenadaY: Coordenada Y en el sistema CRTM05 (metros).
    """

    id_Asada: int
    id_Objecto: int = 0
    provincia: str = ""
    canton: str = ""
    distrito: str = ""
    operador: str = ""
    correo: str = ""
    telefono: str = ""
    fax: str = ""
    tipoSistema: str = ""
    codigoDTA: str = ""
    coordenadaX: float = 0.0
    coordenadaY: float = 0.0

    @classmethod
    def desde_dict(cls, datos: Mapping[str, Any]) -> "Asada":
        """Construye una :class:`Asada` a partir de un diccionario del JSON.

        La lectura de llaves es **insensible a mayúsculas/minúsculas** para
        tolerar pequeñas variaciones en el esquema remoto.

        :param datos: Diccionario con los atributos crudos de una ASADA.
        :returns: La instancia de :class:`Asada` resultante.
        """
        normalizado: Dict[str, Any] = {
            str(clave).lower(): valor for clave, valor in datos.items()
        }

        def obtener(*nombres: str) -> Any:
            for nombre in nombres:
                if nombre.lower() in normalizado:
                    return normalizado[nombre.lower()]
            return None

        return cls(
            id_Asada=_a_entero(obtener("id_Asada", "idAsada", "id")),
            id_Objecto=_a_entero(obtener("id_Objecto", "id_Objeto", "idObjecto")),
            provincia=_a_texto(obtener("provincia")),
            canton=_a_texto(obtener("canton", "cantón")),
            distrito=_a_texto(obtener("distrito")),
            operador=_a_texto(obtener("operador")),
            correo=_a_texto(obtener("correo")),
            telefono=_a_texto(obtener("telefono", "teléfono")),
            fax=_a_texto(obtener("fax")),
            tipoSistema=_a_texto(obtener("tipoSistema", "tiposistema")),
            codigoDTA=_a_texto(obtener("codigoDTA", "codigodta")),
            coordenadaX=_a_flotante(obtener("coordenadaX", "coordenadax")),
            coordenadaY=_a_flotante(obtener("coordenadaY", "coordenaday")),
        )

    def a_dict(self) -> Dict[str, Any]:
        """Devuelve la representación de la ASADA como diccionario.

        Útil para el protocolo de sockets (serialización a JSON) que
        implementa el Desarrollador B.

        :returns: Diccionario con todos los atributos de la ASADA.
        """
        return asdict(self)
