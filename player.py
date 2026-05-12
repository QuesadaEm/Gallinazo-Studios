"""
Módulo: player.py
Descripción: Contiene la clase Player, que gestiona la posición,
             movimiento, poderes y puntaje del jugador en el laberinto.
Autor: Persona A
Curso: Taller de Programación IC1803
"""

from matrix import Matrix


class Player:
    """
    Representa al jugador dentro del laberinto dinámico.

    Gestiona la posición actual, el movimiento en 4 direcciones,
    el inventario de poderes y el puntaje acumulado.

    El jugador inicia en el centro de la fila inferior de la matriz.

    Attributes:
        row (int): Fila actual del jugador (0 = superior).
        col (int): Columna actual del jugador.
        score (int): Puntaje acumulado.
        bombs (int): Cantidad de bombas disponibles.
        ghosts (int): Cantidad de pasos fantasma disponibles.
        last_direction (str): Última dirección de movimiento ('up','down','left','right').
        is_alive (bool): Estado del jugador.
        _matrix (Matrix): Referencia a la matriz del juego.
    """

    # Direcciones válidas de movimiento
    UP = 'up'
    DOWN = 'down'
    LEFT = 'left'
    RIGHT = 'right'

    # Puntos por tipo de moneda
    COIN_5_VALUE = 5
    COIN_10_VALUE = 10

    def __init__(self, matrix: Matrix):
        """
        Inicializa el jugador en el centro de la fila inferior.

        Args:
            matrix (Matrix): Referencia a la matriz del laberinto.
        """
        self._matrix = matrix
        self.row: int = matrix.size - 1
        self.col: int = matrix.size // 2
        self.score: int = 0
        self.bombs: int = 0
        self.ghosts: int = 0
        self.last_direction: str = self.UP
        self.is_alive: bool = True

        # Marcar posición inicial en la matriz
        self._matrix.set_cell(self.row, self.col, Matrix.PLAYER)

    def move(self, direction: str) -> bool:
        """
        Intenta mover al jugador en la dirección indicada.

        Valida que la celda destino esté dentro de los límites y
        no sea un obstáculo. Si la celda contiene una recompensa,
        la recoge automáticamente.

        Args:
            direction (str): Dirección del movimiento. Valores válidos:
                             'up', 'down', 'left', 'right'.

        Returns:
            bool: True si el movimiento fue exitoso, False si fue bloqueado.
        """
        if not self.is_alive:
            return False

        self.last_direction = direction
        new_row, new_col = self._calculate_destination(direction)

        # Verificar límites
        if not self._matrix._in_bounds(new_row, new_col):
            return False

        # Verificar obstáculo
        if self._matrix.is_obstacle(new_row, new_col):
            return False

        # Ejecutar movimiento
        self._perform_move(new_row, new_col)
        return True

    def use_bomb(self) -> bool:
        """
        Usa una bomba para destruir el obstáculo en la dirección actual.

        La bomba destruye exactamente un obstáculo adyacente en la
        dirección en que se movió el jugador por última vez.

        Returns:
            bool: True si la bomba fue usada con éxito.
                  False si no hay bombas o no hay obstáculo que destruir.
        """
        if self.bombs <= 0:
            return False

        target_row, target_col = self._calculate_destination(self.last_direction)

        if not self._matrix._in_bounds(target_row, target_col):
            return False

        if self._matrix.is_obstacle(target_row, target_col):
            self._matrix.set_cell(target_row, target_col, Matrix.FREE)
            self.bombs -= 1
            return True

        return False

    def use_ghost(self) -> bool:
        """
        Activa el poder de paso fantasma.

        Permite al jugador atravesar UN ÚNICO obstáculo consecutivo
        en la dirección actual del movimiento. No funciona si hay
        dos o más obstáculos seguidos.

        Returns:
            bool: True si el paso fue exitoso, False si no se pudo usar.
        """
        if self.ghosts <= 0:
            return False

        # Calcular la celda del obstáculo y la celda detrás de él
        obstacle_row, obstacle_col = self._calculate_destination(self.last_direction)
        beyond_row, beyond_col = self._calculate_destination(
            self.last_direction, from_row=obstacle_row, from_col=obstacle_col
        )

        # Verificar que haya exactamente un obstáculo (no dos seguidos)
        if not self._matrix.is_obstacle(obstacle_row, obstacle_col):
            return False  # No hay obstáculo que atravesar

        if self._matrix.is_obstacle(beyond_row, beyond_col):
            return False  # Dos obstáculos seguidos: no se puede

        if not self._matrix._in_bounds(beyond_row, beyond_col):
            return False

        # Ejecutar el paso fantasma
        self._perform_move(beyond_row, beyond_col)
        self.ghosts -= 1
        return True

    def collect_reward(self, cell_value: int) -> None:
        """
        Procesa la recolección de una recompensa según el valor de la celda.

        Args:
            cell_value (int): Valor de la celda de destino.
                              3 -> Moneda 5 pts
                              4 -> Moneda 10 pts
                              5 -> Bomba
                              6 -> Paso fantasma
        """
        if cell_value == Matrix.COIN_5:
            self.score += self.COIN_5_VALUE
        elif cell_value == Matrix.COIN_10:
            self.score += self.COIN_10_VALUE
        elif cell_value == Matrix.POWER_BOMB:
            self.bombs += 1
        elif cell_value == Matrix.POWER_GHOST:
            self.ghosts += 1

    def push_down(self) -> bool:
        """
        Empuja al jugador una fila hacia abajo por el scroll del mapa.

        Si el jugador ya está en la fila inferior, pierde.

        Returns:
            bool: True si el jugador fue empujado con éxito.
                  False si el jugador cayó fuera del mapa (pierde).
        """
        new_row = self.row + 1

        if new_row >= self._matrix.size:
            # El jugador sale del mapa: fin del juego
            self._matrix.set_cell(self.row, self.col, Matrix.FREE)
            self.is_alive = False
            return False

        # Mover al jugador una fila hacia abajo
        self._perform_move(new_row, self.col)
        return True

    def get_position(self) -> tuple[int, int]:
        """
        Retorna la posición actual del jugador.

        Returns:
            tuple[int, int]: Tupla (fila, columna) del jugador.
        """
        return (self.row, self.col)

    def get_inventory(self) -> dict:
        """
        Retorna el inventario actual de poderes del jugador.

        Returns:
            dict: Diccionario con las cantidades de cada poder.
                  Ejemplo: {'bombs': 2, 'ghosts': 1}
        """
        return {'bombs': self.bombs, 'ghosts': self.ghosts}

    def _calculate_destination(
        self,
        direction: str,
        from_row: int = None,
        from_col: int = None
    ) -> tuple[int, int]:
        """
        Calcula las coordenadas destino dada una dirección.

        Args:
            direction (str): Dirección del movimiento.
            from_row (int): Fila de origen (default: posición actual).
            from_col (int): Columna de origen (default: posición actual).

        Returns:
            tuple[int, int]: Coordenadas (fila, columna) destino.
        """
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

    def _perform_move(self, new_row: int, new_col: int) -> None:
        """
        Ejecuta el movimiento del jugador a las coordenadas indicadas.

        Limpia la celda anterior, recoge la recompensa si la hay,
        y marca la nueva celda con el valor del jugador.

        Args:
            new_row (int): Nueva fila destino.
            new_col (int): Nueva columna destino.
        """
        # Limpiar posición anterior
        self._matrix.set_cell(self.row, self.col, Matrix.FREE)

        # Recoger recompensa si existe en la celda destino
        cell_value = self._matrix.get_cell(new_row, new_col)
        if cell_value not in (Matrix.FREE, Matrix.PLAYER):
            self.collect_reward(cell_value)

        # Actualizar posición
        self.row = new_row
        self.col = new_col
        self._matrix.set_cell(self.row, self.col, Matrix.PLAYER)

    def __repr__(self) -> str:
        """Representación en cadena del jugador."""
        return (
            f"Player(pos=({self.row},{self.col}), "
            f"score={self.score}, bombs={self.bombs}, ghosts={self.ghosts})"
        )
