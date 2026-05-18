"""
Módulo: game_screen.py
Descripción: Renderiza la matriz del juego dentro de la ventana fija.
             La matriz se centra con un margen gris alrededor.
             El margen superior incluye botón "Menú" y panel de info
             (puntaje, bombas, fantasmas, velocidad de scroll).

Imágenes:
    Al iniciar, busca automáticamente en la carpeta IMG/ los siguientes
    archivos (PNG, JPG o JPEG):

        IMG/Suelo.png       → celda libre
        IMG/Muro.png        → obstáculo
        IMG/Jugador.png     → jugador
        IMG/coin_5.png      → moneda 5 pts
        IMG/coin_10.png     → moneda 10 pts
        IMG/Bomba.png       → bomba
        IMG/Fantasmas.png   → paso fantasma

    Si un archivo existe se usa la imagen; si no, se dibuja el color
    provisional definido en COLORS.
"""

import os
import pygame
from matrix import Matrix
from ui import Button

# ── Tamaño de celda ───────────────────────────────────────────────────────────
CELL_SIZE = 32

# ── Carpeta de imágenes ───────────────────────────────────────────────────────
RUTA = "IMG"

# ── Nombre de archivo por valor de celda ─────────────────────────────────────
ARCHIVOS_IMG: dict[int, str] = {
    Matrix.FREE:        "Suelo",
    Matrix.OBSTACLE:    "Muro",
    Matrix.PLAYER:      "Jugador",
    Matrix.COIN_5:      "coin_5",
    Matrix.COIN_10:     "coin_10",
    Matrix.POWER_BOMB:  "Bomba",
    Matrix.POWER_GHOST: "Fantasmas",
}

# ── Imágenes direccionales del jugador ───────────────────────────────────────
ARCHIVOS_JUGADOR_DIR: dict[str, str] = {
    'up':    "ARRIBA",
    'down':  "ABAJO",
    'left':  "IZQUIERDA",
    'right': "DERECHA",
}

# ── Colores de respaldo ───────────────────────────────────────────────────────
COLORS: dict[int, tuple] = {
    Matrix.FREE:        (30,  90,  30),
    Matrix.OBSTACLE:    (50,  50,  50),
    Matrix.PLAYER:      (70, 130, 230),
    Matrix.COIN_5:      (255, 215,   0),
    Matrix.COIN_10:     (255, 165,   0),
    Matrix.POWER_BOMB:  (220,  50,  50),
    Matrix.POWER_GHOST: (180,  80, 220),
}

# ── Márgenes ──────────────────────────────────────────────────────────────────
MARGEN_SUPERIOR = 60
MARGEN_RESTO    = 20

# ── Colores de la UI ──────────────────────────────────────────────────────────
COLOR_MARGEN    = (70,  70,  80)
COLOR_BORDE     = (100, 100, 115)
COLOR_INFO_TEXT = (220, 220, 220)
COLOR_INFO_VAL  = (255, 220,  80)
COLOR_ICON_BG   = (50,  50,  62)


def _buscar_imagen(nombre_base: str) -> str | None:
    for ext in ("png", "jpg", "jpeg"):
        ruta = os.path.join(RUTA, f"{nombre_base}.{ext}")
        if os.path.isfile(ruta):
            return ruta
    return None


def _cargar_imagenes() -> dict[int, pygame.Surface | None]:
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


def _cargar_imagenes_jugador() -> dict[str, pygame.Surface | None]:
    """Carga ARRIBA/ABAJO/IZQUIERDA/DERECHA.png para el jugador direccional."""
    imgs: dict[str, pygame.Surface | None] = {}
    for direccion, nombre in ARCHIVOS_JUGADOR_DIR.items():
        ruta = _buscar_imagen(nombre)
        if ruta:
            try:
                img = pygame.image.load(ruta).convert_alpha()
                imgs[direccion] = pygame.transform.scale(img, (CELL_SIZE, CELL_SIZE))
                print(f"  ✔ imagen jugador : {ruta}")
            except pygame.error as e:
                imgs[direccion] = None
                print(f"  ✘ error al cargar {ruta}: {e}  → usando imagen base")
        else:
            imgs[direccion] = None
            print(f"  · sin imagen     : {RUTA}/{nombre}.[png|jpg]  → usando imagen base")
    return imgs


