"""
Pruebas de la geografía de Dev B (conversor, índice y mapas).

Usa el modelo de Dev A (campos id_Asada, coordenadaX, operador, ...).
Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_geografico
"""

import os
import tempfile
import unittest

from src.geografia.conversor_coordenadas import ConversorCoordenadas
from src.geografia.generador_mapas import GeneradorMapas
from src.geografia.indice_geografico import IndiceGeografico, RepositorioMock
from src.modelo.asada import Asada


def _asada(id_a, prov, cant, dist, x, y, operador="ASADA X"):
    return Asada(id_Asada=id_a, provincia=prov, canton=cant, distrito=dist,
                 operador=operador, coordenadaX=x, coordenadaY=y)


class TestConversorCoordenadas(unittest.TestCase):

    def setUp(self):
        self.conv = ConversorCoordenadas()

    def test_punto_conocido_cae_en_cr(self):
        lat, lon = self.conv.crtm05_a_wgs84(490866.06, 1098368.55)
        self.assertAlmostEqual(lat, 9.9333, places=3)
        self.assertAlmostEqual(lon, -84.0833, places=3)
        self.assertTrue(self.conv.es_valida_para_cr(lat, lon))

    def test_devuelve_orden_lat_lon(self):
        lat, lon = self.conv.crtm05_a_wgs84(490866.06, 1098368.55)
        self.assertGreater(lat, 0)
        self.assertLess(lon, 0)

    def test_punto_fuera_de_cr_se_detecta(self):
        self.assertFalse(self.conv.es_valida_para_cr(40.4168, -3.7038))


class TestIndiceGeografico(unittest.TestCase):

    def setUp(self):
        self.datos = [
            _asada(1790, "Alajuela", "San Carlos", "Pital", 490866.06, 1098368.55),
            _asada(205, "Alajuela", "San Carlos", "La Fortuna", 470000.0, 1145000.0),
            _asada(311, "Alajuela", "San Carlos", "Aguas Zarcas", 480000.0, 1150000.0),
            _asada(42, "San José", "Curridabat", "Tirrases", 500000.0, 1095000.0),
            # Mismo nombre de cantón ('Central') en dos provincias distintas.
            _asada(7, "San José", "Central", "Carmen", 490000.0, 1100000.0),
            _asada(8, "Cartago", "Central", "Oriental", 517300.0, 1090400.0),
        ]
        self.indice = IndiceGeografico().construir(RepositorioMock(self.datos))

    def test_total(self):
        self.assertEqual(self.indice.total_asadas(), 6)

    def test_provincias_ordenadas(self):
        self.assertEqual(self.indice.provincias(), ["Alajuela", "Cartago", "San José"])

    def test_distritos_ordenados(self):
        self.assertEqual(
            self.indice.distritos_de("Alajuela", "San Carlos"),
            ["Aguas Zarcas", "La Fortuna", "Pital"],
        )

    def test_canton_homonimo_se_separa_por_provincia(self):
        self.assertEqual(self.indice.distritos_de("San José", "Central"), ["Carmen"])
        self.assertEqual(self.indice.distritos_de("Cartago", "Central"), ["Oriental"])

    def test_asadas_de_devuelve_id_entero_y_posicion(self):
        resultado = self.indice.asadas_de("Alajuela", "San Carlos", "Pital")
        self.assertEqual(len(resultado), 1)
        id_asada, posicion = resultado[0]
        self.assertEqual(id_asada, 1790)
        self.assertIsInstance(id_asada, int)
        self.assertIsInstance(posicion, int)

    def test_consulta_inexistente_no_falla(self):
        self.assertEqual(self.indice.cantones_de("Limón"), [])
        self.assertEqual(self.indice.distritos_de("Limón", "Pococí"), [])


class TestGeneradorMapas(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.generador = GeneradorMapas(carpeta_salida=self.tmp)

    def test_genera_archivo_con_marcadores(self):
        asadas = [
            _asada(1790, "Alajuela", "San Carlos", "Pital", 490866.06, 1098368.55),
            _asada(42, "San José", "Curridabat", "Tirrases", 500000.0, 1095000.0),
        ]
        ruta = self.generador.generar_html(asadas, "prueba.html")
        self.assertTrue(os.path.exists(ruta))
        with open(ruta, encoding="utf-8") as f:
            html = f.read()
        self.assertEqual(html.count("L.marker("), 2)

    def test_descarta_coordenadas_fuera_de_cr(self):
        asadas = [
            _asada(1790, "Alajuela", "San Carlos", "Pital", 490866.06, 1098368.55),
            _asada(999, "??", "??", "??", 0.0, 0.0),  # cae fuera de CR
        ]
        ruta = self.generador.generar_html(asadas, "prueba2.html")
        with open(ruta, encoding="utf-8") as f:
            html = f.read()
        self.assertEqual(html.count("L.marker("), 1)


if __name__ == "__main__":
    unittest.main()
