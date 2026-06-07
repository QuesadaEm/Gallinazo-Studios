"""Punto de entrada del SERVIDOR con interfaz gráfica.

Levanta la :class:`~src.gui.ventana_principal.VentanaPrincipal`, que internamente:

1. Inicializa el :class:`~src.api.motor_consulta.MotorConsulta` (archivos
   binarios + árbol BST).
2. Construye el :class:`~src.geografia.indice_geografico.IndiceGeografico`
   (listas enlazadas en memoria + persiste ``data/indice_geografico.dat``).
3. Arranca el servidor TCP en un hilo demonio para atender clientes remotos.
4. Muestra la GUI con búsqueda por ID, combos dependientes y mapa.

**Por defecto descarga los datos reales desde ARESEP.**
Usa ``--local`` solo para desarrollo sin conexión a internet.

Uso (desde la raíz del proyecto)::

    python -m src.main_servidor              # descarga EN VIVO desde ARESEP (predeterminado)
    python -m src.main_servidor 5001         # puerto personalizado
    python -m src.main_servidor 0.0.0.0 5001
    python -m src.main_servidor --local      # 8 registros del fixture (sin internet)
    python -m src.main_servidor --consola    # modo CLI sin GUI (diagnóstico)
"""

from __future__ import annotations

import os
import sys

# Solo se usa con --local (desarrollo sin conexión a internet).
RUTA_FIXTURES = os.path.join("tests", "fixtures_asadas.json")


def _modo_consola(usar_local: bool, host: str, port: int) -> None:
    """Arranca el servidor TCP sin GUI (útil para diagnóstico o entornos sin pantalla)."""
    from src.api.motor_consulta import MotorConsulta
    from src.geografia.indice_geografico import IndiceGeografico
    from src.red.servidor import Servidor

    origen = RUTA_FIXTURES if usar_local else None
    indice_geo = IndiceGeografico()
    motor = MotorConsulta(
        directorio_datos="data",
        origen_local=origen,
        al_regenerar=lambda repo: (
            indice_geo.construir(repo),
            indice_geo.persistir(motor.ruta_indice_geo),
        ),
    )

    fuente = "fixture local (8 registros)" if usar_local else "ARESEP en vivo"
    print(f"Cargando datos desde {fuente}...")
    motor.iniciar()
    if not indice_geo.provincias():
        if not indice_geo.cargar_desde_binario(motor.ruta_indice_geo):
            indice_geo.construir(motor.repositorio)
            indice_geo.persistir(motor.ruta_indice_geo)
    print(f"Listo: {motor.repositorio.cantidad_registros()} ASADAS | "
          f"{indice_geo.total_asadas()} indexadas.")

    servidor = Servidor(motor, indice_geo, host=host, port=port)
    print(f"Servidor TCP escuchando en {host}:{port}  (Ctrl+C para detener)")
    try:
        servidor.iniciar()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        servidor.detener()


def main() -> None:
    """Punto de entrada principal del servidor.

    Por defecto descarga de ARESEP. Pasa ``--local`` para usar el fixture
    de 8 registros (sin necesidad de internet).
    """
    args_raw   = sys.argv[1:]
    usar_local = "--local" in args_raw   # solo para desarrollo sin internet
    modo_cli   = "--consola" in args_raw
    # --real queda como alias sin efecto (ya es el comportamiento por defecto)
    args = [a for a in args_raw if not a.startswith("--")]

    host = args[0] if len(args) >= 1 else "0.0.0.0"
    port = int(args[1]) if len(args) >= 2 else 5000

    if modo_cli:
        _modo_consola(usar_local, host, port)
        return

    # Modo GUI (predeterminado)
    from src.gui.ventana_principal import VentanaPrincipal

    origen = RUTA_FIXTURES if usar_local else None
    app = VentanaPrincipal(
        directorio_datos="data",
        host=host,
        port=port,
        origen_local=origen,
    )
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
