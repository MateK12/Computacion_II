import unittest
from src.display.vista import view_summary


class TestVista(unittest.TestCase):
    def test_view_summary_retorna_bien_dimension_ausente(self):
        # Si la dimensión summary no existe, la vista devuelve ts=None y rows=[]
        data = {}
        table = view_summary(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_summary_retorna_bien_dimension_con_datos(self):
        # Si la dimensión summary existe, la vista devuelve los datos correspondientes
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "cpu": {"ts": 1.0, "data": {1: 50.0}},
            "memory": {"ts": 1.0, "data": {1: {"vm_rss": 1024}}},
        }
        table = view_summary(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [[1, "R", 50.0, 1024, 1, "test"]])

    def test_view_summary_retorna_bien_dimension_con_datos_faltantes(self):
        # Si la dimensión summary existe pero cpu y memory no, la vista devuelve None en esas celdas
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
        }
        table = view_summary(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [[1, "R", None, None, 1, "test"]])

    def test_view_summary_retorna_pid_faltante(self):
        # Si la dimensión summary tiene un PID que no está en cpu ni memory, la vista devuelve None en esas celdas
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "cpu": {"ts": 1.0, "data": {}},
            "memory": {"ts": 1.0, "data": {}},
        }
        table = view_summary(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [[1, "R", None, None, 1, "test"]])

    def test_view_summary_ordena_pids_e_info(self):
        # La vista ordena los PIDs y la info correspondiente
        data = {
            "summary": {"ts": 2.0, "data": {2: {"state": "S", "threads": 2, "name": "test2"}, 1: {"state": "R", "threads": 1, "name": "test1"}}},
            "cpu": {"ts": 2.0, "data": {2: 30.0, 1: 50.0}},
            "memory": {"ts": 2.0, "data": {2: {"vm_rss": 2048}, 1: {"vm_rss": 1024}}},
        }
        table = view_summary(data)
        self.assertEqual(table.ts, 2.0)
        self.assertEqual(table.rows, [[1, "R", 50.0, 1024, 1, "test1"], [2, "S", 30.0, 2048, 2, "test2"]])
    def test_view_summary_no_retorna_si_falta_summary(self):
        # Si la dimensión summary no existe, la vista devuelve ts=None y rows=[]
        data = {
            "cpu": {"ts": 1.0, "data": {1: 50.0}},
            "memory": {"ts": 1.0, "data": {1: {"vm_rss": 1024}}},
        }
        table = view_summary(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_summary_no_retorna_si_summary_vacio(self):
        # Si la dimensión summary no existe, la vista devuelve ts=None y rows=[]
        data = {
            "cpu": {"ts": 3.0, "data": {1: 50.0}},
            "memory": {"ts": 3.0, "data": {1: {"vm_rss": 1024}}},
            "summary": {"ts": None, "data": {}}
        }
        table = view_summary(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])



if __name__ == "__main__":
    unittest.main()
