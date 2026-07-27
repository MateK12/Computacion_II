import unittest

from src.analizadores.memory import AnalyzerMemory


class MockProcFS:
    """Doble de prueba: devuelve un status fijo por PID. Para simular un proceso
    que muere a mitad de lectura, registrá su PID en `dead` con la excepción a lanzar."""

    def __init__(self, status_por_pid, dead=None):
        self.status_por_pid = status_por_pid
        self.dead = dead or {}
        self.dead_entre_lecturas = {}  # muere DESPUÉS de read_status, antes de read_stat

    def read_status(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.status_por_pid[pid]

    def read_stat(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        if pid in self.dead_entre_lecturas:
            raise self.dead_entre_lecturas[pid]
        return self.status_por_pid[pid]

def mock_status(**overrides):
    """Status de un proceso normal, con sección Vm* completa (formato real de /proc)."""
    base = {
        "VmSize": "1282704 kB",
        "VmRSS": "7240 kB",
        "VmHWM": "7240 kB",
        "VmData": "1200024 kB",
        "VmStk": "136 kB",
        "VmExe": "54264 kB",
        "VmLib": "2268 kB",
        "VmSwap": "0 kB",
    }
    base.update(overrides)
    return base
def mock_stat(**overrides):
    """Stat de un proceso normal, con starttime y contadores de page faults."""
    base = {
        "starttime": 0,
        "minflt": 10,
        "cminflt": 20,
        "majflt": 5,
        "cmajflt": 2,
    }
    base.update(overrides)
    return base

def status_kernel_thread():
    """Status de un kernel thread (kthreadd, kworker, ...): SIN ninguna línea Vm*,
    porque no tiene mm_struct / espacio de direcciones de usuario."""
    return {
        "Name": "kworker/0:1",
        "State": "I (idle)",
        "PPid": "2",
        "Threads": "1",
    }


class TestAnalyzerMemory(unittest.TestCase):

    def _analyzer(self):
        return AnalyzerMemory(MockProcFS({}), [], {}, 1)

    def test_extract_mapea_los_campos_vm(self):
        """_extract devuelve los 8 campos vm_* desde el status crudo de un proceso normal."""
        resultado = self._analyzer()._extract(mock_status())
        self.assertEqual(
            resultado,
            {
                "vm_size": 1282704,
                "vm_rss": 7240,
                "vm_hwm": 7240,
                "vm_data": 1200024,
                "vm_stack": 136,
                "vm_exe": 54264,
                "vm_lib": 2268,
                "vm_swap": 0,
            },
        )

    def test_extract_kernel_thread_da_none_y_no_explota(self):
        """Un kernel thread no tiene sección Vm*: todos los campos salen None (no KeyError)."""
        resultado = self._analyzer()._extract(status_kernel_thread())
        self.assertTrue(all(v is None for v in resultado.values()))

    def test_extract_convierte_kb_a_int(self):
        """El valor '7240 kB' se guarda como int 7240 (sin la unidad)."""
        resultado = self._analyzer()._extract(mock_status(VmRSS="7240 kB"))
        self.assertIsInstance(resultado["vm_rss"], int)
        self.assertEqual(resultado["vm_rss"], 7240)

    def test_ciclo_publica_la_clave_memory_con_ts_y_data(self):
        """Tras _ciclo(), snapshot['memory'] tiene la forma {'ts': ..., 'data': {...}}."""
        analyzer = self._analyzer()
        analyzer._ciclo()
        self.assertIn("memory", analyzer.snapshot)
        self.assertIn("ts", analyzer.snapshot["memory"])
        self.assertIn("data", analyzer.snapshot["memory"])

    def test_ciclo_indexa_la_data_por_pid(self):
        """snapshot['memory']['data'] tiene una entrada por cada PID vivo."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1, 2])
        analyzer.procfs.status_por_pid.update(
            {1: mock_stat(minflt=10, cminflt=20, majflt=5, cmajflt=2), 2: mock_stat(minflt=15, cminflt=25, majflt=7, cmajflt=3)}
        )
        analyzer._ciclo()
        data = analyzer.snapshot["memory"]["data"]
        self.assertIn(1, data)
        self.assertIn(2, data)

        # primer ciclo: sin base previa contra la cual restar, los 4 deltas son None
        self.assertIsNone(data[1]["minflt_delta"])
        self.assertIsNone(data[1]["cminflt_delta"])
        self.assertIsNone(data[1]["majflt_delta"])
        self.assertIsNone(data[1]["cmajflt_delta"])

    def test_ciclo_saltea_proceso_muerto(self):
        """Un PID que lanza FileNotFoundError/ProcessLookupError no aparece en data."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1, 2])
        analyzer.procfs.status_por_pid.update(
            {1: mock_stat(minflt=10, cminflt=20, majflt=5, cmajflt=2), 2: mock_stat(minflt=15, cminflt=25, majflt=7, cmajflt=3)}
        )
        analyzer.procfs.dead[2] = FileNotFoundError()
        analyzer._ciclo()
        data = analyzer.snapshot["memory"]["data"]
        self.assertIn(1, data)
        self.assertNotIn(2, data)

    def test_ciclo_reconstruye_prev(self):
        """Tras _ciclo(), _prev tiene la info de fault counts y starttime de cada PID."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1])
        analyzer.procfs.status_por_pid.update(
            {1: mock_stat(minflt=10, cminflt=20, majflt=5, cmajflt=2)}
        )
        analyzer._ciclo()
        prev = analyzer._prev
        self.assertIn("starttime", prev[1])
        self.assertEqual(prev[1]["starttime"], 0)  # starttime default en mock_status
        self.assertEqual(prev[1]["majflt"], 5)
        self.assertEqual(prev[1]["minflt"], 10)
        self.assertEqual(prev[1]["cminflt"], 20)
        self.assertEqual(prev[1]["cmajflt"], 2)

    def test_ciclo_pid_reusado_publica_deltas_none(self):
        """Si un PID fue reusado por otro proceso (starttime distinto), los deltas se
        publican como None: restar contra el previo mezclaría contadores de dos procesos."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1])
        analyzer.procfs.status_por_pid.update(
            {1: mock_stat(minflt=10, cminflt=20, majflt=5, cmajflt=2, starttime=10)}
        )
        analyzer._ciclo()
        # ahora el mismo PID 1 es reusado por otro proceso (starttime distinto)
        analyzer.procfs.status_por_pid.update(
            {1: mock_stat(minflt=15, cminflt=25, majflt=7, cmajflt=3, starttime=20)}
        )
        analyzer._ciclo()
        data = analyzer.snapshot["memory"]["data"]
        self.assertIsNone(data[1]["minflt_delta"])   # sin _guard daría 15-10=5
        self.assertIsNone(data[1]["cminflt_delta"])
        self.assertIsNone(data[1]["majflt_delta"])
        self.assertIsNone(data[1]["cmajflt_delta"])

        self.assertEqual(analyzer._prev[1]["starttime"], 20)

    def test_ciclo_fault_deltas(self):
        """_ciclo() publica los deltas de page faults (acumulado actual - previo)."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1])
        analyzer.procfs.status_por_pid.update(
            {1: mock_stat(minflt=10, cminflt=20, majflt=5, cmajflt=2)}
        )
        analyzer._ciclo()
        # ahora el mismo PID 1 tiene más page faults
        analyzer.procfs.status_por_pid.update(
            {1: mock_stat(minflt=15, cminflt=25, majflt=7, cmajflt=3)}
        )
        analyzer._ciclo()
        data = analyzer.snapshot["memory"]["data"]
        self.assertIn(1, data)
        self.assertEqual(data[1]["majflt_delta"], 2)  # 7 - 5
        self.assertEqual(data[1]["minflt_delta"], 5)  # 15 - 10
        self.assertEqual(data[1]["cminflt_delta"], 5)  # 25 - 20
        self.assertEqual(data[1]["cmajflt_delta"], 1)  # 3 - 2

    def test_ciclo_muere_proceso_entre_status_y_stat(self):
        """Si un PID muere entre la lectura de status y stat, no aparece en data."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1])
        analyzer.procfs.status_por_pid.update(
            {1: mock_stat(minflt=10, cminflt=20, majflt=5, cmajflt=2)}
        )
        
        analyzer.procfs.dead_entre_lecturas[1] = ProcessLookupError()
        analyzer._ciclo()
        data = analyzer.snapshot["memory"]["data"]
        self.assertNotIn(1, data)

if __name__ == "__main__":
    unittest.main()