class GameScreen:
    """
    Renderiza la matriz con margen gris, panel de info y botón 'Menú'.

    El panel de info ocupa el margen superior junto al botón Menú:
        [ Menú]   Puntaje: 0   💣 0   👻 0   ⚡ 2.0s

    Uso en main.py:
        game_screen = GameScreen(matrix, pantalla, matrix_size)

        # pasar el status del Game en cada frame:
        game_screen.actualizar_status(game.get_status())

        resultado = game_screen.manejar_evento(evento)
        if resultado == "menu": ...

        game_screen.dibujar()
    """

    def __init__(self, matrix: Matrix, superficie: pygame.Surface, matrix_size: int):
        self.matrix      = matrix
        self.superficie  = superficie
        self.cell        = CELL_SIZE
        self.lado_matriz = matrix_size * CELL_SIZE

        self.offset_x = MARGEN_RESTO
        self.offset_y = MARGEN_SUPERIOR

        # Estado de la UI de info (se actualiza desde main.py)
        self._status: dict = {
            'score':      0,
            'bombs':      0,
            'ghosts':     0,
            'interval':   2.0,
            'state':      'running',
            'player_pos': None,
            'facing':     'up',
        }

        print("GameScreen: buscando imágenes en IMG/...")
        self._images = _cargar_imagenes()
        self._images_jugador = _cargar_imagenes_jugador()

        self._btn_menu = Button(
            12, 10, 110, 38, "⏸  Menú",
            color_normal=(80,  80,  95),
            color_hover =(110, 110, 130),
            color_click =(50,  50,  65),
            radio_borde=6,
        )

        self._fuente_info:  pygame.font.Font | None = None
        self._fuente_label: pygame.font.Font | None = None

    # ── Estático ──────────────────────────────────────────────────────────────

    @staticmethod
    def calcular_tamanio_ventana(matrix_size: int) -> tuple[int, int]:
        """Devuelve (ancho, alto) exactos para la ventana con esta matriz."""
        lado  = matrix_size * CELL_SIZE
        ancho = MARGEN_RESTO + lado + MARGEN_RESTO
        alto  = MARGEN_SUPERIOR + lado + MARGEN_RESTO
        return ancho, alto

    # ── API pública ───────────────────────────────────────────────────────────

    def actualizar_status(self, status: dict) -> None:
        """
        Recibe el dict de get_status() del Game y actualiza el panel de info.

        Args:
            status (dict): {'score', 'bombs', 'ghosts', 'interval', 'state', ...}
        """
        self._status = status

    def actualizar_superficie(self, nueva_superficie: pygame.Surface) -> None:
        self.superficie = nueva_superficie

    def manejar_evento(self, evento: pygame.event.Event) -> str | None:
        """Devuelve 'menu' si se presionó el botón Menú."""
        if self._btn_menu.fue_clickeado(evento):
            return "menu"
        return None

    def dibujar(self) -> None:
        """Dibuja margen + panel de info + matriz + jugador + botón."""
        self.superficie.fill(COLOR_MARGEN)
        self._dibujar_borde_matriz()
        self._dibujar_matriz()
        self._dibujar_jugador()
        self._btn_menu.dibujar(self.superficie)
        self._dibujar_panel_info()

    def cargar_imagen(self, valor_celda: int, ruta: str) -> None:
        imagen = pygame.image.load(ruta).convert_alpha()
        self._images[valor_celda] = pygame.transform.scale(imagen, (self.cell, self.cell))

    def recargar_imagenes(self) -> None:
        print("GameScreen: recargando imágenes...")
        self._images = _cargar_imagenes()
        self._images_jugador = _cargar_imagenes_jugador()

    # ── Interno — dibujo ──────────────────────────────────────────────────────

    def _dibujar_borde_matriz(self) -> None:
        rect_borde = pygame.Rect(
            self.offset_x - 2,
            self.offset_y - 2,
            self.lado_matriz + 4,
            self.lado_matriz + 4,
        )
        pygame.draw.rect(self.superficie, COLOR_BORDE, rect_borde, border_radius=3)

    def _dibujar_matriz(self) -> None:
        snapshot = self.matrix.get_snapshot()
        for fila_idx, fila in enumerate(snapshot):
            for col_idx, valor in enumerate(fila):
                # PLAYER(2) ya no se guarda en la matriz; se dibuja aparte
                dibujar_valor = valor if valor != Matrix.PLAYER else Matrix.FREE
                self._dibujar_celda(fila_idx, col_idx, dibujar_valor)

    def _dibujar_celda(self, fila: int, col: int, valor: int) -> None:
        x    = self.offset_x + col  * self.cell
        y    = self.offset_y + fila * self.cell
        rect = pygame.Rect(x, y, self.cell, self.cell)

        # Suelo siempre de fondo
        img_free = self._images.get(Matrix.FREE)
        if img_free:
            self.superficie.blit(img_free, rect)
        else:
            pygame.draw.rect(self.superficie, COLORS[Matrix.FREE], rect)

        # Elemento encima del suelo
        if valor != Matrix.FREE:
            imagen = self._images.get(valor)
            if imagen:
                self.superficie.blit(imagen, rect)
            else:
                color = COLORS.get(valor, (255, 0, 255))
                pygame.draw.rect(self.superficie, color, rect)


    def _dibujar_jugador(self) -> None:
        """
        Dibuja al jugador usando player_pos del status.
        Al estar desacoplado de la matriz, siempre se dibuja correctamente
        sin importar qué ocurrió durante el scroll.
        """
        pos = self._status.get('player_pos')
        if pos is None:
            return
        fila, col = pos
        x    = self.offset_x + col  * self.cell
        y    = self.offset_y + fila * self.cell
        rect = pygame.Rect(x, y, self.cell, self.cell)

        # Fondo (suelo) debajo del jugador
        img_free = self._images.get(Matrix.FREE)
        if img_free:
            self.superficie.blit(img_free, rect)
        else:
            pygame.draw.rect(self.superficie, COLORS[Matrix.FREE], rect)

        # Imagen o color del jugador — prioridad: direccional > base > color
        facing = self._status.get('facing', 'up')
        imagen = self._images_jugador.get(facing) or self._images.get(Matrix.PLAYER)
        if imagen:
            self.superficie.blit(imagen, rect)
        else:
            pygame.draw.rect(self.superficie, COLORS[Matrix.PLAYER], rect)

    def _dibujar_panel_info(self) -> None:
        """
        Dibuja el panel de información en el margen superior.
        Layout:  [◀ Menú]  |  Pts: 999  💣 x2  👻 x1  ⚡ 1.8s
        El botón Menú ya se dibujó; aquí añadimos los indicadores.
        """
        if self._fuente_info is None:
            self._fuente_info  = pygame.font.SysFont(["segoeuisymbol", "arial"], 26)
            self._fuente_label = pygame.font.SysFont(["segoeuisymbol", "arial"], 20)

        score   = self._status.get('score',    0)
        bombs   = self._status.get('bombs',    0)
        ghosts  = self._status.get('ghosts',   0)
        interval= self._status.get('interval', 2.0)

        # Definir los bloques de info con su color de valor
        bloques = [
            ("PTS",  f"{score}",          COLOR_INFO_VAL),
            ("💣",   f"x{bombs}",         (220,  80,  80)),
            ("👻",   f"x{ghosts}",        (180,  80, 220)),
            ("⚡",   f"{interval:.1f}s",  (80,  200, 120)),
        ]

        x = 140   # empieza después del botón Menú
        y_center = MARGEN_SUPERIOR // 2  # centro vertical del margen

        for label, valor, color_val in bloques:
            # Fondo pill
            bloque_ancho = 78
            pill_rect = pygame.Rect(x, y_center - 14, bloque_ancho, 28)
            pygame.draw.rect(self.superficie, COLOR_ICON_BG, pill_rect, border_radius=6)

            # Label pequeño arriba-izquierda dentro del pill
            s_label = self._fuente_label.render(label, True, COLOR_INFO_TEXT)
            self.superficie.blit(s_label, (x + 6, y_center - 12))

            # Valor a la derecha
            s_val = self._fuente_info.render(valor, True, color_val)
            val_rect = s_val.get_rect(midright=(x + bloque_ancho - 6, y_center + 4))
            self.superficie.blit(s_val, val_rect)

            x += bloque_ancho + 6