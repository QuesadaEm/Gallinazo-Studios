"""
Pruebas de integración de la capa de red (Dev B).

Levanta un Servidor real en un puerto efímero dentro de un hilo y lo consulta
con un Cliente real, usando los datos del fixture de ARESEP.

Ejecutar desde la raíz:  python -m unittest tests.test_protocolo
"""

import os
import socket
import tempfile
import threading
import unittest

from src.api.motor_consulta import MotorConsulta
from src.geografia.indice_geografico import IndiceGeografico
from src.red.cliente import Cliente, ErrorConsulta
from src.red.protocolo import Conexion, Protocolo
from src.red.servidor import Servidor

RUTA_FIXTURES = os.path.join("tests", "fixtures_asadas.json")


class TestProtocoloUnidad(unittest.TestCase):

    def test_round_trip_serializacion(self):
        original = Protocolo.consulta("por_id", id=50)
        linea = Protocolo.serializar(original)
        self.assertTrue(linea.endswith(b"\n"))
        self.assertEqual(Protocolo.deserializar(linea.strip()), original)

    def test_framing_mensajes_pegados(self):
        # Dos mensajes en un solo envío deben leerse por separado.
        a, b = socket.socketpair()
        emisor, receptor = Conexion(a), Conexion(b)
        emisor.enviar({"tipo": "provincias"})
        emisor.enviar({"tipo": "salir"})
        self.assertEqual(receptor.recibir(), {"tipo": "provincias"})
        self.assertEqual(receptor.recibir(), {"tipo": "salir"})
        emisor.cerrar(); receptor.cerrar()


class TestServidorClienteIntegracion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.indice_geo = IndiceGeografico()
        cls.motor = MotorConsulta(
            directorio_datos=cls.tmp,
            origen_local=RUTA_FIXTURES,
            al_regenerar=lambda repo: cls.indice_geo.construir(repo),
        )
        cls.motor.iniciar()
        if not cls.indice_geo.provincias():
            cls.indice_geo.construir(cls.motor.repositorio)

        cls.servidor = Servidor(cls.motor, cls.indice_geo, host="127.0.0.1", port=0)
        puerto = cls.servidor.preparar()
        cls.puerto = puerto
        cls.hilo = threading.Thread(target=cls.servidor.servir, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.detener()

    def _cliente(self) -> Cliente:
        c = Cliente(host="127.0.0.1", port=self.puerto)
        c.conectar()
        return c

    def test_provincias(self):
        with self._cliente() as c:
            provincias = c.provincias()
        self.assertIn("Alajuela", provincias)
        self.assertEqual(provincias, sorted(provincias, key=str.lower))

    def test_navegacion_combos(self):
        with self._cliente() as c:
            self.assertIn("San Carlos", c.cantones("Alajuela"))
            distritos = c.distritos("Alajuela", "San Carlos")
            self.assertIn("Quesada", distritos)

    def test_asadas_de_distrito(self):
        with self._cliente() as c:
            registros = c.asadas("Alajuela", "San Carlos", "Quesada")
        self.assertGreaterEqual(len(registros), 1)
        self.assertEqual(registros[0]["operador"], "ASADA Quesada")
        self.assertIn("coordenadaX", registros[0])

    def test_por_id(self):
        with self._cliente() as c:
            asada = c.por_id(50)
        self.assertEqual(asada["id_Asada"], 50)
        self.assertEqual(asada["operador"], "ASADA Quesada")

    def test_id_inexistente_lanza_error(self):
        with self._cliente() as c:
            with self.assertRaises(ErrorConsulta):
                c.por_id(999999)

    def test_dos_clientes_concurrentes(self):
        # Dos clientes a la vez, atendidos por hilos distintos.
        c1, c2 = self._cliente(), self._cliente()
        try:
            self.assertIn("Alajuela", c1.provincias())
            self.assertEqual(c2.por_id(50)["operador"], "ASADA Quesada")
        finally:
            c1.cerrar(); c2.cerrar()


if __name__ == "__main__":
    unittest.main()
