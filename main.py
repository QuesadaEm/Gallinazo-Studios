import emoji

"""
main.py — Punto de entrada y controlador de estados del juego.

Estados:
    ESTADO_MENU      → menú principal
    ESTADO_JUEGO     → partida en curso
    ESTADO_GAMEOVER  → pantalla de game over / ingreso de nombre
    ESTADO_CONFIG    → pantalla de configuración
"""

import pygame
from ui import Button
from game import Game
from game_screen import GameScreen
from config_screen import ConfigScreen

# ── Ventana del menú (fija) ───────────────────────────────────────────────────
ANCHO_MENU  = 700
ALTO_MENU   = 700
FPS         = 60
TITULO      = "Mi Juego"
GRIS_OSCURO = (40, 40, 40)

# ── Paleta game over ──────────────────────────────────────────────────────────
COLOR_GO_FONDO   = (20,  20,  30)
COLOR_GO_TITULO  = (230,  60,  60)
COLOR_GO_TEXTO   = (200, 200, 200)
COLOR_GO_NOMBRE  = (255, 255, 255)
COLOR_GO_INPUT   = (50,  50,  65)
COLOR_GO_BORDE   = (100, 100, 130)

# ── Configuración del juego ───────────────────────────────────────────────────
config = {"matrix_size": 20}

# ── Fondo del menú ────────────────────────────────────────────────────────────
def _cargar_fondo_menu() -> pygame.Surface | None:
    """Busca FondoMenu.png/jpg en IMG/ y lo devuelve escalado al menú."""
    import os
    for ext in ("png", "jpg", "jpeg"):
        ruta = os.path.join("IMG", f"FondoMenu.{ext}")
        if os.path.isfile(ruta):
            try:
                img = pygame.image.load(ruta).convert()
                img = pygame.transform.scale(img, (ANCHO_MENU, ALTO_MENU))
                print(f"  ✔ fondo menú     : {ruta}")
                return img
            except pygame.error as e:
                print(f"  ✘ error fondo menú: {e}")
    print("  · sin imagen     : IMG/FondoMenu.[png|jpg]  → usando color")
    return None

# ── Estados ───────────────────────────────────────────────────────────────────
ESTADO_MENU     = "menu"
ESTADO_JUEGO    = "juego"
ESTADO_GAMEOVER = "gameover"
ESTADO_CONFIG   = "config"


# ─────────────────────────────────────────────────────────────────────────────
# Pantalla de Game Over
# ─────────────────────────────────────────────────────────────────────────────

