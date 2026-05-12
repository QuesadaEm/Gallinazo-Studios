"""
Módulo: row_generator.py
Descripción: Contiene la clase RowGenerator, encargada de generar
             filas válidas para el laberinto dinámico.
Autor: Persona A
Curso: Taller de Programación IC1803
"""

import random


class RowGenerator:
    """
    Genera filas aleatorias válidas para el laberinto.

    Restricciones que cumple cada fila generada:
    - Aproximadamente 60% de celdas son obstáculos (valor 1).
    - Las secuencias de celdas libres no superan 2 consecutivas.
    - Siempre existe al menos un camino transitable.

    Attributes:
        size (int): Número de columnas de la fila (ancho de la matriz).
        obstacle_ratio (float): Proporción de obstáculos deseada (default 0.6).
    """

    # Constantes de celda
    FREE = 0
    OBSTACLE = 1

    def __init__(self, size: int, obstacle_ratio: float = 0.6):
        """
        Inicializa el generador de filas.

        Args:
            size (int): Ancho de la fila (número de columnas).
            obstacle_ratio (float): Proporción de obstáculos (0.0 a 1.0).

        Raises:
            ValueError: Si size <= 0 o obstacle_ratio está fuera de [0, 1].
        """
        if size <= 0:
            raise ValueError("El tamaño debe ser mayor que 0.")
        if not (0.0 <= obstacle_ratio <= 1.0):
            raise ValueError("obstacle_ratio debe estar entre 0.0 y 1.0.")

        self.size = size
        self.obstacle_ratio = obstacle_ratio

    def generate(self) -> list[int]:
        """
        Genera una fila aleatoria válida para el laberinto.

        El algoritmo coloca celdas de izquierda a derecha. Si se han
        colocado 2 celdas libres consecutivas, la siguiente es forzada
        a ser obstáculo. De lo contrario, se decide aleatoriamente
        según obstacle_ratio.

        Returns:
            list[int]: Lista de enteros donde FREE=0 y OBSTACLE=1.
        """
        row = []
        consecutive_free = 0

        for _ in range(self.size):
            if consecutive_free >= 2:
                # Forzar obstáculo para respetar la restricción
                cell = self.OBSTACLE
                consecutive_free = 0
            else:
                # Decidir aleatoriamente
                cell = self.OBSTACLE if random.random() < self.obstacle_ratio else self.FREE
                if cell == self.FREE:
                    consecutive_free += 1
                else:
                    consecutive_free = 0

            row.append(cell)

        # Garantizar que la fila tenga al menos una celda libre
        if self.FREE not in row:
            free_index = random.randint(0, self.size - 1)
            row[free_index] = self.FREE

        return row

    def generate_empty_row(self) -> list[int]:
        """
        Genera una fila completamente libre (sin obstáculos).

        Útil para la fila inicial donde aparece el jugador.

        Returns:
            list[int]: Lista de ceros del tamaño de la fila.
        """
        return [self.FREE] * self.size

    def __repr__(self) -> str:
        """Representación en cadena del generador."""
        return f"RowGenerator(size={self.size}, obstacle_ratio={self.obstacle_ratio})"
