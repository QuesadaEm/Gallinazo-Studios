"""Prueba rápida de integración con datos reales de ARESEP.

Ejecutar directamente:  python tests/test_aresep_real.py
No forma parte del suite unittest automático (requiere internet).
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.motor_consulta import MotorConsulta
from src.geografia.indice_geografico import IndiceGeografico


def main():
    with tempfile.TemporaryDirectory() as tmp:
        indice_geo = IndiceGeografico()
        ruta_geo = os.path.join(tmp, "indice_geografico.dat")

        motor = MotorConsulta(
            directorio_datos=tmp,
            origen_local=None,   # descarga real de ARESEP
            al_regenerar=lambda repo: (
                indice_geo.construir(repo),
                indice_geo.persistir(ruta_geo),
            ),
        )
        print("Descargando desde ARESEP...")
        motor.iniciar()

        total = motor.repositorio.cantidad_registros()
        print(f"Registros reales descargados y persistidos: {total}")
        print(f"Provincias: {indice_geo.provincias()}")
        print(f"Total indexadas en estructura geografica: {indice_geo.total_asadas()}")

        for nombre in ("registros.dat", "indice_arbol.dat"):
            ruta = os.path.join(tmp, nombre)
            print(f"{nombre}: {os.path.getsize(ruta):,} bytes")
        print(f"indice_geografico.dat: {os.path.getsize(ruta_geo):,} bytes")

        primer_id = list(motor.repositorio.recorrer_todos())[0].id_Asada
        asada = motor.obtener_asada(primer_id)
        print(f"Busqueda id={primer_id}: {asada.operador}")
        print("OK - pipeline real completo")


if __name__ == "__main__":
    main()
