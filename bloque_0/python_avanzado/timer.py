
from __future__ import annotations
import time
from typing import Optional
from contextlib import contextmanager
#time.perf_counter() -> Devuelve el valor del contador de rendimiento en segundos como un número de punto flotante. El contador de rendimiento es el reloj más preciso disponible en el sistema y se utiliza para medir intervalos de tiempo cortos.
class Timer:
    """Cronómetro simple con métodos explícitos de inicio y reporte."""

    def __init__(self, label: str = "Timer") -> None:
        self.label = label
        self._started_at: Optional[float] = None
        self._elapsed: Optional[float] = None

    @property
    def elapsed(self) -> float:
        """Devuelve el tiempo transcurrido desde `start` o el último reporte, sin imprimirlo.

        Si el cronómetro no se ha iniciado, devuelve 0.0.
        """
        if self._started_at is None:
            return 0.0
        return time.perf_counter() - self._started_at
    def __enter__(self):
        self._started_at = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> float:
        """Devuelve e imprime el tiempo transcurrido desde `start`."""

        if self._started_at is None:
            raise RuntimeError("Timer.report() llamado antes de start().")

        elapsed = time.perf_counter() - self._started_at
        print(f"{self.label}: {elapsed:.6f} segundos")
        return elapsed

def paso_1():
    sum(range(1_000_000))

def paso_2():
    sum(range(200_000))

if __name__ == "__main__":
    with Timer("timer_con_pasos") as t_con_pasos:
        paso_1()
        total = t_con_pasos.elapsed
        print(f"Total de paso 1: {total}")
        paso_2()
        total = t_con_pasos.elapsed
        print(f"Total de paso 2: {total}")
    with Timer("timer_sin_pasos") as t_sp:
        time.sleep(5)
    print(f"Total de timer sin pasos: {t_sp.elapsed}")
    with Timer("timer_list_comprehension") as t_ls:
        datos = [x**2 for x in range(1000000)]
    print(f"Total de timer list comprehension: {t_ls.elapsed}")
    with Timer("timer_sin_as"):
        paso_1()