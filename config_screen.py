"""
Módulo: config_screen.py
Descripción: Pantalla de configuración del juego.
             Permite seleccionar el tamaño de la matriz (celdas).
             Devuelve el control a main.py cuando el jugador guarda o cancela.
"""

import pygame
from ui import Button, SelectorOpcion

# ── Colores ───────────────────────────────────────────────────────────────────
FONDO        = (30,  30,  40)
COLOR_TITULO = (255, 255, 255)
COLOR_LINEA  = (80,  80, 100)


class ConfigScreen:
    """
    Pantalla de configuración.

    Uso en main.py:
        config = ConfigScreen(pantalla, config_actual)

        # dentro del loop:
        for evento in pygame.event.get():
            resultado = config.manejar_evento(evento)
            # resultado puede ser:
            #   None          → sin cambios
            #   "guardar"     → el jugador guardó; leer config.valores
            #   "cancelar"    → volver al menú sin cambios

        config.dibujar()

    Atributos de lectura:
        config.valores  →  dict con la configuración actual, ej:
                           {"matrix_size": 20}
    """

    OPCIONES_CELDAS = [10, 20, 30]

    def __init__(self, superficie: pygame.Surface, config_actual: dict):
        """
        Args:
            superficie:     Surface principal (ventana).
            config_actual:  Dict con valores vigentes, ej. {"matrix_size": 20}
        """
        self.superficie = superficie
        ancho = superficie.get_width()
        alto  = superficie.get_height()

        # Índice inicial según config actual
        size_actual = config_actual.get("matrix_size", 20)
        idx_inicial = self.OPCIONES_CELDAS.index(size_actual) \
                      if size_actual in self.OPCIONES_CELDAS else 1

        # ── Selector de celdas ────────────────────────────────────────────────
        sel_x = ancho // 2 - 130
        sel_y = alto  // 2 - 30
        self._sel_celdas = SelectorOpcion(
            sel_x, sel_y, 260, 50,
            "Tamaño de la matriz (celdas x celdas)",
            self.OPCIONES_CELDAS,
            indice_inicial=idx_inicial,
        )

        # ── Botones ───────────────────────────────────────────────────────────
        btn_y   = alto // 2 + 80
        btn_sep = 120
        self._btn_guardar  = Button(ancho // 2 - btn_sep - 80, btn_y, 160, 50, "Guardar")
        self._btn_cancelar = Button(ancho // 2 + btn_sep - 80, btn_y, 160, 50, "Cancelar",
                                    color_normal=(100, 60, 60),
                                    color_hover  =(140, 80, 80),
                                    color_click  =(70,  40, 40))

        self._fuente_titulo: pygame.font.Font | None = None

    # ── Propiedad de lectura ──────────────────────────────────────────────────

    @property
    def valores(self) -> dict:
        """Devuelve la configuración seleccionada actualmente."""
        return {"matrix_size": self._sel_celdas.valor}

    # ── API pública ───────────────────────────────────────────────────────────

    def manejar_evento(self, evento: pygame.event.Event) -> str | None:
        """
        Procesa un evento pygame.

        Returns:
            "guardar"   → el jugador confirmó los cambios
            "cancelar"  → el jugador canceló
            None        → sin acción especial
        """
        self._sel_celdas.manejar_evento(evento)

        if self._btn_guardar.fue_clickeado(evento):
            return "guardar"
        if self._btn_cancelar.fue_clickeado(evento):
            return "cancelar"

        if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
            return "cancelar"

        return None

    def dibujar(self) -> None:
        """Dibuja la pantalla completa de configuración."""
        self.superficie.fill(FONDO)
        self._dibujar_titulo()
        self._dibujar_separador()
        self._sel_celdas.dibujar(self.superficie)
        self._btn_guardar.dibujar(self.superficie)
        self._btn_cancelar.dibujar(self.superficie)

    # ── Interno ───────────────────────────────────────────────────────────────

    def _dibujar_titulo(self) -> None:
        if self._fuente_titulo is None:
            self._fuente_titulo = pygame.font.SysFont(None, 48)
        s = self._fuente_titulo.render("Configuración", True, COLOR_TITULO)
        ancho = self.superficie.get_width()
        self.superficie.blit(s, s.get_rect(centerx=ancho // 2, y=60))

    def _dibujar_separador(self) -> None:
        ancho = self.superficie.get_width()
        alto  = self.superficie.get_height()
        pygame.draw.line(
            self.superficie, COLOR_LINEA,
            (60, alto // 2 - 80),
            (ancho - 60, alto // 2 - 80),
            width=1,
        )
