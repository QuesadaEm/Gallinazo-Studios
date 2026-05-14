import pygame

# ── Paleta por defecto (puedes sobreescribir al instanciar) ───────────────────
COLOR_NORMAL   = (70,  130, 180)   # azul acero
COLOR_HOVER    = (100, 160, 210)   # más claro al pasar el mouse
COLOR_CLICK    = (40,  90,  140)   # más oscuro al presionar
COLOR_TEXTO    = (255, 255, 255)
COLOR_BORDE    = (200, 200, 200)

FUENTE_TAMAÑO  = 26


class Button:
    """
    Botón reutilizable para pygame.

    Uso básico:
        btn = Button(x, y, ancho, alto, "Texto")
        btn.dibujar(pantalla)          # en el loop de dibujo
        btn.fue_clickeado(evento)      # en el loop de eventos
    """

    def __init__(
        self,
        x: int, y: int,
        ancho: int, alto: int,
        texto: str,
        color_normal: tuple = COLOR_NORMAL,
        color_hover:  tuple = COLOR_HOVER,
        color_click:  tuple = COLOR_CLICK,
        color_texto:  tuple = COLOR_TEXTO,
        radio_borde:  int   = 8,          # esquinas redondeadas (0 = cuadrado)
    ):
        self.rect         = pygame.Rect(x, y, ancho, alto)
        self.texto        = texto
        self.c_normal     = color_normal
        self.c_hover      = color_hover
        self.c_click      = color_click
        self.c_texto      = color_texto
        self.radio        = radio_borde

        self._presionado  = False         # estado interno
        self._fuente      = None          # se inicializa al primer dibujo

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _obtener_fuente(self) -> pygame.font.Font:
        """Inicializa la fuente una sola vez (pygame.init ya debe haberse llamado)."""
        if self._fuente is None:
            self._fuente = pygame.font.SysFont(None, FUENTE_TAMAÑO)
        return self._fuente

    @property
    def _sobre_boton(self) -> bool:
        return self.rect.collidepoint(pygame.mouse.get_pos())

    # ── API pública ───────────────────────────────────────────────────────────

    def dibujar(self, superficie: pygame.Surface) -> None:
        """Dibuja el botón con efecto hover/click."""
        if self._presionado and self._sobre_boton:
            color = self.c_click
        elif self._sobre_boton:
            color = self.c_hover
        else:
            color = self.c_normal

        pygame.draw.rect(superficie, color, self.rect, border_radius=self.radio)
        pygame.draw.rect(superficie, COLOR_BORDE, self.rect,
                         width=2, border_radius=self.radio)

        fuente = self._obtener_fuente()
        sup_texto = fuente.render(self.texto, True, self.c_texto)
        pos_texto = sup_texto.get_rect(center=self.rect.center)
        superficie.blit(sup_texto, pos_texto)

    def fue_clickeado(self, evento: pygame.event.Event) -> bool:
        """
        Devuelve True UNA SOLA VEZ cuando el botón es soltado sobre él.
        Llámalo dentro del loop de eventos con cada evento.
        """
        if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            if self.rect.collidepoint(evento.pos):
                self._presionado = True

        if evento.type == pygame.MOUSEBUTTONUP and evento.button == 1:
            if self._presionado and self.rect.collidepoint(evento.pos):
                self._presionado = False
                return True
            self._presionado = False

        return False

    def mover(self, x: int, y: int) -> None:
        """Reposiciona el botón en tiempo de ejecución."""
        self.rect.topleft = (x, y)

    def cambiar_texto(self, nuevo_texto: str) -> None:
        """Cambia la etiqueta del botón."""
        self.texto = nuevo_texto


# ── Selector de opción  ◀  valor  ▶ ──────────────────────────────────────────

