"""
Módulo: player.py
Descripción: Gestiona posición, movimiento, poderes y puntaje del jugador.

El jugador NO se almacena como valor dentro de la matriz.
Sus coordenadas (row, col) son variables independientes.
La matriz solo contiene FREE, OBSTACLE, monedas y poderes.
"""

from matrix import Matrix


class Player:
    UP    = 'up'
    DOWN  = 'down'
    LEFT  = 'left'
    RIGHT = 'right'

    COIN_5_VALUE  = 5
    COIN_10_VALUE = 10

    def __init__(self, matrix: Matrix):
        """
        Inicializa el jugador en la primera celda libre
        de la fila size//2 (centro de la matriz).

        Args:
            matrix (Matrix): Referencia a la matriz del laberinto.
        """
        self._matrix         = matrix
        self.score:          int  = 0
        self.bombs:          int  = 0
        self.ghosts:         int  = 0
        self.last_direction: str  = self.UP
        self.facing:         str  = self.UP   # dirección visual actual
        self.is_alive:       bool = True

        self.row, self.col = self._find_spawn()

    # ── Spawn ─────────────────────────────────────────────────────────────────

    def _find_spawn(self) -> tuple[int, int]:
        """
        Primera celda libre en la fila inferior. Si la fila inferior
        está completamente bloqueada, sube fila por fila hasta encontrar
        una celda libre, tal como pide la especificación.
        """
        size = self._matrix.size

        for row in range(size - 1, -1, -1):
            for col in range(size):
                if self._matrix.grid[row][col] == Matrix.FREE:
                    return row, col

        return size - 1, size // 2  # fallback

    # ── Movimiento ────────────────────────────────────────────────────────────

    def move(self, direction: str) -> bool:
        """
        Intenta mover al jugador en la dirección indicada.
        Recoge el reward si la celda destino lo tiene.

        Returns:
            bool: True si el movimiento fue exitoso.
        """
        if not self.is_alive:
            return False

        self.last_direction = direction
        self.facing         = direction   # actualizar dirección visual siempre
        new_row, new_col    = self._calculate_destination(direction)

        if not self._matrix._in_bounds(new_row, new_col):
            return False

        if self._matrix.is_obstacle(new_row, new_col):
            return False

        # Recoger reward si lo hay
        cell_value = self._matrix.get_cell(new_row, new_col)
        if cell_value not in (Matrix.FREE,):
            self._collect_reward(cell_value)
            self._matrix.set_cell(new_row, new_col, Matrix.FREE)

        self.row = new_row
        self.col = new_col
        return True

    def use_bomb(self) -> bool:
        """Destruye el obstáculo adyacente en la dirección actual."""
        if self.bombs <= 0:
            return False

        tr, tc = self._calculate_destination(self.last_direction)
        if not self._matrix._in_bounds(tr, tc):
            return False

        if self._matrix.is_obstacle(tr, tc):
            self._matrix.set_cell(tr, tc, Matrix.FREE)
            self.bombs -= 1
            return True

        return False

    def use_ghost(self) -> bool:
        """Atraviesa exactamente un obstáculo en la dirección actual."""
        if self.ghosts <= 0:
            return False

        obs_r, obs_c    = self._calculate_destination(self.last_direction)
        beyond_r, beyond_c = self._calculate_destination(
            self.last_direction, from_row=obs_r, from_col=obs_c
        )

        if not self._matrix.is_obstacle(obs_r, obs_c):
            return False
        if self._matrix.is_obstacle(beyond_r, beyond_c):
            return False
        if not self._matrix._in_bounds(beyond_r, beyond_c):
            return False

        # Recoger reward si lo hay al otro lado
        cell_value = self._matrix.get_cell(beyond_r, beyond_c)
        if cell_value not in (Matrix.FREE,):
            self._collect_reward(cell_value)
            self._matrix.set_cell(beyond_r, beyond_c, Matrix.FREE)

        self.row = beyond_r
        self.col = beyond_c
        self.ghosts -= 1
        return True

    def push_down(self) -> bool:
        """
        El scroll empuja al jugador una fila hacia abajo.
        No toca la matriz — solo actualiza las coordenadas.

        Returns:
            bool: True si sobrevivió, False si salió por el borde inferior.
        """
        new_row = self.row + 1

        if new_row >= self._matrix.size:
            self.is_alive = False
            return False

        # Recoger reward si el scroll lo lleva encima de uno
        cell_value = self._matrix.get_cell(new_row, self.col)
        if cell_value not in (Matrix.FREE, Matrix.OBSTACLE):
            self._collect_reward(cell_value)
            self._matrix.set_cell(new_row, self.col, Matrix.FREE)

        self.row = new_row
        return True

    # ── Consultas ─────────────────────────────────────────────────────────────

    def get_position(self) -> tuple[int, int]:
        return (self.row, self.col)

    def get_inventory(self) -> dict:
        return {'bombs': self.bombs, 'ghosts': self.ghosts}

    # ── Interno ───────────────────────────────────────────────────────────────

    def _collect_reward(self, cell_value: int) -> None:
        if cell_value == Matrix.COIN_5:
            self.score += self.COIN_5_VALUE
        elif cell_value == Matrix.COIN_10:
            self.score += self.COIN_10_VALUE
        elif cell_value == Matrix.POWER_BOMB:
            self.bombs += 1
        elif cell_value == Matrix.POWER_GHOST:
            self.ghosts += 1

    def _calculate_destination(
        self,
        direction: str,
        from_row:  int = None,
        from_col:  int = None,
    ) -> tuple[int, int]:
        r = from_row if from_row is not None else self.row
        c = from_col if from_col is not None else self.col
        deltas = {
            self.UP:    (-1,  0),
            self.DOWN:  ( 1,  0),
            self.LEFT:  ( 0, -1),
            self.RIGHT: ( 0,  1),
        }
        dr, dc = deltas.get(direction, (0, 0))
        return r + dr, c + dc

    def __repr__(self) -> str:
        return (
            f"Player(pos=({self.row},{self.col}), "
            f"score={self.score}, bombs={self.bombs}, ghosts={self.ghosts})"
        )
