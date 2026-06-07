"""Pruebas del tercer archivo binario — IndiceGeograficoBinario.

Verifica que la serialización y deserialización de la estructura jerárquica
provincia → cantón → distrito → ASADAs funciona correctamente, preservando
todos los punteros lógicos y los datos de cada nodo.
"""

import os
import tempfile
import unittest

from src.geografia.indice_geografico import IndiceGeografico
from src.geografia.nodos_geograficos import NodoAsadaGeo, NodoCanton, NodoDistrito, NodoProvincia
from src.modelo.asada import Asada
from src.persistencia.indice_geografico_binario import IndiceGeograficoBinario


def _asadas_ejemplo():
    """ASADAS de prueba que cubren múltiples provincias, cantones y distritos."""
    return [
        Asada(id_Asada=10, provincia="Alajuela", canton="San Carlos",
              distrito="Quesada", operador="ASADA Quesada",
              coordenadaX=404500.5, coordenadaY=1140200.0),
        Asada(id_Asada=20, provincia="Alajuela", canton="San Carlos",
              distrito="Florencia", operador="ASADA Florencia",
              coordenadaX=402100.0, coordenadaY=1138900.0),
        Asada(id_Asada=30, provincia="Cartago", canton="Cartago",
              distrito="Oriental", operador="ASADA Oriental",
              coordenadaX=517300.0, coordenadaY=1090400.0),
        Asada(id_Asada=40, provincia="San José", canton="Central",
              distrito="Carmen", operador="ASADA Carmen",
              coordenadaX=490000.0, coordenadaY=1100000.0),
        Asada(id_Asada=50, provincia="Alajuela", canton="San Carlos",
              distrito="Quesada", operador="ASADA Quesada 2",
              coordenadaX=404600.0, coordenadaY=1140300.0),
    ]


class PruebasIndiceGeograficoBinario(unittest.TestCase):
    """Tests de serialización/deserialización del tercer archivo binario."""

    def setUp(self):
        """Construye un IndiceGeografico con datos de prueba."""
        self.tmp = tempfile.mkdtemp()
        self.ruta = os.path.join(self.tmp, "indice_geografico.dat")
        # Construir el índice usando un repositorio simulado.
        asadas = _asadas_ejemplo()
        indice = IndiceGeografico()
        for i, a in enumerate(asadas):
            indice.insertar(a, i * 100)   # posición ficticia = i * 100
        self.indice_original = indice

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_archivo_se_crea_al_serializar(self):
        """El archivo binario debe existir tras llamar a persistir."""
        self.assertFalse(os.path.exists(self.ruta))
        self.indice_original.persistir(self.ruta)
        self.assertTrue(os.path.exists(self.ruta))
        self.assertGreater(os.path.getsize(self.ruta), 8)  # más que solo la cabecera

    def test_provincias_sobreviven_round_trip(self):
        """Las mismas provincias deben aparecer tras serializar y deserializar."""
        self.indice_original.persistir(self.ruta)
        indice2 = IndiceGeografico()
        indice2.cargar_desde_binario(self.ruta)
        self.assertEqual(
            self.indice_original.provincias(),
            indice2.provincias()
        )

    def test_cantones_sobreviven_round_trip(self):
        """Los cantones de cada provincia se reconstruyen correctamente."""
        self.indice_original.persistir(self.ruta)
        indice2 = IndiceGeografico()
        indice2.cargar_desde_binario(self.ruta)
        for prov in self.indice_original.provincias():
            self.assertEqual(
                self.indice_original.cantones_de(prov),
                indice2.cantones_de(prov),
                msg=f"Cantones de {prov!r} no coinciden tras round-trip"
            )

    def test_distritos_sobreviven_round_trip(self):
        """Los distritos de cada cantón se reconstruyen correctamente."""
        self.indice_original.persistir(self.ruta)
        indice2 = IndiceGeografico()
        indice2.cargar_desde_binario(self.ruta)
        for prov in self.indice_original.provincias():
            for cant in self.indice_original.cantones_de(prov):
                self.assertEqual(
                    self.indice_original.distritos_de(prov, cant),
                    indice2.distritos_de(prov, cant),
                    msg=f"Distritos de {prov!r} > {cant!r} no coinciden"
                )

    def test_total_asadas_se_conserva(self):
        """El número total de ASADAs indexadas se preserva."""
        self.indice_original.persistir(self.ruta)
        indice2 = IndiceGeografico()
        indice2.cargar_desde_binario(self.ruta)
        self.assertEqual(
            self.indice_original.total_asadas(),
            indice2.total_asadas()
        )

    def test_posicion_registro_se_preserva(self):
        """Las posiciones físicas de los registros se conservan en los nodos ASADA."""
        self.indice_original.persistir(self.ruta)
        indice2 = IndiceGeografico()
        indice2.cargar_desde_binario(self.ruta)
        pares_orig = self.indice_original.asadas_de("Alajuela", "San Carlos", "Quesada")
        pares_rest = indice2.asadas_de("Alajuela", "San Carlos", "Quesada")
        self.assertEqual(
            sorted(pares_orig), sorted(pares_rest),
            msg="Los pares (id_asada, posicion_registro) deben coincidir"
        )

    def test_cargar_desde_binario_devuelve_false_si_no_existe(self):
        """cargar_desde_binario devuelve False cuando el archivo no existe."""
        indice = IndiceGeografico()
        resultado = indice.cargar_desde_binario(os.path.join(self.tmp, "no_existe.dat"))
        self.assertFalse(resultado)
        self.assertIsNone(indice.primera_provincia)

    def test_existe_devuelve_false_antes_de_serializar(self):
        """IndiceGeograficoBinario.existe() es False si el archivo no existe."""
        binario = IndiceGeograficoBinario(self.ruta)
        self.assertFalse(binario.existe())

    def test_existe_devuelve_true_despues_de_serializar(self):
        """IndiceGeograficoBinario.existe() es True tras serializar."""
        self.indice_original.persistir(self.ruta)
        binario = IndiceGeograficoBinario(self.ruta)
        self.assertTrue(binario.existe())

    def test_tamano_bytes_crece_con_mas_datos(self):
        """Un índice con más datos produce un archivo más grande."""
        # Índice pequeño: solo una ASADA
        indice_peq = IndiceGeografico()
        indice_peq.insertar(_asadas_ejemplo()[0], 0)
        ruta_peq = os.path.join(self.tmp, "pequeno.dat")
        indice_peq.persistir(ruta_peq)

        # Índice grande: 5 ASADAS
        self.indice_original.persistir(self.ruta)

        self.assertLess(
            IndiceGeograficoBinario(ruta_peq).tamano_bytes(),
            IndiceGeograficoBinario(self.ruta).tamano_bytes()
        )

    def test_indice_vacio_no_produce_error(self):
        """Serializar un índice vacío y luego cargarlo no lanza excepción."""
        indice_vacio = IndiceGeografico()
        indice_vacio.persistir(self.ruta)
        indice2 = IndiceGeografico()
        ok = indice2.cargar_desde_binario(self.ruta)
        # Un índice vacío puede devolver False o True con lista vacía; ambos son válidos.
        self.assertEqual(indice2.provincias(), [])


if __name__ == "__main__":
    unittest.main()
