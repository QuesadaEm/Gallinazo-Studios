"""Pruebas del motor de persistencia e indexación (Desarrollador A).

Cubren la serialización binaria, el acceso directo por posición, la corrección
del BST persistente (incluyendo búsquedas y balanceo), la actualización
incremental y la API pública. Son autocontenidas: usan directorios temporales
y un *fixture* JSON local, por lo que no requieren conexión a ARESEP.

Ejecución::

    python -m unittest discover -s tests        # con la stdlib
    python -m pytest tests                       # con pytest (si está instalado)
"""

from __future__ import annotations

import os
import tempfile
import unittest

from src.api.motor_consulta import MotorConsulta
from src.ingesta.actualizador import ActualizadorIncremental
from src.ingesta.cliente_aresep import ClienteAresep
from src.modelo.asada import Asada
from src.persistencia.indice_arbol import IndiceArbolBinario
from src.persistencia.repositorio_binario import RepositorioBinario

RUTA_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures_asadas.json")


def _asada_ejemplo(id_asada: int = 50) -> Asada:
    return Asada(
        id_Asada=id_asada,
        id_Objecto=1001,
        provincia="Alajuela",
        canton="San Carlos",
        distrito="Quesada",
        operador="ASADA Quesada",
        correo="quesada@asada.cr",
        telefono="2460-1000",
        fax="2460-1001",
        tipoSistema="Acueducto",
        codigoDTA="21001",
        coordenadaX=404500.5,
        coordenadaY=1140200.0,
    )


