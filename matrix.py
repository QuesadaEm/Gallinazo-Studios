"""
Módulo: matrix.py
Descripción: Contiene la clase Matrix, que representa y gestiona
             el laberinto dinámico mediante una matriz cuadrada.
Autor: Persona A
Curso: Taller de Programación IC1803
"""

import threading
from row_generator import RowGenerator


class Matrix:
    """
    Representa el laberinto dinámico como una matriz cuadrada 2D.

    La matriz se construye progresivamente desde arriba (fila por fila)
    y, una vez completa, hace scroll continuo hacia abajo generando
    nuevas filas en la parte superior.

    Los valores de celda son:
        0  -> Celda libre
        1  -> Obstáculo (muro)
        2  -> Jugador
        3  -> Moneda de 5 puntos
        4  -> Moneda de 10 puntos
        5  -> Poder: Bomba
        6  -> Poder: Paso fantasma

    Attributes:
        size (int): Dimensión de la matriz cuadrada (NxN).
        grid (list[list[int]]): Representación 2D del laberinto.
        is_complete (bool): True cuando la matriz se llenó por primera vez.
        lock (threading.Lock): Lock para acceso seguro entre hilos.
        _row_gen (RowGenerator): Generador de filas aleatorias.
        _rows_built (int): Cantidad de filas construidas en la fase inicial.
    """

    # Constantes de celda
    FREE = 0
    OBSTACLE = 1
    PLAYER = 2
    COIN_5 = 3
    COIN_10 = 4
    POWER_BOMB = 5
    POWER_GHOST = 6

    def __init__(self, size: int):
        """
        Inicializa la matriz vacía (llena de celdas libres).

        Args:
            size (int): Dimensión NxN de la matriz. Debe ser 10, 20 o 30.

        Raises:
            ValueError: Si el tamaño no es 10, 20 o 30.
        """
        if size not in (10, 20, 30):
            raise ValueError("El tamaño debe ser 10, 20 o 30.")

        self.size = size
        self.grid: list[list[int]] = [[self.FREE] * size for _ in range(size)]
        self.is_complete: bool = False
        self.lock = threading.Lock()
        self._row_gen = RowGenerator(size)
        self._rows_built: int = 0

    def add_row(self) -> bool:
        """
        Agrega una nueva fila al laberinto.

        Durante la construcción inicial: rellena la matriz de abajo hacia
        arriba, una fila cada llamada. Cuando la matriz se completa,
        activa el modo scroll.

        En modo scroll: inserta una nueva fila en la parte superior y
        desplaza todo el contenido hacia abajo (la fila inferior se pierde).

        Returns:
            bool: True si la fila fue agregada con éxito.
        """
        with self.lock:
            if not self.is_complete:
                return self._build_initial_row()
            else:
                return self._scroll_row()

    def _build_initial_row(self) -> bool:
        """
        Agrega una fila durante la construcción inicial de la matriz.

        Las filas se insertan de arriba hacia abajo en posiciones
        decrecientes (la primera fila aparece en la cima).

        Returns:
            bool: True cuando se agrega la fila correctamente.
        """
        new_row = self._row_gen.generate()
        insert_index = self._rows_built

        if insert_index < self.size:
            self.grid[insert_index] = new_row
            self._rows_built += 1

            if self._rows_built == self.size:
                self.is_complete = True

        return True

    def _scroll_row(self) -> bool:
        """
        Desplaza el contenido de la matriz una fila hacia abajo y
        agrega una nueva fila generada en la parte superior.

        La fila que estaba en la posición inferior se elimina.

        Returns:
            bool: True cuando el scroll se realiza correctamente.
        """
        new_row = self._row_gen.generate()
        # Desplazar todo hacia abajo: mover filas [0..n-2] a [1..n-1]
        self.grid = [new_row] + self.grid[:-1]
        return True

    def get_cell(self, row: int, col: int) -> int:
        """
        Obtiene el valor de una celda específica.

        Args:
            row (int): Índice de fila (0 = superior).
            col (int): Índice de columna (0 = izquierda).

        Returns:
            int: Valor de la celda.

        Raises:
            IndexError: Si las coordenadas están fuera de rango.
        """
        if not self._in_bounds(row, col):
            raise IndexError(f"Coordenadas ({row}, {col}) fuera de rango.")
        with self.lock:
            return self.grid[row][col]

    def set_cell(self, row: int, col: int, value: int) -> None:
        """
        Establece el valor de una celda específica.

        Args:
            row (int): Índice de fila.
            col (int): Índice de columna.
            value (int): Valor a asignar (0-6).

        Raises:
            IndexError: Si las coordenadas están fuera de rango.
            ValueError: Si el valor no es válido.
        """
        if not self._in_bounds(row, col):
            raise IndexError(f"Coordenadas ({row}, {col}) fuera de rango.")
        if value not in (0, 1, 2, 3, 4, 5, 6):
            raise ValueError(f"Valor de celda inválido: {value}.")
        with self.lock:
            self.grid[row][col] = value

    def is_free(self, row: int, col: int) -> bool:
        """
        Verifica si una celda es transitable (no es obstáculo).

        Una celda es transitable si su valor es distinto de OBSTACLE (1).

        Args:
            row (int): Índice de fila.
            col (int): Índice de columna.

        Returns:
            bool: True si la celda es transitable.
        """
        if not self._in_bounds(row, col):
            return False
        with self.lock:
            return self.grid[row][col] != self.OBSTACLE

    def is_obstacle(self, row: int, col: int) -> bool:
        """
        Verifica si una celda es un obstáculo.

        Args:
            row (int): Índice de fila.
            col (int): Índice de columna.

        Returns:
            bool: True si la celda es obstáculo.
        """
        if not self._in_bounds(row, col):
            return False
        with self.lock:
            return self.grid[row][col] == self.OBSTACLE

    def get_snapshot(self) -> list[list[int]]:
        """
        Retorna una copia profunda de la matriz actual.

        Útil para que la GUI pueda leer el estado sin bloquear
        el hilo de juego durante el renderizado.

        Returns:
            list[list[int]]: Copia 2D de la matriz en su estado actual.
        """
        with self.lock:
            return [row[:] for row in self.grid]

    def find_free_cells(self) -> list[tuple[int, int]]:
        """
        Retorna las coordenadas de todas las celdas libres (valor 0).

        Útil para el RewardManager al colocar monedas y poderes
        en posiciones aleatorias.

        Returns:
            list[tuple[int, int]]: Lista de tuplas (fila, columna) libres.
        """
        with self.lock:
            return [
                (r, c)
                for r in range(self.size)
                for c in range(self.size)
                if self.grid[r][c] == self.FREE
            ]

    def _in_bounds(self, row: int, col: int) -> bool:
        """
        Verifica si las coordenadas están dentro del rango de la matriz.

        Args:
            row (int): Índice de fila.
            col (int): Índice de columna.

        Returns:
            bool: True si las coordenadas son válidas.
        """
        return 0 <= row < self.size and 0 <= col < self.size

    def __repr__(self) -> str:
        """Representación en cadena de la matriz."""
        return f"Matrix(size={self.size}, complete={self.is_complete})"

    def print_grid(self) -> None:
        """
        Imprime la matriz en consola. Útil para depuración.

        Usa caracteres visuales:
            '.' -> Libre
            '#' -> Obstáculo
            'P' -> Jugador
            '$' -> Moneda
            'B' -> Bomba
            'G' -> Paso fantasma
        """
        symbols = {
            self.FREE: '.',
            self.OBSTACLE: '#',
            self.PLAYER: 'P',
            self.COIN_5: '$',
            self.COIN_10: '€',
            self.POWER_BOMB: 'B',
            self.POWER_GHOST: 'G',
        }
        with self.lock:
            for row in self.grid:
                print(' '.join(symbols.get(cell, '?') for cell in row))
