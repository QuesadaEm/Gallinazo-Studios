"""Verificación del pipeline completo de integración.

Ejecutar directamente:  python tests/test_pipeline.py
No forma parte del suite unittest automático.
"""
import tempfile
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.motor_consulta import MotorConsulta
from src.geografia.indice_geografico import IndiceGeografico
from src.persistencia.indice_geografico_binario import IndiceGeograficoBinario


def main():
    with tempfile.TemporaryDirectory() as tmp:
        indice_geo = IndiceGeografico()
        ruta_geo_ref = [None]

        def al_regenerar(repo):
            ruta = os.path.join(tmp, "indice_geografico.dat")
            ruta_geo_ref[0] = ruta
            indice_geo.construir(repo)
            indice_geo.persistir(ruta)

        motor = MotorConsulta(
            directorio_datos=tmp,
            origen_local="tests/fixtures_asadas.json",
            al_regenerar=al_regenerar,
        )
        motor.iniciar()

        total = motor.repositorio.cantidad_registros()
        print(f"Registros en repositorio: {total}")
        print(f"Provincias: {indice_geo.provincias()}")
        print(f"Total ASADAS en indice: {indice_geo.total_asadas()}")

        ruta_geo = ruta_geo_ref[0] or os.path.join(tmp, "indice_geografico.dat")
        existe = os.path.exists(ruta_geo)
        print(f"3er archivo existe: {existe}")
        if existe:
            print(f"Tamano 3er archivo: {os.path.getsize(ruta_geo)} bytes")

        indice2 = IndiceGeografico()
        ok = indice2.cargar_desde_binario(ruta_geo)
        print(f"Carga desde binario OK: {ok}")
        print(f"Provincias tras carga: {indice2.provincias()}")
        print(f"Total ASADAS tras carga: {indice2.total_asadas()}")

        asada50 = motor.obtener_asada(50)
        print(f"Busqueda id=50: {asada50.operador if asada50 else 'NO ENCONTRADO'}")

        pares = indice2.asadas_de("Alajuela", "San Carlos", "Quesada")
        print(f"ASADAS en Alajuela>San Carlos>Quesada: {pares}")

        print("Pipeline completo OK")


if __name__ == "__main__":
    main()