class GameOverScreen:
    """
    Pantalla de fin de partida.

    Muestra el puntaje final, solicita el nombre del jugador y permite
    guardar el puntaje o volver al menú sin guardar.

    Uso:
        go = GameOverScreen(pantalla, game)
        resultado = go.manejar_evento(evento)
        # resultado: "guardado" | "menu" | None
        go.dibujar()
    """

    MAX_NOMBRE = 20

    def __init__(self, superficie: pygame.Surface, game: Game):
        self.superficie = superficie
        self.game       = game

        self.nombre: str   = ""
        self._guardado     = False
        self._pos_ranking  = 0

        ancho = superficie.get_width()
        alto  = superficie.get_height()

        cx = ancho // 2
        self._btn_guardar = Button(cx - 170, alto // 2 + 120, 150, 46, "Guardar",
                                   color_normal=(50, 120, 50),
                                   color_hover =(70, 160, 70),
                                   color_click =(30,  80, 30))
        self._btn_menu    = Button(cx +  20, alto // 2 + 120, 150, 46, "Menú",
                                   color_normal=(80,  80,  95),
                                   color_hover =(110, 110, 130),
                                   color_click =(50,  50,  65))

        self._fuente_titulo: pygame.font.Font | None = None
        self._fuente_texto:  pygame.font.Font | None = None
        self._fuente_input:  pygame.font.Font | None = None

    # ── API pública ───────────────────────────────────────────────────────────

    def manejar_evento(self, evento: pygame.event.Event) -> str | None:
        # Input de nombre (solo si aún no guardó)
        if not self._guardado and evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_BACKSPACE:
                self.nombre = self.nombre[:-1]
            elif evento.key == pygame.K_RETURN:
                return self._intentar_guardar()
            elif len(self.nombre) < self.MAX_NOMBRE:
                # Solo letras, números y espacios
                if evento.unicode.isprintable() and evento.unicode != "":
                    self.nombre += evento.unicode

        if not self._guardado and self._btn_guardar.fue_clickeado(evento):
            return self._intentar_guardar()

        if self._btn_menu.fue_clickeado(evento):
            return "menu"

        return None

    def dibujar(self) -> None:
        self._init_fuentes()
        ancho = self.superficie.get_width()
        alto  = self.superficie.get_height()
        cx    = ancho // 2

        self.superficie.fill(COLOR_GO_FONDO)

        # Título
        s = self._fuente_titulo.render("¡GAME OVER!", True, COLOR_GO_TITULO)
        self.superficie.blit(s, s.get_rect(centerx=cx, y=60))

        # Puntaje
        score = self.game.player.score
        s = self._fuente_texto.render(f"Puntaje final: {score}", True, COLOR_GO_TEXTO)
        self.superficie.blit(s, s.get_rect(centerx=cx, y=140))

        if self._guardado:
            # Confirmación
            msg = (f"¡Guardado! Quedaste #{self._pos_ranking}"
                   if self._pos_ranking else "Puntaje registrado.")
            s = self._fuente_texto.render(msg, True, (100, 220, 100))
            self.superficie.blit(s, s.get_rect(centerx=cx, y=200))
        else:
            # Instrucción
            s = self._fuente_texto.render("Ingresa tu nombre:", True, COLOR_GO_TEXTO)
            self.superficie.blit(s, s.get_rect(centerx=cx, y=200))

            # Caja de texto
            box_rect = pygame.Rect(cx - 160, alto // 2 - 10, 320, 46)
            pygame.draw.rect(self.superficie, COLOR_GO_INPUT,  box_rect, border_radius=8)
            pygame.draw.rect(self.superficie, COLOR_GO_BORDE,  box_rect, width=2, border_radius=8)

            display = self.nombre + ("|" if (pygame.time.get_ticks() // 500) % 2 == 0 else "")
            s = self._fuente_input.render(display, True, COLOR_GO_NOMBRE)
            self.superficie.blit(s, s.get_rect(center=box_rect.center))

        # Top 3 puntajes
        self._dibujar_top3(cx, alto // 2 + 60)

        self._btn_guardar.dibujar(self.superficie)
        self._btn_menu.dibujar(self.superficie)

    # ── Interno ───────────────────────────────────────────────────────────────

    def _intentar_guardar(self) -> str | None:
        nombre = self.nombre.strip()
        if not nombre:
            return None
        entro, pos = self.game.save_score(nombre)
        self._guardado    = True
        self._pos_ranking = pos if entro else 0
        return "guardado"

    def _dibujar_top3(self, cx: int, y: int) -> None:
        top = self.game.get_top_scores()[:3]
        if not top:
            return
        s = self._fuente_texto.render("── Top 3 ──", True, (150, 150, 170))
        self.superficie.blit(s, s.get_rect(centerx=cx, y=y))
        for i, (nombre, pts) in enumerate(top):
            color = [(255, 215, 0), (192, 192, 192), (205, 127, 50)][i]
            txt = f"#{i+1}  {nombre}  —  {pts}"
            s = self._fuente_texto.render(txt, True, color)
            self.superficie.blit(s, s.get_rect(centerx=cx, y=y + 28 + i * 26))

    def _init_fuentes(self) -> None:
        if self._fuente_titulo is None:
            self._fuente_titulo = pygame.font.SysFont(None, 64)
            self._fuente_texto  = pygame.font.SysFont(None, 34)
            self._fuente_input  = pygame.font.SysFont(None, 36)


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────

def _crear_juego(pantalla: pygame.Surface) -> tuple[Game, GameScreen, pygame.Surface]:
    """
    Instancia Game y GameScreen para una nueva partida.

    Returns:
        (game, game_screen, nueva_pantalla)
    """
    size = config["matrix_size"]

    # Redimensionar ventana al tamaño exacto de la matriz
    ancho, alto = GameScreen.calcular_tamanio_ventana(size)
    pantalla    = pygame.display.set_mode((ancho, alto))

    # Crear y arrancar el juego
    game = Game(size)
    game.start()

    game_screen = GameScreen(game.matrix, pantalla, size)
    return game, game_screen, pantalla


def main() -> None:
    pygame.init()
    pygame.display.set_caption(TITULO)

    pantalla = pygame.display.set_mode((ANCHO_MENU, ALTO_MENU))
    reloj    = pygame.time.Clock()

    # Cargar fondo del menú (después de pygame.init)
    fondo_menu: pygame.Surface | None = _cargar_fondo_menu()

    # ── Botones del menú ──────────────────────────────────────────────────────
    cx = ANCHO_MENU // 2 - 100
    btn_jugar    = Button(cx, 250, 200, 55, "Jugar")
    btn_opciones = Button(cx, 330, 200, 55, "Opciones")
    btn_salir    = Button(cx, 410, 200, 55, "Salir")

    # ── Estado global ─────────────────────────────────────────────────────────
    game:        Game           | None = None
    game_screen: GameScreen     | None = None
    go_screen:   GameOverScreen | None = None
    cfg_screen:  ConfigScreen   | None = None
    estado = ESTADO_MENU

    # Callback: el hilo de scroll notifica game over → pedimos cambio de estado
    _game_over_pendiente = [False]

    def _on_game_over():
        _game_over_pendiente[0] = True

    corriendo = True
    while corriendo:

        # ── Detectar game over desde el hilo secundario ───────────────────────
        if _game_over_pendiente[0] and estado == ESTADO_JUEGO:
            _game_over_pendiente[0] = False
            # Restaurar ventana al tamaño del menú para game over
            pantalla    = pygame.display.set_mode((ANCHO_MENU, ALTO_MENU))
            go_screen   = GameOverScreen(pantalla, game)
            estado      = ESTADO_GAMEOVER

        # ── Eventos ───────────────────────────────────────────────────────────
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                corriendo = False

            # ── Menú ──────────────────────────────────────────────────────────
            if estado == ESTADO_MENU:
                if btn_jugar.fue_clickeado(evento):
                    _game_over_pendiente[0] = False
                    game, game_screen, pantalla = _crear_juego(pantalla)
                    game.on_game_over = _on_game_over
                    estado = ESTADO_JUEGO

                if btn_opciones.fue_clickeado(evento):
                    cfg_screen = ConfigScreen(pantalla, config)
                    estado = ESTADO_CONFIG

                if btn_salir.fue_clickeado(evento):
                    corriendo = False

            # ── Juego ─────────────────────────────────────────────────────────
            elif estado == ESTADO_JUEGO:
                resultado = game_screen.manejar_evento(evento)

                # Botón Menú o Escape → ir a game over primero
                if resultado == "menu" or (
                    evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE
                ):
                    game.stop()
                    pantalla  = pygame.display.set_mode((ANCHO_MENU, ALTO_MENU))
                    go_screen = GameOverScreen(pantalla, game)
                    estado    = ESTADO_GAMEOVER

                # Teclado de movimiento y poderes
                elif evento.type == pygame.KEYDOWN:
                    teclas = {
                        pygame.K_UP:    'up',
                        pygame.K_DOWN:  'down',
                        pygame.K_LEFT:  'left',
                        pygame.K_RIGHT: 'right',
                        pygame.K_w:     'up',
                        pygame.K_s:     'down',
                        pygame.K_a:     'left',
                        pygame.K_d:     'right',
                        pygame.K_1:     '1',
                        pygame.K_2:     '2',
                    }
                    if evento.key in teclas:
                        game.handle_key(teclas[evento.key])

            # ── Game Over ─────────────────────────────────────────────────────
            elif estado == ESTADO_GAMEOVER:
                resultado = go_screen.manejar_evento(evento)
                if resultado == "menu" or resultado == "guardado":
                    # Volver al menú después de guardar o directamente
                    if resultado == "guardado":
                        # Esperamos un evento de "menu" posterior para salir
                        pass
                    if resultado == "menu":
                        if game:
                            game.stop()
                        estado = ESTADO_MENU

            # ── Configuración ─────────────────────────────────────────────────
            elif estado == ESTADO_CONFIG:
                resultado = cfg_screen.manejar_evento(evento)
                if resultado == "guardar":
                    config.update(cfg_screen.valores)
                    estado = ESTADO_MENU
                elif resultado == "cancelar":
                    estado = ESTADO_MENU

        # ── Dibujo ────────────────────────────────────────────────────────────
        if estado == ESTADO_MENU:
            if fondo_menu:
                pantalla.blit(fondo_menu, (0, 0))
            else:
                pantalla.fill(GRIS_OSCURO)
            btn_jugar.dibujar(pantalla)
            btn_opciones.dibujar(pantalla)
            btn_salir.dibujar(pantalla)

        elif estado == ESTADO_JUEGO and game_screen:
            game_screen.actualizar_status(game.get_status())
            game_screen.dibujar()

        elif estado == ESTADO_GAMEOVER and go_screen:
            pantalla.fill(GRIS_OSCURO)
            go_screen.dibujar()

        elif estado == ESTADO_CONFIG and cfg_screen:
            pantalla.fill(GRIS_OSCURO)
            cfg_screen.dibujar()

        pygame.display.flip()
        reloj.tick(FPS)

    # ── Limpieza ──────────────────────────────────────────────────────────────
    if game:
        game.stop()
    pygame.quit()


if __name__ == "__main__":
    main()