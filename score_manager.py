"""
Módulo: score_manager.py
Descripción: Contiene la clase ScoreManager, encargada de gestionar
             la persistencia del Top 20 de mejores puntajes históricos,
             separados por tamaño de matriz.
Autor: Persona A
Curso: Taller de Programación IC1803
"""

import os


class ScoreManager:
    """
    Gestiona el registro y persistencia del Top 20 de puntajes.

    Cada tamaño de matriz (10x10, 20x20, 30x30) tiene su propio
    archivo de puntajes. Los puntajes se almacenan ordenados de
    mayor a menor y se limitan a los 20 mejores.

    Formato de archivo (una entrada por línea):
        NombreJugador,puntaje
        Ejemplo: Mateo,350

    Attributes:
        size (int): Tamaño de la matriz de la partida actual.
        scores_dir (str): Ruta al directorio donde se guardan los archivos.
        filepath (str): Ruta completa al archivo de puntajes correspondiente.
        MAX_SCORES (int): Límite máximo de puntajes almacenados (20).
    """

    MAX_SCORES = 20

    def __init__(self, size: int, scores_dir: str = "scores"):
        """
        Inicializa el gestor de puntajes para un tamaño de matriz dado.

        Crea el directorio de puntajes si no existe.

        Args:
            size (int): Tamaño de la matriz (10, 20 o 30).
            scores_dir (str): Carpeta donde se guardan los archivos de puntajes.

        Raises:
            ValueError: Si el tamaño no es 10, 20 o 30.
        """
        if size not in (10, 20, 30):
            raise ValueError("El tamaño debe ser 10, 20 o 30.")

        self.size = size
        self.scores_dir = scores_dir
        self.filepath = os.path.join(scores_dir, f"scores_{size}x{size}.txt")

        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """
        Crea el directorio de puntajes si no existe.
        """
        os.makedirs(self.scores_dir, exist_ok=True)

    def load_scores(self) -> list[tuple[str, int]]:
        """
        Carga los puntajes desde el archivo correspondiente.

        Si el archivo no existe o está vacío, retorna una lista vacía.
        Las líneas malformadas se omiten silenciosamente.

        Returns:
            list[tuple[str, int]]: Lista de tuplas (nombre, puntaje)
                                   ordenada de mayor a menor puntaje.
        """
        if not os.path.exists(self.filepath):
            return []

        scores = []

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.rsplit(",", 1)  # Split por la última coma
                    if len(parts) != 2:
                        continue
                    name, score_str = parts
                    try:
                        score = int(score_str)
                        scores.append((name.strip(), score))
                    except ValueError:
                        continue  # Línea malformada, se omite
        except OSError:
            return []

        # Ordenar de mayor a menor y retornar
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def save_scores(self, scores: list[tuple[str, int]]) -> None:
        """
        Guarda la lista de puntajes en el archivo correspondiente.

        Solo guarda los primeros MAX_SCORES (20) puntajes.

        Args:
            scores (list[tuple[str, int]]): Lista de tuplas (nombre, puntaje).

        Raises:
            OSError: Si ocurre un error al escribir el archivo.
        """
        # Ordenar y limitar al Top 20
        scores_sorted = sorted(scores, key=lambda x: x[1], reverse=True)
        top_scores = scores_sorted[:self.MAX_SCORES]

        with open(self.filepath, "w", encoding="utf-8") as f:
            for name, score in top_scores:
                f.write(f"{name},{score}\n")

    def add_score(self, name: str, score: int) -> tuple[bool, int]:
        """
        Agrega un nuevo puntaje al registro histórico.

        Carga los puntajes existentes, agrega el nuevo, ordena y guarda.
        Si el puntaje entra en el Top 20, se actualiza el archivo.

        Args:
            name (str): Nombre del jugador.
            score (int): Puntaje obtenido en la partida.

        Returns:
            tuple[bool, int]: 
                - bool: True si el puntaje entró en el Top 20.
                - int: Posición en el ranking (1-indexed). 
                       0 si no entró en el Top 20.

        Raises:
            ValueError: Si el nombre está vacío o el puntaje es negativo.
        """
        if not name or not name.strip():
            raise ValueError("El nombre del jugador no puede estar vacío.")
        if score < 0:
            raise ValueError("El puntaje no puede ser negativo.")

        name = name.strip()
        current_scores = self.load_scores()

        # Verificar si entraría en el Top 20 antes de guardar
        qualifies = (
            len(current_scores) < self.MAX_SCORES or
            score > current_scores[-1][1]
        )

        if not qualifies:
            return False, 0

        # Agregar y guardar
        current_scores.append((name, score))
        current_scores.sort(key=lambda x: x[1], reverse=True)
        top_scores = current_scores[:self.MAX_SCORES]
        self.save_scores(top_scores)

        # Calcular posición (1-indexed)
        position = next(
            i + 1
            for i, (n, s) in enumerate(top_scores)
            if n == name and s == score
        )

        return True, position

    def is_top_20(self, score: int) -> bool:
        """
        Verifica si un puntaje entraría en el Top 20 actual.

        Útil para mostrar un mensaje al jugador antes de pedirle
        su nombre.

        Args:
            score (int): Puntaje a evaluar.

        Returns:
            bool: True si el puntaje clasificaría en el Top 20.
        """
        scores = self.load_scores()
        if len(scores) < self.MAX_SCORES:
            return True
        return score > scores[-1][1]

    def get_top_scores(self) -> list[tuple[str, int]]:
        """
        Retorna el Top 20 de puntajes históricos para la matriz actual.

        Returns:
            list[tuple[str, int]]: Lista de hasta 20 tuplas (nombre, puntaje),
                                   ordenada de mayor a menor.
        """
        return self.load_scores()[:self.MAX_SCORES]

    def clear_scores(self) -> None:
        """
        Elimina todos los puntajes del archivo actual.

        Útil para pruebas o si el usuario desea reiniciar el registro.
        """
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def __repr__(self) -> str:
        """Representación en cadena del gestor de puntajes."""
        return (
            f"ScoreManager(size={self.size}, "
            f"file='{self.filepath}', "
            f"scores={len(self.load_scores())})"
        )
