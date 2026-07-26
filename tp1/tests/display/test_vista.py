import unittest
from src.display.vista import view_memory, view_summary


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
    #VIEW MEMORY
    
    def test_view_memory_retorna_bien_dimension_ausente(self):
        # Si la dimensión memory no existe, la vista devuelve ts=None y rows=[]
        data = {}
        table = view_memory(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_memory_retorna_bien_dimension_con_datos(self):
        # Si la dimensión memory existe, la vista devuelve los datos correspondientes
        data = {
            "summary": {"ts": 3.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "memory": {"ts": 3.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 3.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, "test"]])

    def test_view_memory_retorna_bien_dimension_con_comando_faltante(self):
        # Si la dimensión memory existe pero summary no, la vista devuelve None en la columna Comando
        data = {
            "memory": {"ts": 2.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 2.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, None]])

    def test_view_memory_retorna_ts_de_su_dimension(self):
        # La vista memory devuelve el ts de la dimensión memory, no de summary
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "memory": {"ts": 4.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 4.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, "test"]])

    def test_view_memory_ordena_pids_e_info(self):
        # La vista ordena los PIDs y la info correspondiente
        data = {
            "summary": {"ts": 5.0, "data": {2: {"state": "S", "threads": 2, "name": "test2"}, 1: {"state": "R", "threads": 1, "name": "test1"}}},
            "memory": {"ts": 5.0, "data": {2: {"vm_size": 4096, "vm_rss": 2048, "vm_hwm": 1024, "vm_data": 512, "vm_stack": 256, "vm_exe": 128, "vm_lib": 64, "vm_swap": 32}, 1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 5.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, "test1"], [2, 4096, 2048, 1024, 512, 256, 128, 64, 32, "test2"]])

    def test_view_memory_filtra_procesos_con_datos_faltantes(self):
        # La vista filtra los procesos que tienen None en alguna de las columnas de memoria
        data = {
            "summary": {"ts": 6.0, "data": {1: {"state": "R", "threads": 1, "name": "test1"}, 2: {"state": "S", "threads": 2, "name": "test2"}}},
            "memory": {"ts": 6.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16}, 2: {"vm_size": None, "vm_rss": None, "vm_hwm": None, "vm_data": None, "vm_stack": None, "vm_exe": None, "vm_lib": None, "vm_swap": None}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 6.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, "test1"]])

    def test_view_memory_no_retorna_si_falta_memory(self):
        # Si la dimensión memory no existe, la vista devuelve ts=None y rows=[]
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_memory_no_retorna_si_falta_por_lo_menos_un_dato_de_columnas(self):
        # Si la dimensión memory existe pero le falta por lo menos un dato de las columnas de memoria, la vista filtra ese proceso
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "memory": {"ts": 1.0, "data": {1: {"vm_size": None, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [])
        
if __name__ == "__main__":
    unittest.main()
