"""
Módulo: game_screen.py
Descripción: Renderiza la matriz del juego dentro de la ventana fija.
             La matriz se centra con un margen gris alrededor.
             Incluye botón "Menú" en el margen superior.

Imágenes:
    Al iniciar, busca automáticamente en la carpeta IMG/ los siguientes
    archivos (PNG, JPG o JPEG):

        IMG/Pasto.png          → celda libre
        IMG/Obstaculo.png      → obstáculo
        IMG/Jugador.png        → jugador
        IMG/coin_5.png        → moneda 5 pts
        IMG/coin_10.png       → moneda 10 pts
        IMG/Bomba.png          → bomba
        IMG/Fantasmas.png         → paso fantasma

    Si un archivo existe se usa la imagen; si no, se dibuja el color
    provisional definido en COLORS. Puedes mezclar: tener imagen para
    algunos elementos y color para otros.
"""

import os
import pygame
from matrix import Matrix
from ui import Button

#──Tamaño de celda────────────────────────────────────────────────────────────
CELL_SIZE = 32

#──Carpeta de IMAGENES─────────────────────────────────────────────────────────
RUTA = "IMG"

#──Nombre de archivo por valor de celda──────────────────────────────────────
ARCHIVOS_IMG: dict[int, str] = {
    Matrix.FREE:        "Pasto",
    Matrix.OBSTACLE:    "Muro",
    Matrix.PLAYER:      "Jugador",
    Matrix.COIN_5:      "coin_5",
    Matrix.COIN_10:     "coin_10",
    Matrix.POWER_BOMB:  "Bomba",
    Matrix.POWER_GHOST: "Fantasmas",
}

#──Colores de respaldo (se usan si no hay imagen)────────────────────────────
COLORS: dict[int, tuple] = {
    Matrix.FREE:        (30,  90,  30),
    Matrix.OBSTACLE:    (50,  50,  50),
    Matrix.PLAYER:      (70, 130, 230),
    Matrix.COIN_5:      (255, 215,   0),
    Matrix.COIN_10:     (255, 165,   0),
    Matrix.POWER_BOMB:  (220,  50,  50),
    Matrix.POWER_GHOST: (180,  80, 220),
}

# ── Margen alrededor de la matriz ─────────────────────────────────────────────
MARGEN_SUPERIOR = 60
MARGEN_RESTO    = 20

# ── Colores de la UI ──────────────────────────────────────────────────────────
COLOR_MARGEN = (70, 70, 80)
COLOR_BORDE  = (100, 100, 115)


def _buscar_imagen(nombre_base: str) -> str | None:
    """
    Busca en RUTA un archivo llamado nombre_base con extensión
    .png, .jpg o .jpeg (en ese orden de preferencia).

    Returns:
        Ruta completa si existe, None si no se encuentra ninguna.
    """
    for ext in ("png", "jpg", "jpeg"):
        ruta = os.path.join(RUTA, f"{nombre_base}.{ext}")
        if os.path.isfile(ruta):
            return ruta
    return None


def _cargar_imagenes() -> dict[int, pygame.Surface | None]:
    """
    Intenta cargar todas las imágenes definidas en ARCHIVOS_IMG.
    Muestra en consola qué encontró y qué usará color de respaldo.

    Returns:
        Dict valor_celda -> Surface (o None si no se encontró imagen).
    """
    imagenes: dict[int, pygame.Surface | None] = {}

    for valor, nombre in ARCHIVOS_IMG.items():
        ruta = _buscar_imagen(nombre)
        if ruta:
            try:
                img = pygame.image.load(ruta).convert_alpha()
                imagenes[valor] = pygame.transform.scale(img, (CELL_SIZE, CELL_SIZE))
                print(f"  ✔ imagen cargada : {ruta}")
            except pygame.error as e:
                imagenes[valor] = None
                print(f"  ✘ error al cargar {ruta}: {e}  → usando color")
        else:
            imagenes[valor] = None
            print(f"  · sin imagen     : {RUTA}/{nombre}.[png|jpg]  → usando color")

    return imagenes


