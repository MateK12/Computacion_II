import unittest
from unittest.mock import patch

from src.analizadores.threads import AnalyzerThreads


class MockProcFS:
    """Doble de prueba: estructura {pid: {tid: (stat, status)}}. Para simular
    muertes, registrá el PID en `dead_pids` (falla list_tids) o el par (pid, tid)
    en `dead_tids` (falla la lectura del thread)."""

    def __init__(self, threads_por_pid, dead_pids=None, dead_tids=None):
        self.threads_por_pid = threads_por_pid
        self.dead_pids = dead_pids or {}
        self.dead_tids = dead_tids or {}

    def list_tids(self, pid):
        if pid in self.dead_pids:
            raise self.dead_pids[pid]
        return list(self.threads_por_pid[pid].keys())

    def read_thread_stat(self, pid, tid):
        if (pid, tid) in self.dead_tids:
            raise self.dead_tids[(pid, tid)]
        return self.threads_por_pid[pid][tid][0]

    def read_thread_status(self, pid, tid):
        if (pid, tid) in self.dead_tids:
            raise self.dead_tids[(pid, tid)]
        return self.threads_por_pid[pid][tid][1]


def mock_stat(utime=0, stime=0, starttime=1000, comm="worker", state="S"):
    return {
        "comm": comm,
        "state": state,
        "utime": utime,
        "stime": stime,
        "starttime": starttime,
    }


def mock_status(vol=0, nonvol=0):
    # status crudo: los valores son strings, como los devuelve parse_status
    return {
        "voluntary_ctxt_switches": str(vol),
        "nonvoluntary_ctxt_switches": str(nonvol),
    }


class FakeClock:
    def __init__(self, t):
        self.t = t

    def time(self):
        return self.t


class TestThreads(unittest.TestCase):

    def setUp(self):
        self.clock = FakeClock(1000.0)
        patcher = patch("src.analizadores.threads.time", self.clock)
        self.addCleanup(patcher.stop)
        patcher.start()

    def _analyzer(self, threads=None, dead_pids=None, dead_tids=None, pids=None):
        a = AnalyzerThreads(
            MockProcFS(threads or {}, dead_pids, dead_tids),
            list(pids or []),
            {},
            1,
        )
        a._clk_tck = 100  # fijo -> independiente del SC_CLK_TCK real
        return a

    def test_primera_vez_cpu_none(self):
        """El primer ciclo de un thread no tiene previo -> cpu None."""
        a = self._analyzer(
            threads={1: {1: (mock_stat(utime=10), mock_status())}}, pids=[1]
        )
        a._ciclo()
        self.assertIsNone(a.snapshot["threads"]["data"][1][1]["cpu"])

    def test_segundo_ciclo_calcula_cpu_por_thread(self):
        """Delta de 50 jiffies en 1s, clk_tck=100 -> 50%."""
        a = self._analyzer(
            threads={1: {1: (mock_stat(utime=10), mock_status())}}, pids=[1]
        )
        a._ciclo()
        a.procfs.threads_por_pid[1][1] = (mock_stat(utime=60), mock_status())
        self.clock.t = 1001.0
        a._ciclo()
        self.assertAlmostEqual(a.snapshot["threads"]["data"][1][1]["cpu"], 50.0)

    def test_threads_de_un_mismo_pid_son_independientes(self):
        """Dos TIDs bajo el mismo PID computan su CPU por separado."""
        a = self._analyzer(
            threads={
                1: {
                    100: (mock_stat(utime=0, starttime=1000), mock_status()),
                    200: (mock_stat(utime=0, starttime=2000), mock_status()),
                }
            },
            pids=[1],
        )
        a._ciclo()
        a.procfs.threads_por_pid[1][100] = (mock_stat(utime=50, starttime=1000), mock_status())
        a.procfs.threads_por_pid[1][200] = (mock_stat(utime=10, starttime=2000), mock_status())
        self.clock.t = 1001.0
        a._ciclo()
        data = a.snapshot["threads"]["data"][1]
        self.assertAlmostEqual(data[100]["cpu"], 50.0)
        self.assertAlmostEqual(data[200]["cpu"], 10.0)

    def test_reuso_de_tid_devuelve_none(self):
        """Mismo TID pero starttime distinto (otro thread) -> None, no delta basura."""
        a = self._analyzer(
            threads={1: {5: (mock_stat(utime=100, starttime=1000), mock_status())}},
            pids=[1],
        )
        a._ciclo()
        a.procfs.threads_por_pid[1][5] = (mock_stat(utime=5, starttime=9999), mock_status())
        self.clock.t = 1001.0
        a._ciclo()
        self.assertIsNone(a.snapshot["threads"]["data"][1][5]["cpu"])

    def test_expone_name_state_y_ctxt(self):
        """name/state salen de stat; ctxt (vol/nonvol) salen de status como int."""
        a = self._analyzer(
            threads={
                1: {1: (mock_stat(comm="hilo-io", state="R"), mock_status(vol=7, nonvol=3))}
            },
            pids=[1],
        )
        a._ciclo()
        t = a.snapshot["threads"]["data"][1][1]
        self.assertEqual(t["name"], "hilo-io")
        self.assertEqual(t["state"], "R")
        self.assertEqual(t["ctxt"], {"vol": 7, "nonvol": 3})

    def test_ciclo_saltea_thread_muerto(self):
        """Un TID cuya lectura lanza FileNotFoundError no aparece en data."""
        a = self._analyzer(
            threads={1: {10: (mock_stat(), mock_status()), 20: (mock_stat(), mock_status())}},
            dead_tids={(1, 20): FileNotFoundError()},
            pids=[1],
        )
        a._ciclo()
        data = a.snapshot["threads"]["data"][1]
        self.assertIn(10, data)
        self.assertNotIn(20, data)

    def test_ciclo_saltea_proceso_muerto(self):
        """Un PID cuyo list_tids lanza ProcessLookupError no aparece en data."""
        a = self._analyzer(
            threads={1: {1: (mock_stat(), mock_status())}, 2: {2: (mock_stat(), mock_status())}},
            dead_pids={2: ProcessLookupError()},
            pids=[1, 2],
        )
        a._ciclo()
        data = a.snapshot["threads"]["data"]
        self.assertIn(1, data)
        self.assertNotIn(2, data)

    def test_poda_saca_pids_muertos_de_prev(self):
        """Un PID que desaparece de shared_pids no queda en _prev (sin fuga)."""
        a = self._analyzer(
            threads={1: {1: (mock_stat(), mock_status())}, 2: {2: (mock_stat(), mock_status())}},
            pids=[1, 2],
        )
        a._ciclo()
        self.assertIn(2, a._prev)
        a.shared_pids.remove(2)
        self.clock.t = 1001.0
        a._ciclo()
        self.assertNotIn(2, a._prev)
        self.assertIn(1, a._prev)

    def test_ciclo_publica_la_clave_threads_con_ts_y_data(self):
        """Tras _ciclo(), snapshot['threads'] tiene la forma {'ts':..., 'data':{...}}."""
        a = self._analyzer()
        a._ciclo()
        self.assertIn("threads", a.snapshot)
        self.assertIn("ts", a.snapshot["threads"])
        self.assertIn("data", a.snapshot["threads"])


if __name__ == "__main__":
    unittest.main()