class PruebasRepositorio(unittest.TestCase):
    """Verifica la serialización y el acceso directo del archivo principal."""

    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.repo = RepositorioBinario(os.path.join(self.dir.name, "registros.dat"))

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_ida_y_vuelta_preserva_los_datos(self) -> None:
        original = _asada_ejemplo()
        posicion = self.repo.escribir_registro(original)
        recuperada = self.repo.leer_registro(posicion)
        self.assertEqual(original, recuperada)

    def test_registros_de_tamano_fijo(self) -> None:
        self.repo.escribir_registro(_asada_ejemplo(1))
        self.repo.escribir_registro(_asada_ejemplo(2))
        self.assertEqual(self.repo.cantidad_registros(), 2)
        self.assertEqual(
            os.path.getsize(self.repo.ruta),
            2 * RepositorioBinario.TAMANO_REGISTRO,
        )

    def test_acceso_directo_por_posicion(self) -> None:
        posiciones = [self.repo.escribir_registro(_asada_ejemplo(i)) for i in range(5)]
        # Se lee en orden inverso para confirmar acceso aleatorio real.
        for esperado, posicion in reversed(list(enumerate(posiciones))):
            self.assertEqual(self.repo.leer_registro(posicion).id_Asada, esperado)

    def test_texto_largo_se_trunca_sin_romper(self) -> None:
        asada = _asada_ejemplo()
        asada.operador = "X" * 500
        posicion = self.repo.escribir_registro(asada)
        recuperada = self.repo.leer_registro(posicion)
        self.assertEqual(len(recuperada.operador), 150)  # límite del campo

    def test_posicion_invalida_lanza_error(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.leer_registro(999_999)


class PruebasIndiceArbol(unittest.TestCase):
    """Verifica la corrección del BST persistente."""

    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.indice = IndiceArbolBinario(os.path.join(self.dir.name, "indice.dat"))

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_insertar_y_buscar(self) -> None:
        self.indice.insertar(50, 100)
        self.indice.insertar(30, 200)
        self.indice.insertar(70, 300)
        self.assertEqual(self.indice.buscar(30), 200)
        self.assertEqual(self.indice.buscar(50), 100)
        self.assertEqual(self.indice.buscar(70), 300)

    def test_buscar_inexistente_devuelve_none(self) -> None:
        self.indice.insertar(50, 100)
        self.assertIsNone(self.indice.buscar(999))

    def test_busqueda_en_disco_coincide_con_memoria(self) -> None:
        for i, id_asada in enumerate([50, 30, 70, 10, 40, 60, 80]):
            self.indice.insertar(id_asada, i * 10)
        for id_asada in [50, 30, 70, 10, 40, 60, 80]:
            self.assertEqual(
                self.indice.buscar(id_asada),
                self.indice.buscar_en_disco(id_asada),
            )

    def test_reconstruccion_balanceada_persiste_todo(self) -> None:
        pares = [(i, i * 7) for i in range(1, 64)]
        self.indice.reconstruir(pares)
        self.assertEqual(self.indice.cantidad_nodos(), 63)
        for id_asada, posicion in pares:
            self.assertEqual(self.indice.buscar(id_asada), posicion)

    def test_duplicado_actualiza_posicion(self) -> None:
        self.indice.insertar(50, 100)
        self.indice.insertar(50, 999)
        self.assertEqual(self.indice.buscar(50), 999)
        self.assertEqual(self.indice.cantidad_nodos(), 1)

    def test_persistencia_entre_instancias(self) -> None:
        self.indice.insertar(50, 100)
        self.indice.insertar(25, 200)
        otra = IndiceArbolBinario(self.indice.ruta)
        self.assertEqual(otra.buscar(50), 100)
        self.assertEqual(otra.buscar(25), 200)


class PruebasClienteYActualizador(unittest.TestCase):
    """Verifica la ingesta sin conexión y la actualización incremental."""

    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.cliente = ClienteAresep(origen_local=RUTA_FIXTURE)
        self.repo = RepositorioBinario(os.path.join(self.dir.name, "registros.dat"))
        self.indice = IndiceArbolBinario(os.path.join(self.dir.name, "indice.dat"))
        self.actualizador = ActualizadorIncremental(
            cliente=self.cliente,
            repositorio=self.repo,
            indice=self.indice,
            ruta_metadata=os.path.join(self.dir.name, "metadata_sync.json"),
        )

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_parseo_envuelto_en_d(self) -> None:
        asadas = self.cliente.descargar_asadas()
        self.assertEqual(len(asadas), 8)
        self.assertTrue(all(isinstance(a, Asada) for a in asadas))

    def test_fecha_modificacion_desde_metadata(self) -> None:
        crudo = self.cliente.descargar_crudo()
        fecha = self.cliente.obtener_fecha_modificacion(crudo)
        self.assertEqual(fecha, "2019-11-12T14:15:53.000")

    def test_soporta_envoltorio_d_antiguo(self) -> None:
        crudo = b'{"d": [{"id_Asada": 9, "provincia": "Guanacaste"}]}'
        asadas = self.cliente.parsear(crudo)
        self.assertEqual(len(asadas), 1)
        self.assertEqual(asadas[0].id_Asada, 9)

    def test_cambio_de_fecha_oficial_detecta_actualizacion(self) -> None:
        # Primera sincronización con la fecha del fixture.
        self.assertTrue(self.actualizador.sincronizar())
        # Simula que ARESEP publicó una fecha distinta (mismo contenido).
        metadata = self.actualizador._cargar_metadata_local()
        metadata["fecha_modificacion"] = "2025-01-01T00:00:00.000"
        import json as _json
        with open(self.actualizador.ruta_metadata, "w", encoding="utf-8") as f:
            _json.dump(metadata, f)
        # Como la fecha local quedó distinta de la remota, debe detectar cambios.
        self.assertTrue(self.actualizador.hay_cambios())

    def test_primera_sincronizacion_regenera(self) -> None:
        self.assertTrue(self.actualizador.sincronizar())
        self.assertEqual(self.repo.cantidad_registros(), 8)

    def test_segunda_sincronizacion_sin_cambios(self) -> None:
        self.assertTrue(self.actualizador.sincronizar())
        self.assertFalse(self.actualizador.sincronizar())  # sin cambios

    def test_forzar_regenera_aunque_no_haya_cambios(self) -> None:
        self.actualizador.sincronizar()
        self.assertTrue(self.actualizador.sincronizar(forzar=True))

    def test_callback_de_regeneracion_se_invoca(self) -> None:
        llamado = {"veces": 0}

        def gancho(_repo: RepositorioBinario) -> None:
            llamado["veces"] += 1

        actualizador = ActualizadorIncremental(
            cliente=self.cliente,
            repositorio=self.repo,
            indice=self.indice,
            ruta_metadata=os.path.join(self.dir.name, "meta2.json"),
            al_regenerar=gancho,
        )
        actualizador.sincronizar()
        self.assertEqual(llamado["veces"], 1)


class PruebasApiMotor(unittest.TestCase):
    """Verifica la API pública de punta a punta (la que usa el servidor de B)."""

    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.motor = MotorConsulta(
            directorio_datos=self.dir.name,
            origen_local=RUTA_FIXTURE,
        )
        self.motor.iniciar()

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_buscar_por_id_devuelve_posicion(self) -> None:
        self.assertIsNotNone(self.motor.buscar_por_id(50))
        self.assertIsNone(self.motor.buscar_por_id(99999))

    def test_obtener_asada_completa(self) -> None:
        asada = self.motor.obtener_asada(80)
        self.assertIsNotNone(asada)
        assert asada is not None
        self.assertEqual(asada.provincia, "Cartago")
        self.assertEqual(asada.distrito, "Oriental")

    def test_obtener_todas(self) -> None:
        self.assertEqual(len(self.motor.obtener_todas()), 8)

    def test_actualizar_datos_idempotente(self) -> None:
        # Ya se sincronizó en iniciar(); una nueva llamada no debe regenerar.
        self.assertFalse(self.motor.actualizar_datos())


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
