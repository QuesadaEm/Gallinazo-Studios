"""
Módulo: game_screen.py
Descripción: Renderiza la matriz del juego dentro de la ventana fija.
             La matriz se centra con un margen gris alrededor.
             Incluye botón "Menú" en el margen superior.
"""

import pygame
from matrix import Matrix
from ui import Button

# ── Tamaño de celda ────────────────────────────────────────────────────────────
CELL_SIZE = 32

# ── Margen alrededor de la matriz ─────────────────────────────────────────────
MARGEN_SUPERIOR = 60   # espacio para el botón "Menú"
MARGEN_RESTO    = 20   # izquierda, derecha, abajo

# ── Colores ────────────────────────────────────────────────────────────────────
COLOR_MARGEN = (70, 70, 80)     # gris del margen
COLOR_BORDE  = (100, 100, 115)  # borde fino alrededor de la matriz

COLORS = {
    Matrix.FREE:        (50,  50,  50),
    Matrix.OBSTACLE:    (30,  90,  30),
    Matrix.PLAYER:      (70, 130, 230),
    Matrix.COIN_5:      (255, 215,   0),
    Matrix.COIN_10:     (255, 165,   0),
    Matrix.POWER_BOMB:  (220,  50,  50),
    Matrix.POWER_GHOST: (180,  80, 220),
}

IMAGES: dict[int, pygame.Surface | None] = {k: None for k in COLORS}


class GameScreen:
    """
    Renderiza la matriz centrada dentro de la ventana fija, con margen gris
    y botón 'Menú' en la barra superior.

    Uso en main.py:
        game_screen = GameScreen(matrix, pantalla, matrix_size)

        # en el loop de eventos:
        resultado = game_screen.manejar_evento(evento)
        if resultado == "menu": ...

        # en el loop de dibujo:
        game_screen.dibujar()
    """

    def __init__(self, matrix: Matrix, superficie: pygame.Surface, matrix_size: int):
        self.matrix      = matrix
        self.superficie  = superficie
        self.cell        = CELL_SIZE
        self.lado_matriz = matrix_size * CELL_SIZE

        # Offsets fijos: margen izquierdo y superior
        self.offset_x = MARGEN_RESTO
        self.offset_y = MARGEN_SUPERIOR

        # Botón "Menú" en la esquina superior izquierda del margen
        self._btn_menu = Button(12, 10, 110, 38, "◀  Menú",
                                color_normal=(80, 80, 95),
                                color_hover =(110, 110, 130),
                                color_click =(50,  50,  65),
                                radio_borde=6)

    @staticmethod
    def calcular_tamanio_ventana(matrix_size: int) -> tuple[int, int]:
        """
        Devuelve (ancho, alto) exactos para la ventana con esta matriz.

        Usar en main.py ANTES de crear GameScreen:
            ancho, alto = GameScreen.calcular_tamanio_ventana(size)
            pantalla = pygame.display.set_mode((ancho, alto))
        """
        lado  = matrix_size * CELL_SIZE
        ancho = MARGEN_RESTO + lado + MARGEN_RESTO
        alto  = MARGEN_SUPERIOR + lado + MARGEN_RESTO
        return ancho, alto

    def actualizar_superficie(self, nueva_superficie: pygame.Surface) -> None:
        """Actualiza la referencia a la ventana tras un resize."""
        self.superficie = nueva_superficie

    # ── API pública ───────────────────────────────────────────────────────────

    def manejar_evento(self, evento: pygame.event.Event) -> str | None:
        """
        Procesa eventos. Devuelve "menu" si se presionó el botón Menú.
        """
        if self._btn_menu.fue_clickeado(evento):
            return "menu"
        return None

    def dibujar(self) -> None:
        """Dibuja margen + matriz + botón."""
        # 1. Fondo del margen (cubre toda la ventana)
        self.superficie.fill(COLOR_MARGEN)

        # 2. Rectángulo negro de fondo de la matriz
        rect_matriz = pygame.Rect(
            self.offset_x - 2,
            self.offset_y - 2,
            self.lado_matriz + 4,
            self.lado_matriz + 4,
        )
        pygame.draw.rect(self.superficie, COLOR_BORDE, rect_matriz, border_radius=3)

        # 3. Celdas
        snapshot = self.matrix.get_snapshot()
        for fila_idx, fila in enumerate(snapshot):
            for col_idx, valor in enumerate(fila):
                self._dibujar_celda(fila_idx, col_idx, valor)

        # 4. Botón menú encima de todo
        self._btn_menu.dibujar(self.superficie)

    def cargar_imagen(self, valor_celda: int, ruta: str) -> None:
        """
        Carga una imagen para un tipo de celda y la escala a CELL_SIZE.

        Ejemplo:
            game_screen.cargar_imagen(Matrix.OBSTACLE, "assets/wall.png")
        """
        imagen = pygame.image.load(ruta).convert_alpha()
        IMAGES[valor_celda] = pygame.transform.scale(imagen, (self.cell, self.cell))

    # ── Interno ───────────────────────────────────────────────────────────────

    def _dibujar_celda(self, fila: int, col: int, valor: int) -> None:
        x = self.offset_x + col  * self.cell
        y = self.offset_y + fila * self.cell
        rect = pygame.Rect(x, y, self.cell, self.cell)

        imagen = IMAGES.get(valor)
        if imagen:
            self.superficie.blit(imagen, rect)
        else:
            color = COLORS.get(valor, (255, 0, 255))
            pygame.draw.rect(self.superficie, color, rect)
