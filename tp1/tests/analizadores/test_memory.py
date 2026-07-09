import unittest

from src.analizadores.memory import AnalyzerMemory


class MockProcFS:
    """Doble de prueba: devuelve un status fijo por PID. Para simular un proceso
    que muere a mitad de lectura, registrá su PID en `dead` con la excepción a lanzar."""

    def __init__(self, status_por_pid, dead=None):
        self.status_por_pid = status_por_pid
        self.dead = dead or {}

    def read_status(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
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
            {1: mock_status(VmRSS="100 kB"), 2: mock_status(VmRSS="200 kB")}
        )
        analyzer._ciclo()
        data = analyzer.snapshot["memory"]["data"]
        self.assertIn(1, data)
        self.assertIn(2, data)
        self.assertEqual(data[1]["vm_rss"], 100)
        self.assertEqual(data[2]["vm_rss"], 200)

    def test_ciclo_saltea_proceso_muerto(self):
        """Un PID que lanza FileNotFoundError/ProcessLookupError no aparece en data."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1, 2])
        analyzer.procfs.status_por_pid.update(
            {1: mock_status(VmRSS="100 kB"), 2: mock_status(VmRSS="200 kB")}
        )
        analyzer.procfs.dead[2] = FileNotFoundError()
        analyzer._ciclo()
        data = analyzer.snapshot["memory"]["data"]
        self.assertIn(1, data)
        self.assertNotIn(2, data)


if __name__ == "__main__":
    unittest.main()
