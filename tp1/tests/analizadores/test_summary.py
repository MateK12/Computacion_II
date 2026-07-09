import unittest

from src.analizadores.summary import AnalyzerSummary


class MockProcFS:
    """Doble de prueba: devuelve un status fijo por PID que controlamos desde el test.
    Para simular un proceso que muere a mitad de lectura, registrá su PID en `dead`
    y read_status lanzará FileNotFoundError (o ProcessLookupError) para ese PID."""

    def __init__(self, status_por_pid, dead=None):
        self.status_por_pid = status_por_pid          # {pid: {status crudo}}
        self.dead = dead or {}                         # {pid: ExcepciónAClasea}

    def read_status(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.status_por_pid[pid]


def status_de_ejemplo(**overrides):
    """Status mínimo válido para el Resumen; pisá campos puntuales con overrides."""
    base = {
        "Name": "bash",
        "State": "S",
        "PPid": "1000",
        "Uid": "1000\t1000\t1000\t1000",
        "Gid": "1000\t1000\t1000\t1000",
        "Threads": "5",
    }
    base.update(overrides)
    return base


class TestAnalyzerSummary(unittest.TestCase):

    def test_extract_mapea_los_campos_del_status(self):
        """_extract devuelve name/state/ppid/uid/gid/threads desde el status crudo."""
        analyzer = AnalyzerSummary(MockProcFS({}),[],[],1)
        status = status_de_ejemplo()
        expected = {
            "name": "bash",
            "state": "S",
            "ppid": 1000,
            "uid": 1000,
            "gid": 1000,
            "threads": 5,
        }
        self.assertEqual(analyzer._extract(status), expected)

    def test_extract_estado_es_solo_el_primer_caracter(self):
        """'S (sleeping)' -> 'S' (no la descripción completa)."""
        analyzer = AnalyzerSummary(MockProcFS({}),[],[],1)
        status = status_de_ejemplo(State="S (sleeping)")
        expected = {
            "name": "bash",
            "state": "S",
            "ppid": 1000,
            "uid": 1000,
            "gid": 1000,
            "threads": 5,
        }
        self.assertEqual(analyzer._extract(status), expected)

    def test_extract_convierte_ppid_y_threads_a_int(self):
        """ppid y threads salen como int, no como string."""
        analyzer = AnalyzerSummary(MockProcFS({}),[],[],1)
        status = status_de_ejemplo(PPid="1000", Threads="5")
        expected = {
            "name": "bash",
            "state": "S",
            "ppid": 1000,
            "uid": 1000,
            "gid": 1000,
            "threads": 5,
        }
        self.assertEqual(analyzer._extract(status), expected)

    def test_ciclo_publica_la_clave_summary_con_ts_y_data(self):
        """Tras _ciclo(), snapshot['summary'] tiene la forma {'ts': ..., 'data': {...}}."""
        snapshot = {}
        analyzer = AnalyzerSummary(MockProcFS({}),[],snapshot,1)
        analyzer._ciclo()
        self.assertIn("summary", snapshot)
        self.assertIn("ts", snapshot["summary"])
        self.assertIn("data", snapshot["summary"])

    def test_ciclo_indexa_la_data_por_pid(self):
        """snapshot['summary']['data'] tiene una entrada por cada PID vivo."""
        snapshot = {}
        analyzer = AnalyzerSummary(MockProcFS({1: status_de_ejemplo(), 2: status_de_ejemplo()}),[1,2],snapshot,1)
        analyzer._ciclo()

        self.assertIn(1, snapshot["summary"]["data"])
        self.assertIn(2, snapshot["summary"]["data"])

    def test_ciclo_saltea_proceso_muerto_filenotfound(self):
        """Un PID que lanza FileNotFoundError no aparece en data (no rompe el ciclo)."""
        snapshot = {}
        analyzer = AnalyzerSummary(MockProcFS({}, {1: FileNotFoundError}),[1],snapshot,1)
        analyzer._ciclo()
        # el ciclo no se rompe: publica summary, pero el PID muerto no entra en data
        self.assertNotIn(1, snapshot["summary"]["data"])

    def test_ciclo_saltea_proceso_muerto_processlookup(self):
        """Idem con ProcessLookupError."""
        snapshot = {}
        analyzer = AnalyzerSummary(MockProcFS({}, {1: ProcessLookupError}), [1], snapshot, 1)
        analyzer._ciclo()
        self.assertNotIn(1, snapshot["summary"]["data"])

    def test_ciclo_reemplaza_no_acumula_entre_pasos(self):
        """Si entre dos _ciclo() cambian los PIDs vivos, data refleja solo los actuales."""
        snapshot = {}
        analyzer = AnalyzerSummary(MockProcFS({1: status_de_ejemplo(), 2: status_de_ejemplo()}),[1,2],snapshot,1)
        analyzer._ciclo()
        self.assertIn(1, snapshot["summary"]["data"])
        self.assertIn(2, snapshot["summary"]["data"])

        analyzer.procfs.status_por_pid[3] = status_de_ejemplo()
        analyzer.shared_pids[:] = [2, 3]  
        analyzer._ciclo()

        self.assertNotIn(1, snapshot["summary"]["data"])
        self.assertIn(2, snapshot["summary"]["data"])
        self.assertIn(3, snapshot["summary"]["data"])

if __name__ == "__main__":
    unittest.main()