class GameScreen:
    """
    Renderiza la matriz con margen gris y botón 'Menú'.

    Al instanciarse, carga automáticamente las imágenes disponibles
    en IMG/. No hace falta llamar a cargar_imagen() manualmente
    salvo que quieras reemplazar una imagen en tiempo de ejecución.

    Uso en main.py:
        game_screen = GameScreen(matrix, pantalla, matrix_size)

        # loop de eventos:
        resultado = game_screen.manejar_evento(evento)
        if resultado == "menu": ...

        # loop de dibujo:
        game_screen.dibujar()
    """

    def __init__(self, matrix: Matrix, superficie: pygame.Surface, matrix_size: int):
        self.matrix      = matrix
        self.superficie  = superficie
        self.cell        = CELL_SIZE
        self.lado_matriz = matrix_size * CELL_SIZE

        self.offset_x = MARGEN_RESTO
        self.offset_y = MARGEN_SUPERIOR

        # Cargar imágenes automáticamente al crear la pantalla
        print("GameScreen: buscando imágenes en IMG/...")
        self._images = _cargar_imagenes()

        self._btn_menu = Button(
            12, 10, 110, 38, "◀  Menú",
            color_normal=(80,  80,  95),
            color_hover =(110, 110, 130),
            color_click =(50,  50,  65),
            radio_borde=6,
        )

    # ── Estático ──────────────────────────────────────────────────────────────

    @staticmethod
    def calcular_tamanio_ventana(matrix_size: int) -> tuple[int, int]:
        """Devuelve (ancho, alto) exactos para la ventana con esta matriz."""
        lado  = matrix_size * CELL_SIZE
        ancho = MARGEN_RESTO + lado + MARGEN_RESTO
        alto  = MARGEN_SUPERIOR + lado + MARGEN_RESTO
        return ancho, alto

    # ── API pública ───────────────────────────────────────────────────────────

    def actualizar_superficie(self, nueva_superficie: pygame.Surface) -> None:
        """Actualiza la referencia a la ventana tras un resize."""
        self.superficie = nueva_superficie

    def manejar_evento(self, evento: pygame.event.Event) -> str | None:
        """Devuelve 'menu' si se presionó el botón Menú."""
        if self._btn_menu.fue_clickeado(evento):
            return "menu"
        return None

    def dibujar(self) -> None:
        """Dibuja margen + matriz + botón."""
        self.superficie.fill(COLOR_MARGEN)

        rect_borde = pygame.Rect(
            self.offset_x - 2,
            self.offset_y - 2,
            self.lado_matriz + 4,
            self.lado_matriz + 4,
        )
        pygame.draw.rect(self.superficie, COLOR_BORDE, rect_borde, border_radius=3)

        snapshot = self.matrix.get_snapshot()
        for fila_idx, fila in enumerate(snapshot):
            for col_idx, valor in enumerate(fila):
                self._dibujar_celda(fila_idx, col_idx, valor)

        self._btn_menu.dibujar(self.superficie)

    def cargar_imagen(self, valor_celda: int, ruta: str) -> None:
        """
        Carga (o reemplaza) la imagen de un tipo de celda en tiempo de ejecución.

        Args:
            valor_celda: Constante de Matrix (ej. Matrix.OBSTACLE).
            ruta:        Ruta al archivo de imagen.
        """
        imagen = pygame.image.load(ruta).convert_alpha()
        self._images[valor_celda] = pygame.transform.scale(imagen, (self.cell, self.cell))

    def recargar_imagenes(self) -> None:
        """Vuelve a escanear IMG/ y recarga todas las imágenes."""
        print("GameScreen: recargando imágenes...")
        self._images = _cargar_imagenes()

    # ── Interno ───────────────────────────────────────────────────────────────

    def _dibujar_celda(self, fila: int, col: int, valor: int) -> None:
        x    = self.offset_x + col  * self.cell
        y    = self.offset_y + fila * self.cell
        rect = pygame.Rect(x, y, self.cell, self.cell)

        # 1. Dibujar siempre el suelo (FREE) como fondo de la celda
        img_free = self._images.get(Matrix.FREE)
        if img_free:
            self.superficie.blit(img_free, rect)
        else:
            pygame.draw.rect(self.superficie, COLORS[Matrix.FREE], rect)

        # 2. Si la celda tiene un elemento encima, dibujarlo sobre el suelo
        if valor != Matrix.FREE:
            imagen = self._images.get(valor)
            if imagen:
                self.superficie.blit(imagen, rect)
            else:
                color = COLORS.get(valor, (255, 0, 255))
                pygame.draw.rect(self.superficie, color, rect)