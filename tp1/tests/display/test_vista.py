import unittest
from src.display.vista import view_fds, view_memory, view_scheduling, view_signals, view_summary, view_threads, view_sistema


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
        self.assertEqual(table.rows, [[1, "R", 50.0, "1.0 MB", 1, "test"]])

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
        self.assertEqual(table.rows, [[1, "R", 50.0, "1.0 MB", 1, "test1"], [2, "S", 30.0, "2.0 MB", 2, "test2"]])
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
        self.assertEqual(table.rows, [[1, "2.0 MB", "1.0 MB", "512 KB", "256 KB", "128 KB", "64 KB", "32 KB", "16 KB", 12, 3, "test"]])

    def test_view_memory_retorna_bien_dimension_con_comando_faltante(self):
        # Si la dimensión memory existe pero summary no, la vista devuelve None en la columna Comando
        data = {
            "memory": {"ts": 2.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 2.0)
        self.assertEqual(table.rows, [[1, "2.0 MB", "1.0 MB", "512 KB", "256 KB", "128 KB", "64 KB", "32 KB", "16 KB", 12, 3, None]])

    def test_view_memory_retorna_ts_de_su_dimension(self):
        # La vista memory devuelve el ts de la dimensión memory, no de summary
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "memory": {"ts": 4.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 4.0)
        self.assertEqual(table.rows, [[1, "2.0 MB", "1.0 MB", "512 KB", "256 KB", "128 KB", "64 KB", "32 KB", "16 KB", 12, 3, "test"]])

    def test_view_memory_ordena_pids_e_info(self):
        # La vista ordena los PIDs y la info correspondiente
        data = {
            "summary": {"ts": 5.0, "data": {2: {"state": "S", "threads": 2, "name": "test2"}, 1: {"state": "R", "threads": 1, "name": "test1"}}},
            "memory": {"ts": 5.0, "data": {2: {"vm_size": 4096, "vm_rss": 2048, "vm_hwm": 1024, "vm_data": 512, "vm_stack": 256, "vm_exe": 128, "vm_lib": 64, "vm_swap": 32, "minflt_delta": 20, "majflt_delta": 5}, 1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 5.0)
        self.assertEqual(table.rows, [[1, "2.0 MB", "1.0 MB", "512 KB", "256 KB", "128 KB", "64 KB", "32 KB", "16 KB", 12, 3, "test1"], [2, "4.0 MB", "2.0 MB", "1.0 MB", "512 KB", "256 KB", "128 KB", "64 KB", "32 KB", 20, 5, "test2"]])

    def test_view_memory_filtra_procesos_con_datos_faltantes(self):
        # La vista filtra los procesos que tienen None en alguna de las columnas de memoria
        data = {
            "summary": {"ts": 6.0, "data": {1: {"state": "R", "threads": 1, "name": "test1"}, 2: {"state": "S", "threads": 2, "name": "test2"}}},
            "memory": {"ts": 6.0, "data": {1: {"vm_size": 2048, "vm_rss": 1024, "vm_hwm": 512, "vm_data": 256, "vm_stack": 128, "vm_exe": 64, "vm_lib": 32, "vm_swap": 16, "minflt_delta": 12, "majflt_delta": 3}, 2: {"vm_size": None, "vm_rss": None, "vm_hwm": None, "vm_data": None, "vm_stack": None, "vm_exe": None, "vm_lib": None, "vm_swap": None, "minflt_delta": 1, "majflt_delta": 0}}},
        }
        table = view_memory(data)
        self.assertEqual(table.ts, 6.0)
        # el PID 2 (kthread) se filtra por sus vm_* None aunque tenga deltas de faults
        self.assertEqual(table.rows, [[1, "2.0 MB", "1.0 MB", "512 KB", "256 KB", "128 KB", "64 KB", "32 KB", "16 KB", 12, 3, "test1"]])

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
        self.assertEqual(table.rows, [[1, "2.0 MB", "1.0 MB", "512 KB", "256 KB", "128 KB", "64 KB", "32 KB", "16 KB", None, None, "test"]])

    #VIEW FDS

    def test_view_fds_retorna_bien_dimension_ausente(self):
        # Si la dimensión fds no existe, la vista devuelve ts=None y rows=[]
        data = {}
        table = view_fds(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_fds_cuenta_por_tipo_y_muestra_destinos(self):
        # Conteos por tipo + total, y la muestra son los 2 FDs más bajos con destino
        data = {
            "summary": {"ts": 1.0, "data": {1: {"state": "R", "threads": 1, "name": "test"}}},
            "fds": {"ts": 1.0, "data": {1: {
                0: {"dest": "/dev/pts/1", "type": "file"},
                1: {"dest": "/dev/pts/1", "type": "file"},
                3: {"dest": "socket:[123]", "type": "socket"},
                4: {"dest": "pipe:[456]", "type": "pipe"},
                5: {"dest": "anon_inode:[eventfd]", "type": "anon_inode"},
            }}},
        }
        table = view_fds(data)
        self.assertEqual(table.ts, 1.0)
        self.assertEqual(table.rows, [[1, 5, 2, 1, 1, 1, 0, "0:/dev/pts/1, 1:/dev/pts/1", "test"]])

    def test_view_fds_tipo_desconocido_cuenta_como_otros(self):
        # Un type que no está en las columnas conocidas suma al Total y a Otros
        data = {
            "fds": {"ts": 2.0, "data": {1: {
                0: {"dest": "mnt:[4026531841]", "type": "unknown"},
            }}},
        }
        table = view_fds(data)
        self.assertEqual(table.rows, [[1, 1, 0, 0, 0, 0, 1, "0:mnt:[4026531841]", None]])

    def test_view_fds_muestra_ordena_numericamente(self):
        # La muestra toma los FDs más bajos por valor numérico (10 > 2, no "10" < "2")
        data = {
            "fds": {"ts": 3.0, "data": {1: {
                10: {"dest": "socket:[123]", "type": "socket"},
                2: {"dest": "/var/log/app.log", "type": "file"},
                7: {"dest": "pipe:[456]", "type": "pipe"},
            }}},
        }
        table = view_fds(data)
        self.assertEqual(table.rows[0][7], "2:/var/log/app.log, 7:pipe:[456]")

    def test_view_fds_proceso_sin_fds(self):
        # Un proceso con dict de FDs vacío (kthread) tiene fila con todo en 0 y muestra vacía
        data = {
            "summary": {"ts": 4.0, "data": {1: {"state": "S", "threads": 1, "name": "kworker"}}},
            "fds": {"ts": 4.0, "data": {1: {}}},
        }
        table = view_fds(data)
        self.assertEqual(table.rows, [[1, 0, 0, 0, 0, 0, 0, "", "kworker"]])

    def test_view_fds_retorna_bien_dimension_con_comando_faltante(self):
        # PID en fds pero no en summary -> None en la columna Comando
        data = {
            "fds": {"ts": 5.0, "data": {1: {0: {"dest": "/dev/null", "type": "file"}}}},
        }
        table = view_fds(data)
        self.assertEqual(table.rows, [[1, 1, 1, 0, 0, 0, 0, "0:/dev/null", None]])

    def test_view_fds_ordena_pids(self):
        # La vista ordena los PIDs para que el orden sea estable entre frames
        entry = {0: {"dest": "/dev/null", "type": "file"}}
        data = {
            "fds": {"ts": 6.0, "data": {2: dict(entry), 1: dict(entry)}},
        }
        table = view_fds(data)
        self.assertEqual([row[0] for row in table.rows], [1, 2])

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

    


    # VIEW SISTEMA

    def test_view_sistema_retorna_bien_dimension_ausente(self):
        # Si la dimensión sistema no existe, la vista devuelve ts=None y rows=[]
        data = {}
        table = view_sistema(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_sistema_retorna_bien_dimension_vacia(self):
        # Si la dimensión sistema existe pero está vacía, la vista devuelve ts=None y rows=[]
        data = {
            "sistema": {"ts": None, "data": {}}
        }
        table = view_sistema(data)
        self.assertEqual(table.ts, None)
        self.assertEqual(table.rows, [])

    def test_view_sistema_retorna_bien_dimension_con_datos(self):
        # Si la dimensión sistema existe con datos, la vista devuelve las métricas globales
        data = {
            "sistema": {
                "ts": 1.0,
                "data": {
                    "uptime": 86400,  # 1 día
                    "boot_time": 1722192600,
                    "load_1m": 0.5,
                    "load_5m": 0.4,
                    "load_15m": 0.3,
                    "mem_total_kb": 8 * 1024 * 1024,
                    "mem_free_kb": 3 * 1024 * 1024,
                    "mem_cached_kb": 2 * 1024 * 1024,
                    "swap_used_kb": 0,
                    "swap_total_kb": 4 * 1024 * 1024,
                    "cpu_user_pct": 20.0,
                    "cpu_system_pct": 10.0,
                    "cpu_idle_pct": 70.0,
                    "cpu_iowait_pct": 0.0,
                    "procs_total": 42,
                    "procs_by_state": {"R": 2, "S": 38, "D": 1, "T": 0, "Z": 1},
                    "threads_total": 105,
                    "ctxt_switches_per_sec": 1234.5,
                    "forks_per_sec": 12.3,
                    "top_cpu": [
                        {"pid": 1234, "cpu_pct": 25.0},
                        {"pid": 1235, "cpu_pct": 18.0},
                        {"pid": 1236, "cpu_pct": 14.0},
                    ],
                    "top_mem": [
                        {"pid": 1234, "rss_kb": 262144},
                        {"pid": 1235, "rss_kb": 204800},
                        {"pid": 1236, "rss_kb": 153600},
                    ],
                }
            }
        }
        table = view_sistema(data)
        self.assertEqual(table.ts, 1.0)
        # Debe tener 9 filas: Uptime, Load, Memoria, CPU, Procesos, Context Sw., Forks, Top CPU, Top Memoria
        self.assertEqual(len(table.rows), 9)
        # Verificar que la primer fila es Uptime
        self.assertEqual(table.rows[0][0], "Uptime")
        # Verificar que la segunda fila es Load
        self.assertEqual(table.rows[1][0], "Load")
        # Verificar que la tercer fila es Memoria
        self.assertEqual(table.rows[2][0], "Memoria")
        # Verificar que la cuarta fila es CPU
        self.assertEqual(table.rows[3][0], "CPU")
        # Verificar que la quinta fila es Procesos
        self.assertEqual(table.rows[4][0], "Procesos")
        # Verificar que la sexta fila es Context Sw.
        self.assertEqual(table.rows[5][0], "Context Sw.")
        # Verificar que la séptima fila es Forks
        self.assertEqual(table.rows[6][0], "Forks")
        # Verificar que la octava fila es Top CPU
        self.assertEqual(table.rows[7][0], "Top CPU")
        # Verificar que la novena fila es Top Memoria
        self.assertEqual(table.rows[8][0], "Top Memoria")

    def test_view_sistema_titulo(self):
        # La vista debe tener el título "Sistema"
        data = {
            "sistema": {
                "ts": 1.0,
                "data": {
                    "uptime": 100,
                    "boot_time": None,
                    "load_1m": 0.5,
                    "load_5m": 0.4,
                    "load_15m": 0.3,
                    "mem_total_kb": 1000,
                    "mem_free_kb": 500,
                    "mem_cached_kb": 300,
                    "swap_used_kb": 0,
                    "swap_total_kb": 500,
                }
            }
        }
        table = view_sistema(data)
        self.assertEqual(table.title, "Sistema")

    def test_view_sistema_columnas(self):
        # La vista debe tener 5 columnas: Métrica, Valor 1, Valor 2, Valor 3, Valor 4
        data = {
            "sistema": {
                "ts": 1.0,
                "data": {
                    "uptime": 100,
                    "boot_time": None,
                    "load_1m": 0.5,
                    "load_5m": 0.4,
                    "load_15m": 0.3,
                    "mem_total_kb": 1000,
                    "mem_free_kb": 500,
                    "mem_cached_kb": 300,
                    "swap_used_kb": 0,
                    "swap_total_kb": 500,
                }
            }
        }
        table = view_sistema(data)
        self.assertEqual(table.columns, ["Métrica", "Valor 1", "Valor 2", "Valor 3", "Valor 4"])


if __name__ == "__main__":
    unittest.main()
