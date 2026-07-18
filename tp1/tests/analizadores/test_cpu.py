import unittest
from unittest.mock import patch

from src.analizadores.cpu import AnalyzerCPU


class MockProcFS:
    """Doble de prueba: devuelve el stat crudo por PID. Para simular un proceso
    que muere a mitad de lectura, registrá su PID en `dead` con la excepción a
    lanzar."""

    def __init__(self, stats_por_pid, dead=None):
        self.stats_por_pid = stats_por_pid
        self.dead = dead or {}

    def read_stat(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.stats_por_pid[pid]


def mock_stat(utime=0, stime=0, starttime=1000):
    """stat crudo mínimo: el analizador solo usa utime/stime/starttime."""
    return {"utime": utime, "stime": stime, "starttime": starttime}


class FakeClock:
    """Reloj falso: time() devuelve self.t. Avanzá self.t entre ciclos para
    controlar el 'elapsed' de forma determinista, sin depender del reloj real."""

    def __init__(self, t):
        self.t = t

    def time(self):
        return self.t


class TestCPU(unittest.TestCase):

    def setUp(self):
        # Reemplazamos el módulo `time` de cpu.py por un reloj controlable.
        self.clock = FakeClock(1000.0)
        patcher = patch("src.analizadores.cpu.time", self.clock)
        self.addCleanup(patcher.stop)
        patcher.start()

    def _analyzer(self, stats=None, dead=None, pids=None):
        a = AnalyzerCPU(MockProcFS(stats or {}, dead), list(pids or []), {}, 1)
        a._clk_tck = 100  # fijo -> tests independientes del SC_CLK_TCK de la máquina
        return a

    def test_primera_vez_devuelve_none(self):
        """El primer ciclo de un PID no tiene lectura previa -> cpu None."""
        a = self._analyzer(stats={1: mock_stat(utime=10)}, pids=[1])
        a._ciclo()
        self.assertIsNone(a.snapshot["cpu"]["data"][1])

    def test_segundo_ciclo_calcula_cpu(self):
        """Delta de 50 jiffies en 1s de reloj, clk_tck=100 -> 50%."""
        a = self._analyzer(stats={1: mock_stat(utime=10)}, pids=[1])
        a._ciclo()                                        # t=1000 -> None
        a.procfs.stats_por_pid[1] = mock_stat(utime=60)   # +50 jiffies
        self.clock.t = 1001.0                             # elapsed = 1s
        a._ciclo()
        self.assertAlmostEqual(a.snapshot["cpu"]["data"][1], 50.0)

    def test_elapsed_distinto_de_uno(self):
        """Mismo delta (50) pero en 2s -> 25% (divide por elapsed)."""
        a = self._analyzer(stats={1: mock_stat(utime=0)}, pids=[1])
        a._ciclo()
        a.procfs.stats_por_pid[1] = mock_stat(utime=50)
        self.clock.t = 1002.0                             # elapsed = 2s
        a._ciclo()
        self.assertAlmostEqual(a.snapshot["cpu"]["data"][1], 25.0)

    def test_puede_superar_100_por_multiples_nucleos(self):
        """300 jiffies en 1s -> 300% (varios núcleos a la vez, es válido)."""
        a = self._analyzer(stats={1: mock_stat(utime=0)}, pids=[1])
        a._ciclo()
        a.procfs.stats_por_pid[1] = mock_stat(utime=300)
        self.clock.t = 1001.0
        a._ciclo()
        self.assertAlmostEqual(a.snapshot["cpu"]["data"][1], 300.0)

    def test_proceso_sin_actividad_da_cero(self):
        """Sin cambio en jiffies entre ciclos -> 0%."""
        a = self._analyzer(stats={1: mock_stat(utime=100)}, pids=[1])
        a._ciclo()
        self.clock.t = 1001.0                             # mismo stat, sin actividad
        a._ciclo()
        self.assertAlmostEqual(a.snapshot["cpu"]["data"][1], 0.0)

    def test_reuso_de_pid_devuelve_none(self):
        """Mismo PID pero starttime distinto (otro proceso) -> None, no delta basura."""
        a = self._analyzer(stats={1: mock_stat(utime=100, starttime=1000)}, pids=[1])
        a._ciclo()
        # el PID 1 fue reasignado a un proceso nuevo (starttime distinto)
        a.procfs.stats_por_pid[1] = mock_stat(utime=5, starttime=9999)
        self.clock.t = 1001.0
        a._ciclo()
        self.assertIsNone(a.snapshot["cpu"]["data"][1])

    def test_poda_saca_pids_muertos_de_prev(self):
        """Un PID que desaparece de shared_pids no queda en _prev (sin fuga)."""
        a = self._analyzer(
            stats={1: mock_stat(starttime=1000), 2: mock_stat(starttime=2000)},
            pids=[1, 2],
        )
        a._ciclo()
        self.assertIn(2, a._prev)                         # vivo en el 1er ciclo
        a.shared_pids.remove(2)                           # el PID 2 muere
        self.clock.t = 1001.0
        a._ciclo()
        self.assertNotIn(2, a._prev)                      # podado
        self.assertIn(1, a._prev)

    def test_ciclo_saltea_proceso_muerto(self):
        """Un PID cuyo read_stat lanza FileNotFoundError no aparece en data."""
        a = self._analyzer(
            stats={1: mock_stat(), 2: mock_stat()},
            dead={2: FileNotFoundError()},
            pids=[1, 2],
        )
        a._ciclo()
        data = a.snapshot["cpu"]["data"]
        self.assertIn(1, data)
        self.assertNotIn(2, data)

    def test_ciclo_publica_la_clave_cpu_con_ts_y_data(self):
        """Tras _ciclo(), snapshot['cpu'] tiene la forma {'ts': ..., 'data': {...}}."""
        a = self._analyzer()
        a._ciclo()
        self.assertIn("cpu", a.snapshot)
        self.assertIn("ts", a.snapshot["cpu"])
        self.assertIn("data", a.snapshot["cpu"])


if __name__ == "__main__":
    unittest.main()
