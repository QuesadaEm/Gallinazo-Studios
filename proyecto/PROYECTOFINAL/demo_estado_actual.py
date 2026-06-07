"""
DEMO INTEGRADA (Dev A + Dev B) — estado actual del sistema.

Esto NO es el programa final (faltan sockets y GUI), pero ya ejecuta el
pipeline real de punta a punta:

    1. MotorConsulta (Dev A) lee los datos reales de ARESEP desde un JSON local
       (fixtures), los escribe en el archivo binario `data/registros.dat` y
       construye el árbol BST por id.
    2. Al regenerarse los datos, el callback `al_regenerar` dispara la
       construcción del índice geográfico de Dev B (punto de integración I3).
    3. Se consultan datos por la API de A (obtener_asada, obtener_todas) y por
       el índice geográfico de B (provincias→cantones→distritos→ASADAS).
    4. Se genera el mapa Folium con todas las ASADAS.

Ejecutar SIEMPRE desde la raíz del proyecto:

    python demo_estado_actual.py
"""

from __future__ import annotations

import os
import sys

from src.api.motor_consulta import MotorConsulta
from src.geografia.generador_mapas import GeneradorMapas
from src.geografia.indice_geografico import IndiceGeografico

RUTA_FIXTURES = os.path.join("tests", "fixtures_asadas.json")


def main() -> None:
    # Modo de datos:
    #   python demo_estado_actual.py          -> usa el fixture local (sin conexión)
    #   python demo_estado_actual.py --real   -> descarga EN VIVO desde ARESEP
    usar_real = "--real" in sys.argv
    origen = None if usar_real else RUTA_FIXTURES

    print("=" * 64)
    print(" DEMO INTEGRADA — Sistema de ASADAS (Dev A + Dev B)")
    print(f" Fuente de datos: {'ARESEP en vivo (--real)' if usar_real else 'fixture local'}")
    print("=" * 64)

    # Índice geográfico de B; se reconstruye solo cuando A regenera los datos.
    indice_geo = IndiceGeografico()

    # Motor de A. Le pasamos el callback de integración I3.
    motor = MotorConsulta(
        directorio_datos="data",
        origen_local=origen,
        al_regenerar=lambda repositorio: indice_geo.construir(repositorio),
    )

    # iniciar() sincroniza si el repositorio está vacío (dispara al_regenerar).
    motor.iniciar()

    # Si los datos ya existían de una corrida anterior, el callback no se
    # dispara; construimos el índice geográfico explícitamente para cubrir
    # también ese caso (así arrancaría el servidor con datos ya presentes).
    if not indice_geo.provincias():
        indice_geo.construir(motor.repositorio)

    # 1. API de A ----------------------------------------------------------
    todas = motor.obtener_todas()
    print(f"\n[1] MotorConsulta de A: {len(todas)} ASADAS en data/registros.dat")
    for a in todas[:4]:
        print(f"    - id {a.id_Asada}: {a.operador}  ({a.provincia} > {a.canton} > {a.distrito})")
    if len(todas) > 4:
        print(f"    ... y {len(todas) - 4} más")

    # Búsqueda puntual por id (lo que el servidor responderá por id).
    alguno = todas[0].id_Asada
    encontrada = motor.obtener_asada(alguno)
    print(f"\n[2] Búsqueda por id {alguno}: {encontrada.operador} "
          f"(posición física {motor.buscar_por_id(alguno)})")

    # 2. Índice geográfico de B -------------------------------------------
    print(f"\n[3] Índice geográfico de B: {indice_geo.total_asadas()} ASADAS indexadas")
    print("    Provincias:", indice_geo.provincias())
    prov = indice_geo.provincias()[0]
    cant = indice_geo.cantones_de(prov)[0]
    dist = indice_geo.distritos_de(prov, cant)[0]
    print(f"    Cantones de {prov}:", indice_geo.cantones_de(prov))
    print(f"    Distritos de {prov} > {cant}:", indice_geo.distritos_de(prov, cant))
    print(f"    ASADAS de {prov} > {cant} > {dist} (id, posición):",
          indice_geo.asadas_de(prov, cant, dist))

    # 3. Mapa Folium -------------------------------------------------------
    ruta_mapa = GeneradorMapas().generar_html(todas)
    print(f"\n[4] Mapa generado: {ruta_mapa}")

    print("\n" + "=" * 64)
    print(" Integración A+B OK. Falta: servidor de sockets y GUI.")
    print("=" * 64)


if __name__ == "__main__":
    main()
