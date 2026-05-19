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

    # Cada cuántos segundos se spawnea un reward (especificación: 5 s)
    REWARD_SPAWN_EVERY: float = 5.0

    # Cuántos segundos dura un reward en el mapa (especificación: 10 s)
    REWARD_TTL: float = 10.0

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

        # La matriz arranca vacía (todo libre). El hilo secundario irá
        # agregando filas con obstáculos desde arriba hacia abajo.
        self.matrix = Matrix(size)

        # Crear el jugador en la fila inferior (que aún está libre)
        self.player = Player(self.matrix)

        # 3. Gestor de puntajes
        self.score_manager = ScoreManager(size, scores_dir)

        # 4. Arrancar directamente en RUNNING
        self.state:           str   = self.STATE_RUNNING
        self.scroll_interval: float = self.INITIAL_INTERVAL

        self._stop_event    = threading.Event()
        self._scroll_thread: threading.Thread = None
        self._tick_count:   int   = 0

        # Rewards activos: lista de (fila, col, tiempo_spawn)
        self._active_rewards: list[tuple[int, int, float]] = []
        self._elapsed_since_reward: float = 0.0

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

            # 1. Agregar nueva fila desde arriba (build o scroll)
            self.matrix.add_row()

            # 2. Solo empujar al jugador una vez que la matriz esté completa
            #    (fase de scroll). Durante la construcción el jugador está libre.
            if self.matrix.is_complete:
                self._shift_rewards_down()
                player_alive = self.player.push_down()
                if not player_alive:
                    self._trigger_game_over()
                    break

            # 3. Gestión de rewards: solo durante la fase de scroll
            if self.matrix.is_complete:
                self._elapsed_since_reward += self.scroll_interval
                if self._elapsed_since_reward >= self.REWARD_SPAWN_EVERY:
                    self._spawn_reward()
                    self._elapsed_since_reward = 0.0
                self._expire_rewards()

            # 5. Dificultad progresiva
            elapsed_since_difficulty += time.time() - start_tick
            if elapsed_since_difficulty >= self.DIFFICULTY_EVERY:
                self._increase_difficulty()
                elapsed_since_difficulty = 0.0

            if self.on_tick:
                self.on_tick()

    def _spawn_reward(self) -> None:
        """
        Coloca un reward aleatorio en una celda libre de la matriz.
        Registra la posición y el tiempo de spawn para controlar su expiración.
        Usa los pesos definidos en REWARD_WEIGHTS.
        No spawnea si no hay celdas libres.
        """
        free_cells = self.matrix.find_free_cells()
        if not free_cells:
            return

        # Excluir la celda del jugador
        player_pos = (self.player.row, self.player.col)
        free_cells = [c for c in free_cells if c != player_pos]
        if not free_cells:
            return

        # Elegir tipo de reward según pesos
        tipos  = list(self.REWARD_WEIGHTS.keys())
        pesos  = list(self.REWARD_WEIGHTS.values())
        tipo   = random.choices(tipos, weights=pesos, k=1)[0]

        # Elegir celda aleatoria y colocar el reward
        row, col = random.choice(free_cells)
        self.matrix.set_cell(row, col, tipo)

        # Registrar para el timer de expiración
        self._active_rewards.append((row, col, time.time()))

    def _expire_rewards(self) -> None:
        """
        Elimina de la matriz los rewards que lleven más de REWARD_TTL (10 s)
        en el mapa sin ser recolectados.
        """
        now = time.time()
        vigentes = []

        for row, col, spawn_time in self._active_rewards:
            if now - spawn_time >= self.REWARD_TTL:
                # Expirado: borrar de la matriz si sigue siendo un reward
                if self.matrix._in_bounds(row, col):
                    cell = self.matrix.get_cell(row, col)
                    if cell in self.REWARD_WEIGHTS:
                        self.matrix.set_cell(row, col, Matrix.FREE)
            else:
                vigentes.append((row, col, spawn_time))

        self._active_rewards = vigentes

    def _shift_rewards_down(self) -> None:
        """
        Ajusta las coordenadas de fila de los rewards activos tras cada scroll.
        Cada scroll desplaza todo una fila hacia abajo, así que fila += 1.
        Los rewards que salen por el borde inferior se descartan.
        """
        nuevos = []
        for row, col, spawn_time in self._active_rewards:
            new_row = row + 1
            if new_row < self.matrix.size:
                nuevos.append((new_row, col, spawn_time))
            # Si sale del mapa simplemente se descarta (ya no existe en la matriz)
        self._active_rewards = nuevos

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
