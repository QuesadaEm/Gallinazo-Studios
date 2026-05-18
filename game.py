"""
Módulo: game.py
Descripción: Controlador principal del juego. Orquesta Matrix, Player,
             ScoreManager y el sistema de rewards. Gestiona el hilo
             secundario del scroll automático y la dificultad progresiva.
"""

import threading
import time
import random

from matrix import Matrix
from player import Player
from score_manager import ScoreManager


class Game:
    """
    Controlador principal del juego de laberinto dinámico.

    Al instanciarse, construye la matriz completa de forma síncrona,
    coloca al jugador, y queda listo para iniciar el scroll con start().

    El hilo secundario cada tick:
      1. Limpia la celda del jugador en la grid ANTES del scroll.
      2. Hace scroll (nueva fila entra por arriba).
      3. Llama push_down (que marca la nueva posición del jugador).
      4. Verifica game over.
      5. Spawnea rewards en celdas libres cada REWARD_INTERVAL ticks.
      6. Aumenta dificultad cada DIFFICULTY_EVERY segundos.
    """

    INITIAL_INTERVAL: float = 2.0
    MIN_INTERVAL:     float = 0.2
    DIFFICULTY_STEP:  float = 0.1
    DIFFICULTY_EVERY: float = 15.0

    # Cada cuántos ticks de scroll se spawnea un reward
    REWARD_INTERVAL: int = 3

    # Probabilidades relativas de cada reward (pesos)
    REWARD_WEIGHTS = {
        Matrix.COIN_5:      50,
        Matrix.COIN_10:     25,
        Matrix.POWER_BOMB:  15,
        Matrix.POWER_GHOST: 10,
    }

    STATE_RUNNING = 'running'
    STATE_OVER    = 'over'

    def __init__(self, size: int, scores_dir: str = "scores"):
        """
        Construye la matriz completa de forma instantánea y coloca
        al jugador. El juego arranca directamente en STATE_RUNNING.

        Args:
            size (int): Dimensión NxN (10, 20 o 30).
            scores_dir (str): Carpeta para los archivos de puntajes.
        """
        self.size = size

        # 1. Construir la matriz completa de forma síncrona
        self.matrix = Matrix(size)
        while not self.matrix.is_complete:
            self.matrix.add_row()

        # 2. Crear el jugador DESPUÉS de que la matriz tenga contenido
        self.player = Player(self.matrix)

        # 3. Gestor de puntajes
        self.score_manager = ScoreManager(size, scores_dir)

        # 4. Arrancar directamente en RUNNING
        self.state:           str   = self.STATE_RUNNING
        self.scroll_interval: float = self.INITIAL_INTERVAL

        self._stop_event    = threading.Event()
        self._scroll_thread: threading.Thread = None
        self._tick_count:   int   = 0

        self.on_game_over = None
        self.on_tick      = None

    # ── API pública ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Lanza el hilo secundario del scroll."""
        if self._scroll_thread is not None:
            raise RuntimeError("El juego ya fue iniciado.")
        self._stop_event.clear()
        self._scroll_thread = threading.Thread(
            target=self._scroll_loop,
            name="ScrollThread",
            daemon=True,
        )
        self._scroll_thread.start()

    def stop(self) -> None:
        """Detiene el hilo de scroll (timeout 3 s)."""
        self._stop_event.set()
        if self._scroll_thread is not None:
            self._scroll_thread.join(timeout=3.0)

    def handle_key(self, key: str) -> None:
        """
        Procesa una tecla capturada por la GUI.
        'up'|'down'|'left'|'right' → movimiento
        '1' → bomba   '2' → paso fantasma
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
        """Copia segura de la matriz para la GUI."""
        return self.matrix.get_snapshot()

    def get_status(self) -> dict:
        """Estado del juego para el panel de info."""
        return {
            'score':      self.player.score,
            'bombs':      self.player.bombs,
            'ghosts':     self.player.ghosts,
            'interval':   round(self.scroll_interval, 2),
            'state':      self.state,
            'player_pos': self.player.get_position(),
            'facing':     self.player.facing,
        }

    def save_score(self, player_name: str) -> tuple[bool, int]:
        """Guarda el puntaje final. Retorna (entró_top20, posición)."""
        return self.score_manager.add_score(player_name, self.player.score)

    def get_top_scores(self) -> list[tuple[str, int]]:
        """Top 20 histórico para el tamaño de matriz actual."""
        return self.score_manager.get_top_scores()

    # ── Hilo secundario ───────────────────────────────────────────────────────

    def _scroll_loop(self) -> None:
        elapsed_since_difficulty = 0.0

        while not self._stop_event.is_set():
            start_tick = time.time()

            self._interruptible_sleep(self.scroll_interval)
            if self._stop_event.is_set():
                break

            self._tick_count += 1

            # 1. Scroll: nueva fila entra por arriba, todo baja.
            #    El jugador NO está en la matriz, solo sus coordenadas,
            #    así que no hay nada que limpiar antes.
            self.matrix.add_row()

            # 2. Empujar coordenadas del jugador una fila hacia abajo
            player_alive = self.player.push_down()
            if not player_alive:
                self._trigger_game_over()
                break

            # 3. Spawnear rewards periódicamente
            if self._tick_count % self.REWARD_INTERVAL == 0:
                self._spawn_reward()

            # 4. Dificultad progresiva
            elapsed_since_difficulty += time.time() - start_tick
            if elapsed_since_difficulty >= self.DIFFICULTY_EVERY:
                self._increase_difficulty()
                elapsed_since_difficulty = 0.0

            if self.on_tick:
                self.on_tick()

    def _spawn_reward(self) -> None:
        """
        Coloca un reward aleatorio en una celda libre de la matriz.
        Usa los pesos definidos en REWARD_WEIGHTS.
        No spawnea si no hay celdas libres.
        """
        free_cells = self.matrix.find_free_cells()
        if not free_cells:
            return

        # Excluir la celda del jugador por si acaso
        player_pos = (self.player.row, self.player.col)
        free_cells = [c for c in free_cells if c != player_pos]
        if not free_cells:
            return

        # Elegir tipo de reward según pesos
        tipos   = list(self.REWARD_WEIGHTS.keys())
        pesos   = list(self.REWARD_WEIGHTS.values())
        tipo    = random.choices(tipos, weights=pesos, k=1)[0]

        # Elegir celda aleatoria
        row, col = random.choice(free_cells)
        self.matrix.set_cell(row, col, tipo)

    def _interruptible_sleep(self, duration: float) -> None:
        steps         = max(1, int(duration / 0.05))
        step_duration = duration / steps
        for _ in range(steps):
            if self._stop_event.is_set():
                return
            time.sleep(step_duration)

    def _increase_difficulty(self) -> None:
        self.scroll_interval = max(
            self.scroll_interval - self.DIFFICULTY_STEP,
            self.MIN_INTERVAL,
        )

    def _trigger_game_over(self) -> None:
        self.state = self.STATE_OVER
        if self.on_game_over:
            self.on_game_over()

    def __repr__(self) -> str:
        return (
            f"Game(size={self.size}, state='{self.state}', "
            f"interval={self.scroll_interval:.2f}s, "
            f"score={self.player.score})"
        )