class SelectorOpcion:
    """
    Control  ◀  Valor  ▶  para elegir entre una lista de opciones.

    Uso:
        selector = SelectorOpcion(x, y, 260, 50, "Celdas", [10, 20, 30])
        selector.dibujar(pantalla)          # en el loop de dibujo
        selector.manejar_evento(evento)     # en el loop de eventos
        valor_actual = selector.valor       # propiedad de lectura
    """

    FLECHA_ANCHO = 44
    COLOR_FLECHA = (70,  130, 180)
    COLOR_FHOVER = (100, 160, 210)
    COLOR_FCLICK = (40,   90, 140)
    COLOR_FONDO  = (55,   55,  65)
    COLOR_TEXTO  = (255, 255, 255)
    COLOR_LABEL  = (180, 180, 180)
    COLOR_BORDE  = (200, 200, 200)

    def __init__(
        self,
        x: int, y: int,
        ancho: int, alto: int,
        etiqueta: str,
        opciones: list,
        indice_inicial: int = 0,
    ):
        self.x        = x
        self.y        = y
        self.ancho    = ancho
        self.alto     = alto
        self.etiqueta = etiqueta
        self.opciones = opciones
        self._indice  = indice_inicial

        fa = self.FLECHA_ANCHO
        self._rect_izq = pygame.Rect(x,                    y, fa,          alto)
        self._rect_der = pygame.Rect(x + ancho - fa,       y, fa,          alto)
        self._rect_cen = pygame.Rect(x + fa,               y, ancho - fa*2, alto)

        self._press_izq = False
        self._press_der = False
        self._fuente_val: pygame.font.Font | None = None
        self._fuente_lbl: pygame.font.Font | None = None

    # ── Propiedad de lectura ──────────────────────────────────────────────────

    @property
    def valor(self):
        return self.opciones[self._indice]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fuentes(self):
        if self._fuente_val is None:
            self._fuente_val = pygame.font.SysFont(None, 30)
            self._fuente_lbl = pygame.font.SysFont(None, 22)
        return self._fuente_val, self._fuente_lbl

    def _color_flecha(self, rect, presionado) -> tuple:
        if presionado and rect.collidepoint(pygame.mouse.get_pos()):
            return self.COLOR_FCLICK
        if rect.collidepoint(pygame.mouse.get_pos()):
            return self.COLOR_FHOVER
        return self.COLOR_FLECHA

    # ── API pública ───────────────────────────────────────────────────────────

    def dibujar(self, superficie: pygame.Surface) -> None:
        fuente_val, fuente_lbl = self._fuentes()
        r = 8   # radio esquinas

        # Fondo central
        pygame.draw.rect(superficie, self.COLOR_FONDO,  self._rect_cen)

        # Flechas
        pygame.draw.rect(superficie, self._color_flecha(self._rect_izq, self._press_izq),
                         self._rect_izq, border_radius=r)
        pygame.draw.rect(superficie, self._color_flecha(self._rect_der, self._press_der),
                         self._rect_der, border_radius=r)

        # Borde general
        rect_total = pygame.Rect(self.x, self.y, self.ancho, self.alto)
        pygame.draw.rect(superficie, self.COLOR_BORDE, rect_total, width=2, border_radius=r)

        # Texto flechas
        for simbolo, rect in [("◀", self._rect_izq), ("▶", self._rect_der)]:
            s = fuente_val.render(simbolo, True, self.COLOR_TEXTO)
            superficie.blit(s, s.get_rect(center=rect.center))

        # Valor actual
        s_val = fuente_val.render(str(self.valor), True, self.COLOR_TEXTO)
        superficie.blit(s_val, s_val.get_rect(center=self._rect_cen.center))

        # Etiqueta encima
        s_lbl = fuente_lbl.render(self.etiqueta, True, self.COLOR_LABEL)
        superficie.blit(s_lbl, (self.x, self.y - 22))

    def manejar_evento(self, evento: pygame.event.Event) -> bool:
        """
        Procesa clicks en las flechas. Devuelve True si el valor cambió.
        """
        cambio = False

        if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            if self._rect_izq.collidepoint(evento.pos):
                self._press_izq = True
            if self._rect_der.collidepoint(evento.pos):
                self._press_der = True

        if evento.type == pygame.MOUSEBUTTONUP and evento.button == 1:
            if self._press_izq and self._rect_izq.collidepoint(evento.pos):
                self._indice = (self._indice - 1) % len(self.opciones)
                cambio = True
            if self._press_der and self._rect_der.collidepoint(evento.pos):
                self._indice = (self._indice + 1) % len(self.opciones)
                cambio = True
            self._press_izq = False
            self._press_der = False

        return cambio
