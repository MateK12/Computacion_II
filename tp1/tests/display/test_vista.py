import unittest
from src.display.vista import view_memory, view_scheduling, view_signals, view_summary, view_threads


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
            "memory": {"ts": 3.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 3.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, 12, 3, "test"]])

    def test_view_memory_retorna_bien_dimension_con_comando_faltante(self):
        # Si la dimensión memory existe pero summary no, la vista devuelve None en la columna Comando
        data = {
            "memory": {"ts": 2.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 2.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, 12, 3, None]])

    def test_view_memory_retorna_ts_de_su_dimension(self):
        # La vista memory devuelve el ts de la dimensión memory, no de summary
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "memory": {"ts": 4.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 4.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, 12, 3, "test"]])

    def test_view_memory_ordena_pids_e_info(self):
        # La vista ordena los PIDs y la info correspondiente
        data = {
            "summary": {"ts": 5.0, "data": {2: {"state": "S", "threads": 2, "name": "test2"}, 1: {"state": "R", "threads": 1, "name": "test1"}}},
            "memory": {"ts": 5.0, "data": {2: {"vm_size": 4096, "vm_rss": 2048, "vm_hwm": 1024, "vm_data": 512, "vm_stack": 256, "vm_exe": 128, "vm_lib": 64, "vm_swap": 32, "minflt_delta": 20, "majflt_delta": 5}, 1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 5.0)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, 12, 3, "test1"], [2, 4096, 2048, 1024, 512, 256, 128, 64, 32, 20, 5, "test2"]])

    def test_view_memory_filtra_procesos_con_datos_faltantes(self):
        # La vista filtra los procesos que tienen None en alguna de las columnas de memoria
        data = {
            "summary": {"ts": 6.0, "data": {1: {"state": "R", "threads": 1, "name": "test1"}, 2: {"state": "S", "threads": 2, "name": "test2"}}},
            "memory": {"ts": 6.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}, 2: {"vm_size": None, "vm_rss": None, "vm_hwm": None, "vm_data": None, "vm_stack": None, "vm_exe": None, "vm_lib": None, "vm_swap": None, "minflt_delta": 1, "majflt_delta": 0}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 6.0)
        # el PID 2 (kthread) se filtra por sus vm_* None aunque tenga deltas de faults
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, 12, 3, "test1"]])

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
            "memory": {"ts": 1.0, "data": {1: {"vm_size": None, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [])

    def test_view_memory_no_filtra_deltas_de_faults_none(self):
        # Los *_delta en None (primer ciclo del monitor, o PID reusado) son transitorios
        
        data = {
            "summary": {"ts": 7.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "memory": {"ts": 7.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": None, "majflt_delta": None}}},
        }
        table = view_memory(data)
        self.assertEqual(table.rows, [[1, 2048, 1024, 512, 256, 128, 64, 32, 16, None, None, "test"]])

    #VIEW SCHEDULING

    def test_view_scheduling_retorna_bien_dimension_ausente(self):
        # Si la dimensión scheduling no existe, la vista devuelve ts=None y rows=[]
        data = {}
        table = view_scheduling(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_scheduling_retorna_bien_dimension_con_datos(self):
        # Fila completa: estáticos + deltas del intervalo + comando cruzado desde summary
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "scheduling": {"ts": 1.0, "data": {1: {"policy": "SCHED_OTHER", "nice": 0, "priority": 20, "rt_priority": 0, "affinity": "0-7", "timeslices": 123, "cpu_usage": 12.5, "runqueue_wait_pct": 0.3}}},
        }
        table = view_scheduling(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [[1, "SCHED_OTHER", 0, 20, 0, "0-7", 123, 12.5, 0.3, "test"]])

    def test_view_scheduling_no_filtra_none_transitorios(self):
        # cpu_usage/runqueue_wait_pct en None (primer ciclo, sin delta) NO sacan la fila:
        # es un None transitorio, distinto del None estructural de los kthreads en memoria
        data = {
            "summary": {"ts": 2.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "scheduling": {"ts": 2.0, "data": {1: {"policy": "SCHED_OTHER", "nice": 0, "priority": 20, "rt_priority": 0, "affinity": "0", "timeslices": 1, "cpu_usage": None, "runqueue_wait_pct": None}}},
        }
        table = view_scheduling(data)
        self.assertEqual(table.rows, [[1, "SCHED_OTHER", 0, 20, 0, "0", 1, None, None, "test"]])

    def test_view_scheduling_retorna_bien_dimension_con_comando_faltante(self):
        # PID en scheduling pero no en summary -> None en la columna Comando
        data = {
            "scheduling": {"ts": 3.0, "data": {1: {"policy": "SCHED_FIFO", "nice": 0, "priority": -100, "rt_priority": 99, "affinity": "0", "timeslices": 5, "cpu_usage": 1.0, "runqueue_wait_pct": 0.0}}},
        }
        table = view_scheduling(data)
        self.assertEqual(table.rows, [[1, "SCHED_FIFO", 0, -100, 99, "0", 5, 1.0, 0.0, None]])

    def test_view_scheduling_ordena_pids(self):
        # La vista ordena los PIDs para que el orden sea estable entre frames
        entry = {"policy": "SCHED_OTHER", "nice": 0, "priority": 20, "rt_priority": 0, "affinity": "0", "timeslices": 1, "cpu_usage": 1.0, "runqueue_wait_pct": 0.0}
        data = {
            "scheduling": {"ts": 4.0, "data": {2: dict(entry), 1: dict(entry)}},
        }
        table = view_scheduling(data)
        self.assertEqual([row[0] for row in table.rows], [1, 2])

    #VIEW SIGNALS

    def test_view_signals_retorna_bien_dimension_ausente(self):
        # Si la dimensión signals no existe, la vista devuelve ts=None y rows=[]
        data = {}
        table = view_signals(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_signals_cuenta_y_formatea_pendientes(self):
        # blocked/ignored/caught como conteo; pending como conteo + cuáles
        # (2=INT, 15=TERM); pending vacía -> "0"
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "S", "threads": 1, "name": "test"}}},
            "signals": {"ts": 1.0, "data": {1: {"blocked": [10, 12], "ignored": [1, 2, 15], "caught": [11], "pending_thread": [], "pending_shared": [2, 15]}}},
        }
        table = view_signals(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [[1, 2, 3, 1, "0", "2: INT,TERM", "test"]])

    def test_view_signals_senal_sin_nombre_queda_como_numero(self):
        # Las señales de tiempo real (34..63) no tienen nombre en signal.Signals:
        # se muestran como número en vez de romper
        data = {
            "signals": {"ts": 2.0, "data": {1: {"blocked": [], "ignored": [], "caught": [], "pending_thread": [42], "pending_shared": []}}},
        }
        table = view_signals(data)
        self.assertEqual(table.rows, [[1, 0, 0, 0, "1: 42", "0", None]])

    def test_view_signals_ordena_pids(self):
        # La vista ordena los PIDs para que el orden sea estable entre frames
        entry = {"blocked": [], "ignored": [], "caught": [], "pending_thread": [], "pending_shared": []}
        data = {
            "signals": {"ts": 3.0, "data": {2: dict(entry), 1: dict(entry)}},
        }
        table = view_signals(data)
        self.assertEqual([row[0] for row in table.rows], [1, 2])

    #VIEW THREADS
    def test_view_threads_retorna_bien_dimension_ausente(self):
        # Si la dimensión threads no existe, la vista devuelve ts=None y rows=[]
        data = {}
        table = view_threads(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_threads_retorna_bien_dimension_con_datos(self):
        # Si la dimensión threads existe, la vista devuelve los datos correspondientes
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "threads": {"ts": 1.0, "data": {1: {100: {"name": "thread1", "state": "S", "cpu": 12.5, "ctxt": {"vol": 10, "nonvol": 5}}}}},
        }
        table = view_threads(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [[1, 100, "thread1", "S", 12.5, 10, 5, "test"]])

    def test_view_threads_retorna_bien_dimension_con_comando_faltante(self):
        # PID en threads pero no en summary -> None en la columna Comando
        data = {
            "threads": {"ts": 2.0, "data": {1: {100: {"name": "thread1", "state": "S", "cpu": 12.5, "ctxt": {"vol": 10, "nonvol": 5}}}}},
        }
        table = view_threads(data)
        self.assertEqual(table.rows, [[1, 100, "thread1", "S", 12.5, 10, 5, None]])

    def test_view_threads_ordena_pids_y_tids(self):
        # La vista ordena los PIDs y TIDs para que el orden sea estable entre frames
        entry = {"name": "thread", "state": "S", "cpu": 12.5, "ctxt": {"vol": 10, "nonvol": 5}}
        data = {
            "threads": {"ts": 3.0, "data": {2: {200: dict(entry), 100: dict(entry)}, 1: {300: dict(entry), 400: dict(entry)}}},
        }
        table = view_threads(data)
        self.assertEqual([row[0] for row in table.rows], [1, 1, 2, 2])
        self.assertEqual([row[1] for row in table.rows], [300, 400, 100, 200])

    


if __name__ == "__main__":
    unittest.main()
