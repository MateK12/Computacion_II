import unittest
from src.collector import Collector


class MockProcFS:
    """Doble de prueba: devuelve una lista de PIDs fija que controlamos desde el test.
    Reemplaza el contacto real con /proc — el Collector no distingue uno del otro
    (duck typing): solo necesita un objeto con .list_pids()."""

    def __init__(self, pids):
        self.pids = pids

    def list_pids(self):
        return iter(self.pids)


class TestCollector(unittest.TestCase):
    def test_ciclo_publica_pids(self):
        shared = []
        col = Collector(MockProcFS([1, 2, 3]), shared, sleep_interval=1)

        col._ciclo()

        self.assertEqual(shared, [1, 2, 3])

    def test_ciclo_reemplaza_no_acumula(self):
        shared = []
        procfs = MockProcFS([1, 2, 3])
        col = Collector(procfs, shared, sleep_interval=1)

        col._ciclo()
        procfs.pids = [4, 5]   # cambió el estado del sistema entre ciclos
        col._ciclo()

        self.assertEqual(shared, [4, 5])

    def test_ciclo_muta_el_mismo_objeto(self):
        # Testear que _ciclo() mute la misma referencia a memoria que utilizan los otros procesos
        shared = []
        col = Collector(MockProcFS([7, 8]), shared, sleep_interval=1)

        col._ciclo()

        self.assertIs(col.shared_pids, shared) #


if __name__ == "__main__":
    unittest.main()
