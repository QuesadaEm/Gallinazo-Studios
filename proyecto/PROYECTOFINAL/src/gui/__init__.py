"""Paquete de interfaz gráfica (Tkinter).

Expone las dos ventanas principales del sistema:

* :class:`~src.gui.ventana_principal.VentanaPrincipal` — GUI del servidor:
  incluye búsqueda por ID, combos dependientes, actualización de datos y
  arranque del servidor TCP.

* :class:`~src.gui.ventana_cliente.VentanaCliente` — GUI del cliente remoto:
  consultas a través del socket TCP (solo lectura).
"""

from src.gui.ventana_principal import VentanaPrincipal
from src.gui.ventana_cliente import VentanaCliente

__all__ = ["VentanaPrincipal", "VentanaCliente"]
