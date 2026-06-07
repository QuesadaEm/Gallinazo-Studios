"""Prueba de integración EN VIVO contra el endpoint real de ARESEP.

A diferencia de ``test_motor.py`` (que es offline y siempre corre), esta prueba
realiza una llamada HTTP real. Por eso está **desactivada por defecto** y solo
se ejecuta si se define la variable de entorno ``ARESEP_LIVE=1``. Así la batería
offline sigue siendo determinista y rápida, y la verificación en vivo queda
disponible bajo demanda.

Ejecución::

    # Linux / macOS
    ARESEP_LIVE=1 python -m unittest tests.test_integracion_aresep -v
    # Windows (PowerShell)
    $env:ARESEP_LIVE=1; python -m unittest tests.test_integracion_aresep -v
"""

from __future__ import annotations

import os
import tempfile
import unittest

from src.api.motor_consulta import MotorConsulta
from src.ingesta.cliente_aresep import ClienteAresep

EJECUTAR_EN_VIVO = os.environ.get("ARESEP_LIVE") == "1"
RAZON = "Prueba en vivo desactivada; defina ARESEP_LIVE=1 para ejecutarla."


@unittest.skipUnless(EJECUTAR_EN_VIVO, RAZON)
class PruebasIntegracionAresep(unittest.TestCase):
    """Verifican el camino HTTP real (requieren conexión a internet)."""

    def test_endpoint_devuelve_registros(self) -> None:
        cliente = ClienteAresep()
        asadas = cliente.descargar_asadas()
        self.assertGreater(len(asadas), 0, "ARESEP no devolvió registros.")
        self.assertTrue(all(a.id_Asada != 0 for a in asadas[:10]))

    def test_flujo_completo_en_vivo(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            motor = MotorConsulta(directorio_datos=carpeta)
            motor.iniciar()
            todas = motor.obtener_todas()
            self.assertGreater(len(todas), 0)
            # Una búsqueda real por id debe recuperar el mismo registro.
            primera = todas[0]
            recuperada = motor.obtener_asada(primera.id_Asada)
            self.assertIsNotNone(recuperada)
            assert recuperada is not None
            self.assertEqual(recuperada.id_Asada, primera.id_Asada)
            # La segunda sincronización no debe detectar cambios.
            self.assertFalse(motor.actualizar_datos())


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
