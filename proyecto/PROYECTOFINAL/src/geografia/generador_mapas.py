"""
GeneradorMapas — genera un mapa HTML (Folium / OpenStreetMap) con las ASADAS.

Generaliza el script original `Genera_mapa_html.py` (una sola ASADA quemada)
para recibir una LISTA de ASADAS y poner un marcador por cada una. Reutiliza
`ConversorCoordenadas` (la lógica de pyproj vive en un solo lugar).

Trabaja con el modelo de Dev A: el "nombre" mostrado es el campo `operador`,
y las coordenadas son `coordenadaX`/`coordenadaY` (CRTM05).
"""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from typing import Iterable, List

import folium

from src.geografia.conversor_coordenadas import ConversorCoordenadas
from src.modelo.asada import Asada

# Centro aproximado de Costa Rica, respaldo si no hay puntos válidos.
CENTRO_CR = (9.7489, -83.7534)


def _nombre(asada: Asada) -> str:
    """Nombre para mostrar: el operador, o el id si viniera vacío."""
    return asada.operador or f"ASADA {asada.id_Asada}"


def _ruta_politica(asada: Asada) -> str:
    return f"{asada.provincia} > {asada.canton} > {asada.distrito}"


class GeneradorMapas:
    """Construye mapas HTML con marcadores de ASADAS."""

    def __init__(self, carpeta_salida: str = "mapas") -> None:
        self.carpeta_salida: str = carpeta_salida
        self._conversor = ConversorCoordenadas()

    def generar_html(self, asadas: Iterable[Asada], nombre_archivo: str = "asadas.html") -> str:
        """Genera el mapa con un marcador por ASADA y lo guarda en disco.

        :param asadas: ASADAS a graficar.
        :param nombre_archivo: Nombre del HTML de salida.
        :returns: Ruta absoluta del archivo HTML generado.
        """
        asadas = list(asadas)

        puntos: List[tuple] = []        # (lat, lon, asada)
        descartadas = 0
        for a in asadas:
            lat, lon = self._conversor.crtm05_a_wgs84(a.coordenadaX, a.coordenadaY)
            if self._conversor.es_valida_para_cr(lat, lon):
                puntos.append((lat, lon, a))
            else:
                descartadas += 1

        if puntos:
            centro = (sum(p[0] for p in puntos) / len(puntos),
                      sum(p[1] for p in puntos) / len(puntos))
        else:
            centro = CENTRO_CR

        mapa = folium.Map(location=list(centro), zoom_start=8, tiles="OpenStreetMap")

        for lat, lon, a in puntos:
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(
                    f"<b>{_nombre(a)}</b><br>ID: {a.id_Asada}<br>{_ruta_politica(a)}",
                    max_width=250,
                ),
                tooltip=_nombre(a),
                icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
            ).add_to(mapa)

        if len(puntos) > 1:
            lats = [p[0] for p in puntos]
            lons = [p[1] for p in puntos]
            mapa.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
        elif len(puntos) == 1:
            mapa.location = [puntos[0][0], puntos[0][1]]
            mapa.zoom_start = 15

        os.makedirs(self.carpeta_salida, exist_ok=True)
        ruta = Path(self.carpeta_salida) / nombre_archivo
        mapa.save(str(ruta))

        if descartadas:
            print(f"[GeneradorMapas] Aviso: {descartadas} ASADA(s) con coordenadas "
                  f"fuera de Costa Rica fueron omitidas.")

        return str(ruta.resolve())

    @staticmethod
    def abrir_en_navegador(ruta: str) -> None:
        """Abre el HTML generado en el navegador predeterminado."""
        webbrowser.open(f"file://{Path(ruta).resolve()}")


if __name__ == "__main__":
    ejemplo = [
        Asada(id_Asada=1790, provincia="Alajuela", canton="San Carlos", distrito="Pital", operador="ASADA Cuestillas", coordenadaX=490866.06, coordenadaY=1098368.55),
        Asada(id_Asada=205, provincia="Alajuela", canton="San Carlos", distrito="La Fortuna", operador="ASADA La Fortuna", coordenadaX=470000.0, coordenadaY=1145000.0),
        Asada(id_Asada=42, provincia="San José", canton="Curridabat", distrito="Tirrases", operador="ASADA Tirrases", coordenadaX=500000.0, coordenadaY=1095000.0),
    ]
    generador = GeneradorMapas()
    ruta = generador.generar_html(ejemplo)
    print("Mapa generado en:", ruta)
