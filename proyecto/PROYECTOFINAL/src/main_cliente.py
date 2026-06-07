"""Punto de entrada del CLIENTE con interfaz gráfica.

Lanza la :class:`~src.gui.ventana_cliente.VentanaCliente`, que permite conectarse
a un servidor TCP remoto y realizar consultas de ASADAS:

* Búsqueda por ID (consulta al servidor por socket).
* Navegación geográfica con combos dependientes (Provincia → Cantón → Distrito).
* Visualización en mapa de las ASADAS del distrito seleccionado.

El cliente es de solo lectura: no puede actualizar los datos del sistema.

Uso::

    python -m src.main_cliente              # abre la GUI (modo predeterminado)
    python -m src.main_cliente --consola    # menú de texto en terminal
    python -m src.main_cliente --consola 192.168.1.10 5000
"""

from __future__ import annotations

import sys

from src.geografia.generador_mapas import GeneradorMapas
from src.modelo.asada import Asada
from src.red.cliente import Cliente, ErrorConsulta


# ------------------------------------------------------------------ #
# Modo consola (texto, sin Tkinter) — para pruebas o entornos sin GUI #
# ------------------------------------------------------------------ #

def _elegir(titulo: str, opciones: list):
    """Menú numerado de texto; devuelve la opción elegida o None."""
    if not opciones:
        print("  (sin resultados)")
        return None
    print(titulo)
    for i, op in enumerate(opciones, 1):
        print(f"  {i}. {op}")
    try:
        idx = int(input("Elegí un número (0 para volver): "))
    except ValueError:
        return None
    return opciones[idx - 1] if 1 <= idx <= len(opciones) else None


def _explorar_consola(cli: Cliente) -> None:
    """Navega la jerarquía política y muestra ASADAS en consola."""
    provincia = _elegir("Provincias:", cli.provincias())
    if not provincia:
        return
    canton = _elegir(f"Cantones de {provincia}:", cli.cantones(provincia))
    if not canton:
        return
    distrito = _elegir(f"Distritos de {canton}:", cli.distritos(provincia, canton))
    if not distrito:
        return
    registros = cli.asadas(provincia, canton, distrito)
    print(f"\nASADAS en {provincia} > {canton} > {distrito}:")
    for r in sorted(registros, key=lambda x: x.get("id_Asada", 0)):
        print(f"  - id {r['id_Asada']}: {r['operador']}")
    if registros and input("\n¿Ver en el mapa? (s/n): ").lower().startswith("s"):
        asadas = [Asada.desde_dict(r) for r in registros]
        ruta = GeneradorMapas().generar_html(asadas, "consulta.html")
        GeneradorMapas.abrir_en_navegador(ruta)
        print(f"Mapa abierto: {ruta}")


def _modo_consola(host: str, port: int) -> None:
    """Menú de texto interactivo conectado al servidor."""
    print(f"Conectando a {host}:{port} ...")
    try:
        with Cliente(host, port) as cli:
            print("Conectado.\n")
            while True:
                print("\n=== MENÚ CLIENTE ===")
                print("1. Buscar ASADA por id")
                print("2. Explorar por división política")
                print("3. Salir")
                opcion = input("Opción: ").strip()
                if opcion == "1":
                    try:
                        id_asada = int(input("ID de la ASADA: "))
                        r = cli.por_id(id_asada)
                        print(f"  id {r['id_Asada']}: {r['operador']} "
                              f"({r['provincia']} > {r['canton']} > {r['distrito']})")
                    except (ValueError, ErrorConsulta) as e:
                        print(f"  Error: {e}")
                elif opcion == "2":
                    try:
                        _explorar_consola(cli)
                    except ErrorConsulta as e:
                        print(f"  Error: {e}")
                elif opcion == "3":
                    break
                else:
                    print("  Opción inválida.")
    except OSError as e:
        print(f"No se pudo conectar al servidor: {e}")


# ------------------------------------------------------------------ #
# Punto de entrada                                                    #
# ------------------------------------------------------------------ #

def main() -> None:
    """Lanza el cliente (GUI por defecto, consola con --consola)."""
    args_raw  = sys.argv[1:]
    modo_cli  = "--consola" in args_raw
    args = [a for a in args_raw if not a.startswith("--")]

    if modo_cli:
        host = args[0] if len(args) >= 1 else "127.0.0.1"
        port = int(args[1]) if len(args) >= 2 else 5000
        _modo_consola(host, port)
        return

    # Modo GUI (predeterminado)
    from src.gui.ventana_cliente import VentanaCliente

    app = VentanaCliente()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
