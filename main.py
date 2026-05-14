import pygame
from ui import Button
from matrix import Matrix
from game_screen import GameScreen
from config_screen import ConfigScreen

# ── Ventana del menú (fija) ────────────────────────────────────────────────────
ANCHO_MENU = 700
ALTO_MENU  = 700
FPS        = 60
TITULO     = "Mi Juego"
GRIS_OSCURO = (40, 40, 40)

# ── Configuración del juego ────────────────────────────────────────────────────
config = {
    "matrix_size": 20,
}

# ── Estados ────────────────────────────────────────────────────────────────────
ESTADO_MENU   = "menu"
ESTADO_JUEGO  = "juego"
ESTADO_CONFIG = "config"


def main():
    pygame.init()
    pygame.display.set_caption(TITULO)

    pantalla = pygame.display.set_mode((ANCHO_MENU, ALTO_MENU))
    reloj    = pygame.time.Clock()

    # ── Botones del menú (centrados en la ventana fija) ───────────────────────
    cx = ANCHO_MENU // 2 - 100
    btn_jugar    = Button(cx, 250, 200, 55, "Jugar")
    btn_opciones = Button(cx, 330, 200, 55, "Opciones")
    btn_salir    = Button(cx, 410, 200, 55, "Salir")

    game_screen = None
    cfg_screen  = None
    estado      = ESTADO_MENU
    corriendo   = True

    while corriendo:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                corriendo = False

            # ── Menú ──────────────────────────────────────────────────────────
            if estado == ESTADO_MENU:
                if btn_jugar.fue_clickeado(evento):
                    # 1. Calcular tamaño exacto para la matriz
                    ancho_juego, alto_juego = GameScreen.calcular_tamanio_ventana(
                        config["matrix_size"]
                    )
                    # 2. Redimensionar ventana
                    pantalla = pygame.display.set_mode((ancho_juego, alto_juego))

                    # 3. Crear matriz y pantalla de juego
                    matrix = Matrix(config["matrix_size"])
                    while not matrix.is_complete:
                        matrix.add_row()
                    game_screen = GameScreen(matrix, pantalla, config["matrix_size"])
                    estado = ESTADO_JUEGO

                if btn_opciones.fue_clickeado(evento):
                    cfg_screen = ConfigScreen(pantalla, config)
                    estado = ESTADO_CONFIG

                if btn_salir.fue_clickeado(evento):
                    corriendo = False

            # ── Juego ─────────────────────────────────────────────────────────
            elif estado == ESTADO_JUEGO:
                resultado = game_screen.manejar_evento(evento)
                volver = resultado == "menu" or (
                    evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE
                )
                if volver:
                    # Restaurar tamaño del menú
                    pantalla = pygame.display.set_mode((ANCHO_MENU, ALTO_MENU))
                    estado = ESTADO_MENU

            # ── Configuración ─────────────────────────────────────────────────
            elif estado == ESTADO_CONFIG:
                resultado = cfg_screen.manejar_evento(evento)
                if resultado == "guardar":
                    config.update(cfg_screen.valores)   # ventana del menú no cambia
                    estado = ESTADO_MENU
                elif resultado == "cancelar":
                    estado = ESTADO_MENU

        # ── Dibujo ────────────────────────────────────────────────────────────
        pantalla.fill(GRIS_OSCURO)

        if estado == ESTADO_MENU:
            btn_jugar.dibujar(pantalla)
            btn_opciones.dibujar(pantalla)
            btn_salir.dibujar(pantalla)

        elif estado == ESTADO_JUEGO and game_screen:
            game_screen.dibujar()

        elif estado == ESTADO_CONFIG and cfg_screen:
            cfg_screen.dibujar()

        pygame.display.flip()
        reloj.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
