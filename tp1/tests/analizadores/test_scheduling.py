import unittest
from unittest.mock import patch

from src.analizadores.scheduling import AnalyzerScheduling


class MockProcFS:
    """Doble de prueba: dobla las tres lecturas que usa el analizador
    (stat/schedstat/status) por PID. Para simular un proceso que muere a mitad
    de lectura, registrá su PID en `dead` con la excepción a lanzar."""

    def __init__(self, stats=None, schedstats=None, statuses=None, dead=None):
        self.stats = stats or {}
        self.schedstats = schedstats or {}
        self.statuses = statuses or {}
        self.dead = dead or {}

    def read_stat(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.stats[pid]

    def read_schedstat(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.schedstats[pid]

    def read_status(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.statuses[pid]


def mock_stat(priority=20, nice=0, rt_priority=0, policy=0, starttime=1000):
    """stat crudo mínimo: solo los campos que consume el analizador."""
    return {
        "priority": priority,
        "nice": nice,
        "rt_priority": rt_priority,
        "policy": policy,
        "starttime": starttime,
    }


def mock_schedstat(cpu_time=0, runqueue_wait=0, timeslices=0):
    return {"cpu_time": cpu_time, "runqueue_wait": runqueue_wait, "timeslices": timeslices}


def mock_status(affinity="0-7"):
    return {"Cpus_allowed_list": affinity}


class FakeClock:
    """Reloj falso: time() devuelve self.t. Avanzá self.t entre ciclos para
    controlar el 'elapsed' de forma determinista."""

    def __init__(self, t):
        self.t = t

    def time(self):
        return self.t


class TestScheduling(unittest.TestCase):

    def setUp(self):
        self.clock = FakeClock(1000.0)
        patcher = patch("src.analizadores.scheduling.time", self.clock)
        self.addCleanup(patcher.stop)
        patcher.start()

    def _analyzer(self, stats=None, schedstats=None, statuses=None, dead=None, pids=None):
        procfs = MockProcFS(stats or {}, schedstats or {}, statuses or {}, dead)
        return AnalyzerScheduling(procfs, list(pids or []), {}, 1)

    def test_primera_vez_delta_none_pero_estaticos_presentes(self):
        """Sin previo: cpu_usage/runqueue_wait_pct None, pero nice/policy ya salen."""
        a = self._analyzer(
            stats={1: mock_stat(nice=5, policy=0)},
            schedstats={1: mock_schedstat()},
            statuses={1: mock_status()},
            pids=[1],
        )
        a._ciclo()
        d = a.snapshot["scheduling"]["data"][1]
        self.assertIsNone(d["cpu_usage"])
        self.assertIsNone(d["runqueue_wait_pct"])
        self.assertEqual(d["nice"], 5)
        self.assertEqual(d["policy"], "SCHED_NORMAL")

    def test_segundo_ciclo_calcula_cpu_usage(self):
        """delta 5e8 ns en 1s -> 0.5s de CPU -> 50%."""
        a = self._analyzer(
            stats={1: mock_stat()},
            schedstats={1: mock_schedstat(cpu_time=0)},
            statuses={1: mock_status()},
            pids=[1],
        )
        a._ciclo()
        a.procfs.schedstats[1] = mock_schedstat(cpu_time=500_000_000)
        self.clock.t = 1001.0
        a._ciclo()
        self.assertAlmostEqual(a.snapshot["scheduling"]["data"][1]["cpu_usage"], 50.0)

    def test_segundo_ciclo_calcula_runqueue_wait_pct(self):
        """delta 5e8 ns esperando en runqueue en 1s -> 50%."""
        a = self._analyzer(
            stats={1: mock_stat()},
            schedstats={1: mock_schedstat(runqueue_wait=0)},
            statuses={1: mock_status()},
            pids=[1],
        )
        a._ciclo()
        a.procfs.schedstats[1] = mock_schedstat(runqueue_wait=500_000_000)
        self.clock.t = 1001.0
        a._ciclo()
        self.assertAlmostEqual(
            a.snapshot["scheduling"]["data"][1]["runqueue_wait_pct"], 50.0
        )

    def test_elapsed_distinto_de_uno_normaliza(self):
        """Mismo delta (5e8 ns) pero en 2s -> 25%."""
        a = self._analyzer(
            stats={1: mock_stat()},
            schedstats={1: mock_schedstat(cpu_time=0)},
            statuses={1: mock_status()},
            pids=[1],
        )
        a._ciclo()
        a.procfs.schedstats[1] = mock_schedstat(cpu_time=500_000_000)
        self.clock.t = 1002.0                             # elapsed = 2s
        a._ciclo()
        self.assertAlmostEqual(a.snapshot["scheduling"]["data"][1]["cpu_usage"], 25.0)

    def test_traduccion_de_policy(self):
        """Cada entero del kernel se traduce a su nombre; desconocido -> UNKNOWN."""
        self.assertEqual(AnalyzerScheduling._parse_policy(0), "SCHED_NORMAL")
        self.assertEqual(AnalyzerScheduling._parse_policy(1), "SCHED_FIFO")
        self.assertEqual(AnalyzerScheduling._parse_policy(2), "SCHED_RR")
        self.assertEqual(AnalyzerScheduling._parse_policy(3), "SCHED_BATCH")
        self.assertEqual(AnalyzerScheduling._parse_policy(5), "SCHED_IDLE")
        self.assertEqual(AnalyzerScheduling._parse_policy(6), "SCHED_DEADLINE")
        self.assertEqual(AnalyzerScheduling._parse_policy(99), "UNKNOWN(99)")

    def test_reuso_de_pid_vuelve_a_none(self):
        """Mismo PID con starttime distinto (otro proceso) -> delta None, no basura."""
        a = self._analyzer(
            stats={1: mock_stat(starttime=1000)},
            schedstats={1: mock_schedstat(cpu_time=100)},
            statuses={1: mock_status()},
            pids=[1],
        )
        a._ciclo()
        a.procfs.stats[1] = mock_stat(starttime=9999)     # PID reasignado
        a.procfs.schedstats[1] = mock_schedstat(cpu_time=500_000_000)
        self.clock.t = 1001.0
        a._ciclo()
        self.assertIsNone(a.snapshot["scheduling"]["data"][1]["cpu_usage"])

    def test_poda_saca_pids_muertos_de_prev(self):
        """Un PID que desaparece de shared_pids no queda en _prev."""
        a = self._analyzer(
            stats={1: mock_stat(starttime=1000), 2: mock_stat(starttime=2000)},
            schedstats={1: mock_schedstat(), 2: mock_schedstat()},
            statuses={1: mock_status(), 2: mock_status()},
            pids=[1, 2],
        )
        a._ciclo()
        self.assertIn(2, a._prev)
        a.shared_pids.remove(2)
        self.clock.t = 1001.0
        a._ciclo()
        self.assertNotIn(2, a._prev)
        self.assertIn(1, a._prev)

    def test_ciclo_saltea_proceso_muerto(self):
        """Un PID cuya lectura lanza FileNotFoundError no aparece en data."""
        a = self._analyzer(
            stats={1: mock_stat(), 2: mock_stat()},
            schedstats={1: mock_schedstat(), 2: mock_schedstat()},
            statuses={1: mock_status(), 2: mock_status()},
            dead={2: FileNotFoundError()},
            pids=[1, 2],
        )
        a._ciclo()
        data = a.snapshot["scheduling"]["data"]
        self.assertIn(1, data)
        self.assertNotIn(2, data)

    def test_ciclo_publica_clave_scheduling_con_ts_y_data(self):
        """Tras _ciclo(), snapshot['scheduling'] tiene forma {'ts': ..., 'data': {...}}."""
        a = self._analyzer()
        a._ciclo()
        self.assertIn("scheduling", a.snapshot)
        self.assertIn("ts", a.snapshot["scheduling"])
        self.assertIn("data", a.snapshot["scheduling"])

    def test_affinity_default_cuando_falta(self):
        """Si status no trae Cpus_allowed_list, affinity cae a 'N/A'."""
        a = self._analyzer(
            stats={1: mock_stat()},
            schedstats={1: mock_schedstat()},
            statuses={1: {}},                             # sin Cpus_allowed_list
            pids=[1],
        )
        a._ciclo()
        self.assertEqual(a.snapshot["scheduling"]["data"][1]["affinity"], "N/A")


if __name__ == "__main__":
    unittest.main()
