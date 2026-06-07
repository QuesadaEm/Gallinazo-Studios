"""Diagnóstico de conexión con ARESEP (ejecución manual, requiere internet).

Este script NO es parte del sistema en producción: es una herramienta de
verificación para comprobar, en una máquina con conexión, que:

1. El endpoint de ARESEP responde (código HTTP 200).
2. Qué metadatos de modificación expone (cabeceras ``Last-Modified`` / ``ETag``).
3. Cómo viene envuelto el JSON (arreglo directo o dentro de ``"d"``).
4. Cuántos registros trae.
5. Que las llaves reales del JSON coinciden con los atributos del modelo
   :class:`~src.modelo.asada.Asada`.
6. Que el flujo completo (descarga -> binario -> índice -> consulta) funciona
   de punta a punta contra los datos reales.

Uso::

    python verificar_conexion.py

Si alguna llave del JSON real no coincide con el modelo, el script lo reporta
para que se ajuste el mapeo en ``Asada.desde_dict`` antes de la entrega.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import fields

from src.api.motor_consulta import MotorConsulta
from src.ingesta.cliente_aresep import URL_ARESEP, ClienteAresep
from src.modelo.asada import Asada


def _separador(titulo: str) -> None:
    print("\n" + "=" * 70)
    print(titulo)
    print("=" * 70)


def diagnosticar() -> int:
    """Ejecuta el diagnóstico y devuelve un código de salida (0 = éxito)."""
    try:
        import requests
    except ImportError:
        print("ERROR: instale las dependencias primero -> pip install -r requirements.txt")
        return 1

    # ---- 1. Petición HTTP cruda -------------------------------------- #
    _separador("1. Petición HTTP al endpoint de ARESEP")
    print(f"URL: {URL_ARESEP}")
    try:
        respuesta = requests.get(URL_ARESEP, timeout=30)
    except requests.RequestException as error:
        print(f"FALLO la conexión: {error}")
        return 1

    print(f"Código HTTP        : {respuesta.status_code}")
    print(f"Content-Type       : {respuesta.headers.get('Content-Type')}")
    print(f"Tamaño (bytes)     : {len(respuesta.content):,}")
    print(f"Last-Modified      : {respuesta.headers.get('Last-Modified')}")
    print(f"ETag               : {respuesta.headers.get('ETag')}")
    if respuesta.status_code != 200:
        print("El endpoint no respondió 200. Revise la URL o la disponibilidad.")
        return 1

    # ---- 2. Estructura del JSON -------------------------------------- #
    _separador("2. Estructura del JSON recibido")
    cliente = ClienteAresep()
    documento = respuesta.json()
    if isinstance(documento, list):
        print("Formato: arreglo JSON directo (sin envoltorio).")
    elif isinstance(documento, dict):
        print(f"Formato: objeto JSON. Llaves de nivel superior: {list(documento.keys())}")
    registros = cliente._extraer_lista(documento)
    print(f"Cantidad de registros: {len(registros):,}")

    if not registros:
        print("No se recibieron registros.")
        return 1

    # ---- 3. Cotejo de llaves contra el modelo ------------------------ #
    _separador("3. Cotejo de llaves del JSON contra el modelo Asada")
    llaves_reales = {str(k).lower() for k in registros[0].keys()}
    campos_modelo = {f.name.lower() for f in fields(Asada)}
    print(f"Llaves del primer registro: {sorted(registros[0].keys())}")
    faltantes = campos_modelo - llaves_reales
    extras = llaves_reales - campos_modelo
    if faltantes:
        print(f"AVISO: el modelo espera estas llaves que NO vinieron: {sorted(faltantes)}")
        print("       (revise el mapeo de alias en Asada.desde_dict)")
    if extras:
        print(f"INFO : el JSON trae llaves que el modelo ignora: {sorted(extras)}")
    if not faltantes:
        print("OK: todas las llaves del modelo están presentes en el JSON real.")

    # ---- 4. Flujo completo de punta a punta -------------------------- #
    _separador("4. Flujo completo: descarga -> binario -> indice -> consulta")
    with tempfile.TemporaryDirectory() as carpeta:
        motor = MotorConsulta(directorio_datos=carpeta)
        motor.iniciar()  # descarga real y construye las estructuras
        total = motor.obtener_todas()
        print(f"Registros almacenados en binario: {len(total):,}")
        muestra = total[0]
        print(f"Ejemplo -> id_Asada={muestra.id_Asada}, "
              f"provincia='{muestra.provincia}', distrito='{muestra.distrito}'")
        # Búsqueda real por id usando el árbol cargado en memoria.
        encontrada = motor.obtener_asada(muestra.id_Asada)
        ok_busqueda = encontrada is not None and encontrada.id_Asada == muestra.id_Asada
        print(f"Búsqueda por id_Asada={muestra.id_Asada}: "
              f"{'OK' if ok_busqueda else 'FALLO'}")
        # Segunda sincronización: no debe haber cambios.
        sin_cambios = not motor.actualizar_datos()
        print(f"Segunda sincronización sin cambios: {'OK' if sin_cambios else 'REGENERO'}")

    _separador("RESULTADO")
    if ok_busqueda and not faltantes:
        print("VERIFICACIÓN EXITOSA: el sistema consume ARESEP y consulta correctamente.")
        return 0
    print("Verificación con observaciones (ver avisos arriba).")
    return 0 if ok_busqueda else 1


if __name__ == "__main__":
    sys.exit(diagnosticar())
