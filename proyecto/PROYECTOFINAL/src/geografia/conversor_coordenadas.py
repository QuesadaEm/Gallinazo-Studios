"""
ConversorCoordenadas — CRTM05 (EPSG:5367) -> WGS84 (EPSG:4326).

CRTM05 es el sistema oficial de Costa Rica. Las coordenadas de ARESEP vienen
en metros (coordenadaX, coordenadaY) y hay que pasarlas a latitud/longitud para
poder pintarlas sobre OpenStreetMap con Folium.

Detalle importante de pyproj: con `always_xy=True`, `transform(x, y)` devuelve
los valores en orden (longitud, latitud). Folium en cambio espera [lat, lon].
Por eso este conversor devuelve SIEMPRE (lat, lon), ya en el orden que necesita
el mapa, para que nadie se confunda más adelante.
"""

from __future__ import annotations

from pyproj import Transformer

# Límites aproximados de Costa Rica, para validar que una conversión tenga sentido.
LAT_MIN, LAT_MAX = 8.0, 11.3
LON_MIN, LON_MAX = -86.0, -82.5


class ConversorCoordenadas:
    """Convierte coordenadas CRTM05 a WGS84 (lat, lon)."""

    def __init__(self) -> None:
        # El Transformer es reutilizable; se crea una sola vez (es lo costoso).
        self._transformador = Transformer.from_crs(
            "EPSG:5367",   # CRTM05
            "EPSG:4326",   # WGS84
            always_xy=True,
        )

    def crtm05_a_wgs84(self, x: float, y: float) -> tuple[float, float]:
        """
        Convierte un par CRTM05 (x, y) en (latitud, longitud).

        Devuelve (lat, lon) listo para Folium.
        """
        lon, lat = self._transformador.transform(x, y)
        return (lat, lon)

    def es_valida_para_cr(self, lat: float, lon: float) -> bool:
        """True si (lat, lon) cae dentro del rectángulo que envuelve a CR."""
        return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX

    def convertir_lote(self, puntos):
        """
        Convierte una lista de pares (x, y) en una lista de (lat, lon).

        Útil para preparar de un solo golpe todos los marcadores de un mapa.
        """
        return [self.crtm05_a_wgs84(x, y) for (x, y) in puntos]


if __name__ == "__main__":
    conv = ConversorCoordenadas()

    # Punto de prueba: aprox. San José centro convertido previamente a CRTM05.
    lat, lon = conv.crtm05_a_wgs84(490866.06, 1098368.55)
    print(f"lat={lat:.5f}  lon={lon:.5f}")
    print("¿Dentro de Costa Rica?", conv.es_valida_para_cr(lat, lon))
