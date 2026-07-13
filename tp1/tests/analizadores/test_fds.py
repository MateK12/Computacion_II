import unittest

from src.analizadores.fds import AnalyzerFileDescriptor


class MockProcFS:
    """Doble de prueba: devuelve los FDs crudos {fd: dest} por PID. Para simular un
    proceso que muere a mitad de lectura, registrá su PID en `dead` con la excepción
    a lanzar."""

    def __init__(self, fds_por_pid, dead=None):
        self.fds_por_pid = fds_por_pid
        self.dead = dead or {}

    def read_fd_links(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.fds_por_pid[pid]


def mock_fds(**overrides):
    """FDs de un proceso normal: los 3 estándar (stdin/out/err) más algunos abiertos.
    Los destinos son strings crudos tal como los devolvería os.readlink."""
    base = {
        0: "/dev/pts/3",
        1: "/dev/pts/3",
        2: "/dev/pts/3",
        3: "socket:[12345]",
        4: "pipe:[67890]",
        5: "/home/mateo/data.txt",
        6: "anon_inode:[eventpoll]",
    }
    base.update(overrides)
    return base


class TestFDs(unittest.TestCase):

    def _analyzer(self, fds_por_pid=None, dead=None):
        return AnalyzerFileDescriptor(
            MockProcFS(fds_por_pid or {}, dead), [], {}, 1
        )

    def test_lists_open_fds(self):
        """Tras _ciclo, data[pid] tiene una entrada por cada FD que devolvió procfs."""
        analyzer = self._analyzer({1: mock_fds()})
        analyzer.shared_pids.append(1)
        analyzer._ciclo()
        data = analyzer.snapshot["fds"]["data"]
        self.assertEqual(set(data[1].keys()), set(mock_fds().keys()))

    def test_inferrs_fd_type_correctly(self):
        """_parse_fd_type infiere el tipo por el prefijo del destino crudo."""
        parse = self._analyzer()._parse_fd_type
        self.assertEqual(parse("socket:[12345]"), "socket")
        self.assertEqual(parse("pipe:[67890]"), "pipe")
        self.assertEqual(parse("anon_inode:[eventpoll]"), "anon_inode")
        self.assertEqual(parse("/dev/null"), "file")
        self.assertEqual(parse("/home/mateo/data.txt"), "file")
        self.assertEqual(parse("net:[4026531840]"), "unknown")

    def test_shows_symlink_destination(self):
        """data[pid][fd]['dest'] es exactamente el string crudo del symlink."""
        analyzer = self._analyzer({1: {3: "/dev/null"}})
        analyzer.shared_pids.append(1)
        analyzer._ciclo()
        entry = analyzer.snapshot["fds"]["data"][1][3]
        self.assertEqual(entry["dest"], "/dev/null")
        self.assertEqual(entry["type"], "file")

    def test_ciclo_publica_la_clave_fds_con_ts_y_data(self):
        """Tras _ciclo(), snapshot['fds'] tiene la forma {'ts': ..., 'data': {...}}."""
        analyzer = self._analyzer()
        analyzer._ciclo()
        self.assertIn("fds", analyzer.snapshot)
        self.assertIn("ts", analyzer.snapshot["fds"])
        self.assertIn("data", analyzer.snapshot["fds"])

    def test_ciclo_saltea_proceso_muerto(self):
        """Un PID cuyo read_fd_links lanza FileNotFoundError no aparece en data."""
        analyzer = self._analyzer(
            fds_por_pid={1: mock_fds(), 2: mock_fds()},
            dead={2: FileNotFoundError()},
        )
        analyzer.shared_pids.extend([1, 2])
        analyzer._ciclo()
        data = analyzer.snapshot["fds"]["data"]
        self.assertIn(1, data)
        self.assertNotIn(2, data)


if __name__ == "__main__":
    unittest.main()
