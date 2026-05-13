"""
Módulo: game.py
Descripción: Contiene la clase Game, controlador principal del juego.
             Orquesta todos los módulos, gestiona el hilo secundario
             del scroll automático y la dificultad progresiva.
Autor: Persona A
Curso: Taller de Programación IC1803
"""

import threading
import time

from matrix import Matrix
from player import Player
from row_generator import RowGenerator
from score_manager import ScoreManager


class Game:
    """
    Controlador principal del juego de laberinto dinámico.

    Coordina la lógica del juego entre todos los módulos:
    Matrix, Player y ScoreManager. Gestiona dos hilos:

    - Hilo principal: interfaz gráfica y eventos de teclado (manejado
      externamente por GameGUI).
    - Hilo secundario: scroll automático de la matriz y dificultad
      progresiva.

    Attributes:
        size (int): Tamaño de la matriz (10, 20 o 30).
        matrix (Matrix): Instancia de la matriz del laberinto.
        player (Player): Instancia del jugador.
        score_manager (ScoreManager): Instancia del gestor de puntajes.
        state (str): Estado actual del juego. Valores posibles:
                     'building' -> construyendo la matriz inicial,
                     'running'  -> partida en curso,
                     'over'     -> partida terminada.
        scroll_interval (float): Intervalo en segundos entre cada scroll.
        _scroll_thread (threading.Thread): Hilo secundario del scroll.
        _stop_event (threading.Event): Señal para detener el hilo secundario.
        _difficulty_timer (float): Acumulador de tiempo para la dificultad.
        INITIAL_INTERVAL (float): Intervalo inicial del scroll (2.0 seg).
        MIN_INTERVAL (float): Intervalo mínimo posible (0.2 seg).
        DIFFICULTY_STEP (float): Reducción del intervalo cada 15 seg (0.1 seg).
        DIFFICULTY_EVERY (float): Cada cuántos segundos aumenta la dificultad (15 seg).
    """

    INITIAL_INTERVAL: float = 2.0
    MIN_INTERVAL: float = 0.2
    DIFFICULTY_STEP: float = 0.1
    DIFFICULTY_EVERY: float = 15.0

    # Estados del juego
    STATE_BUILDING = 'building'
    STATE_RUNNING = 'running'
    STATE_OVER = 'over'

    def __init__(self, size: int, scores_dir: str = "scores"):
        """
        Inicializa el juego con el tamaño de matriz indicado.

        Crea la matriz, el jugador y el gestor de puntajes.
        El juego no inicia hasta que se llame a start().

        Args:
            size (int): Dimensión NxN de la matriz (10, 20 o 30).
            scores_dir (str): Directorio para los archivos de puntajes.

        Raises:
            ValueError: Si el tamaño no es 10, 20 o 30.
        """
        self.size = size
        self.matrix = Matrix(size)
        self.player = Player(self.matrix)
        self.score_manager = ScoreManager(size, scores_dir)

        self.state: str = self.STATE_BUILDING
        self.scroll_interval: float = self.INITIAL_INTERVAL

        self._stop_event = threading.Event()
        self._difficulty_timer: float = 0.0
        self._scroll_thread: threading.Thread = None

        # Callback opcional para notificar a la GUI del game over
        self.on_game_over = None

        # Callback opcional para notificar a la GUI de cada tick
        self.on_tick = None

    def start(self) -> None:
        """
        Inicia la partida lanzando el hilo secundario del scroll.

        El hilo secundario se ejecuta como daemon para que se detenga
        automáticamente si el programa principal termina.

        Raises:
            RuntimeError: Si el juego ya fue iniciado anteriormente.
        """
        if self._scroll_thread is not None:
            raise RuntimeError("El juego ya fue iniciado.")

        self._stop_event.clear()
        self._scroll_thread = threading.Thread(
            target=self._scroll_loop,
            name="ScrollThread",
            daemon=True
        )
        self._scroll_thread.start()

    def stop(self) -> None:
        """
        Detiene el hilo secundario del scroll de forma segura.

        Señala al hilo que debe terminar y espera a que finalice
        con un timeout de 3 segundos.
        """
        self._stop_event.set()
        if self._scroll_thread is not None:
            self._scroll_thread.join(timeout=3.0)

    def handle_key(self, key: str) -> None:
        """
        Procesa un evento de teclado capturado por la GUI.

        Teclas soportadas:
            'up', 'down', 'left', 'right' -> movimiento del jugador.
            '1' -> usar bomba.
            '2' -> usar paso fantasma.

        Args:
            key (str): Identificador de la tecla presionada.
        """
        if self.state != self.STATE_RUNNING:
            return

        if key in ('up', 'down', 'left', 'right'):
            self.player.move(key)
        elif key == '1':
            self.player.use_bomb()
        elif key == '2':
            self.player.use_ghost()

    def get_snapshot(self) -> list[list[int]]:
        """
        Retorna una copia del estado actual de la matriz.

        Método pensado para que la GUI pueda leer el estado de forma
        segura sin bloquear el hilo del scroll.

        Returns:
            list[list[int]]: Copia 2D de la matriz en su estado actual.
        """
        return self.matrix.get_snapshot()

    def get_status(self) -> dict:
        """
        Retorna el estado actual del juego en un diccionario.

        Útil para que la GUI actualice el panel de información
        (puntaje, poderes, velocidad, estado).

        Returns:
            dict: Diccionario con los campos:
                  - 'score' (int): Puntaje actual del jugador.
                  - 'bombs' (int): Bombas disponibles.
                  - 'ghosts' (int): Pasos fantasma disponibles.
                  - 'interval' (float): Intervalo de scroll actual.
                  - 'state' (str): Estado del juego.
                  - 'player_pos' (tuple): Posición (fila, col) del jugador.
        """
        return {
            'score':      self.player.score,
            'bombs':      self.player.bombs,
            'ghosts':     self.player.ghosts,
            'interval':   round(self.scroll_interval, 2),
            'state':      self.state,
            'player_pos': self.player.get_position(),
        }

    def save_score(self, player_name: str) -> tuple[bool, int]:
        """
        Guarda el puntaje final del jugador al terminar la partida.

        Args:
            player_name (str): Nombre del jugador para el registro.

        Returns:
            tuple[bool, int]: (entró_en_top20, posición). Ver ScoreManager.add_score.
        """
        return self.score_manager.add_score(player_name, self.player.score)

    def get_top_scores(self) -> list[tuple[str, int]]:
        """
        Retorna el Top 20 de puntajes históricos para el tamaño actual.

        Returns:
            list[tuple[str, int]]: Lista de (nombre, puntaje) ordenada.
        """
        return self.score_manager.get_top_scores()

    # ------------------------------------------------------------------
    # Hilo secundario — lógica privada
    # ------------------------------------------------------------------

    def _scroll_loop(self) -> None:
        """
        Bucle principal del hilo secundario.

        Ejecuta el ciclo de scroll automático mientras el juego esté activo:
        1. Espera el intervalo actual.
        2. Agrega una nueva fila a la matriz (build o scroll).
        3. Empuja al jugador una fila hacia abajo.
        4. Verifica si el jugador perdió.
        5. Actualiza la dificultad cada 15 segundos.
        6. Notifica a la GUI si existe callback registrado.

        El hilo se detiene cuando _stop_event es señalado o cuando
        el jugador pierde.
        """
        elapsed_since_difficulty = 0.0

        while not self._stop_event.is_set():
            start_tick = time.time()

            # Esperar el intervalo actual en fracciones pequeñas
            # para poder reaccionar rápido al stop_event
            self._interruptible_sleep(self.scroll_interval)

            if self._stop_event.is_set():
                break

            # --- Agregar nueva fila ---
            self.matrix.add_row()

            # Transición de estado: building -> running
            if self.state == self.STATE_BUILDING and self.matrix.is_complete:
                self.state = self.STATE_RUNNING

            # --- Empujar al jugador solo cuando el juego está en curso ---
            if self.state == self.STATE_RUNNING:
                player_alive = self.player.push_down()

                if not player_alive:
                    self._trigger_game_over()
                    break

            # --- Actualizar dificultad ---
            tick_duration = time.time() - start_tick
            elapsed_since_difficulty += tick_duration

            if elapsed_since_difficulty >= self.DIFFICULTY_EVERY:
                self._increase_difficulty()
                elapsed_since_difficulty = 0.0

            # --- Notificar a la GUI ---
            if self.on_tick:
                self.on_tick()

    def _interruptible_sleep(self, duration: float) -> None:
        """
        Duerme durante 'duration' segundos de forma interrumpible.

        Divide el sleep en intervalos de 0.05 segundos para poder
        reaccionar al stop_event sin esperar el intervalo completo.

        Args:
            duration (float): Tiempo total a esperar en segundos.
        """
        steps = max(1, int(duration / 0.05))
        step_duration = duration / steps

        for _ in range(steps):
            if self._stop_event.is_set():
                return
            time.sleep(step_duration)

    def _increase_difficulty(self) -> None:
        """
        Aumenta la dificultad reduciendo el intervalo de scroll.

        El intervalo disminuye en DIFFICULTY_STEP (0.1 seg) cada
        DIFFICULTY_EVERY (15 seg), hasta un mínimo de MIN_INTERVAL (0.2 seg).
        """
        new_interval = self.scroll_interval - self.DIFFICULTY_STEP
        self.scroll_interval = max(new_interval, self.MIN_INTERVAL)

    def _trigger_game_over(self) -> None:
        """
        Marca el juego como terminado y notifica a la GUI.

        Cambia el estado a 'over' y llama al callback on_game_over
        si fue registrado por la GUI.
        """
        self.state = self.STATE_OVER
        if self.on_game_over:
            self.on_game_over()

    def __repr__(self) -> str:
        """Representación en cadena del controlador de juego."""
        return (
            f"Game(size={self.size}, state='{self.state}', "
            f"interval={self.scroll_interval:.2f}s, "
            f"score={self.player.score})"
        )
