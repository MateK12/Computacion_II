import unittest
from unittest.mock import patch

from src.analizadores.sistema import AnalyzerSystem


class MockProcFS:
    """Doble de prueba. Dobla las cuatro lecturas globales más el read_stat por
    PID (que el analizador usa solo para contar estados).

    `dead` marca PIDs cuya lectura lanza excepción (proceso que se murió).
    `globals_raise` simula /proc inaccesible en las lecturas globales.
    """

    def __init__(self, stat_global=None, meminfo=None, loadavg=None, uptime=None,
                 stats=None, dead=None, globals_raise=None):
        self.stat_global = stat_global if stat_global is not None else mock_stat_global()
        self.meminfo = meminfo if meminfo is not None else mock_meminfo()
        self.loadavg = loadavg if loadavg is not None else mock_loadavg()
        self.uptime = uptime if uptime is not None else mock_uptime()
        self.stats = stats or {}
        self.dead = dead or {}
        self.globals_raise = globals_raise

    def read_stat_global(self):
        if self.globals_raise:
            raise self.globals_raise
        return self.stat_global

    def read_meminfo(self):
        return self.meminfo

    def read_loadavg(self):
        return self.loadavg

    def read_uptime(self):
        return self.uptime

    def read_stat(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.stats[pid]


def mock_cpu(user=0, nice=0, system=0, idle=0, iowait=0,
             irq=0, softirq=0, steal=0, guest=0, guest_nice=0):
    """Las 10 categorías crudas de la línea 'cpu', como las devuelve procfs.

    Recordá que son ACUMULADAS: en los tests se pasan valores absolutos y el
    delta lo hace el analizador entre dos _ciclo().
    """
    return {"user": user, "nice": nice, "system": system, "idle": idle,
            "iowait": iowait, "irq": irq, "softirq": softirq, "steal": steal,
            "guest": guest, "guest_nice": guest_nice}


def mock_stat_global(cpu=None, ctxt=0, btime=1_700_000_000, processes=0,
                     procs_running=0, procs_blocked=0):
    return {"cpu": cpu if cpu is not None else mock_cpu(), "ctxt": ctxt,
            "btime": btime, "processes": processes,
            "procs_running": procs_running, "procs_blocked": procs_blocked}


def mock_meminfo(**overrides):
    """meminfo con los campos que consume el analizador. Pasá None para borrar
    una clave (sirve para simular kernels sin MemAvailable)."""
    base = {"MemTotal": 1000, "MemFree": 200, "MemAvailable": 700,
            "Buffers": 100, "Cached": 400, "SwapTotal": 500, "SwapFree": 500}
    base.update(overrides)
    return {key: value for key, value in base.items() if value is not None}


def mock_loadavg(load_1m=0.5, load_5m=0.4, load_15m=0.3):
    return {"load_1m": load_1m, "load_5m": load_5m, "load_15m": load_15m,
            "runnable": 1, "total_threads": 100, "last_pid": 12345}


def mock_uptime(uptime=3600.0, idle=28000.0):
    return {"uptime": uptime, "idle": idle}


def mock_proc_stat(state="S", num_threads=1):
    """stat por PID: solo los dos campos que consume este analizador."""
    return {"state": state, "num_threads": num_threads}


class FakeClock:
    """Reloj falso con los DOS relojes separados: `t` es el de pared (time()) y
    `mono` el monotónico. Tenerlos sueltos permite moverlos de forma
    independiente, que es justo lo que hace NTP en la vida real."""

    def __init__(self, t=1000.0, mono=500.0):
        self.t = t
        self.mono = mono

    def time(self):
        return self.t

    def monotonic(self):
        return self.mono


class TestSystem(unittest.TestCase):

    def setUp(self):
        self.clock = FakeClock()
        patcher = patch("src.analizadores.sistema.time", self.clock)
        self.addCleanup(patcher.stop)
        patcher.start()

    def _analyzer(self, pids=None, snapshot=None, **mock_kwargs):
        procfs = MockProcFS(**mock_kwargs)
        return AnalyzerSystem(procfs, list(pids or []), snapshot if snapshot is not None else {}, 1)

    def _data(self, analyzer):
        return analyzer.snapshot["sistema"]["data"]

    def _second_cycle(self, analyzer, stat_global, elapsed=1.0):
        """Corre un segundo ciclo con una nueva lectura de /proc/stat."""
        analyzer.procfs.stat_global = stat_global
        self.clock.mono += elapsed
        self.clock.t += elapsed
        analyzer._ciclo()
        return self._data(analyzer)

    #region forma del snapshot y primer ciclo

    def test_ciclo_publica_clave_sistema_con_ts_y_data(self):
        a = self._analyzer()
        a._ciclo()
        self.assertIn("sistema", a.snapshot)
        self.assertIn("ts", a.snapshot["sistema"])
        self.assertIn("data", a.snapshot["sistema"])

    def test_data_es_plano_no_indexado_por_pid(self):
        """A diferencia de los otros seis, data NO es {pid: {...}}."""
        a = self._analyzer(pids=[1], stats={1: mock_proc_stat()})
        a._ciclo()
        data = self._data(a)
        self.assertIn("mem_total_kb", data)
        self.assertNotIn(1, data)

    def test_primer_ciclo_derivados_none_pero_estaticos_presentes(self):
        """Sin lectura previa no hay delta, pero las claves existen igual."""
        a = self._analyzer()
        a._ciclo()
        data = self._data(a)
        self.assertIsNone(data["cpu_pct"])
        self.assertIsNone(data["cpu_user_pct"])
        self.assertIsNone(data["ctxt_switches_per_sec"])
        self.assertIsNone(data["forks_per_sec"])
        # los de foto instantánea sí salen desde el ciclo 1
        self.assertEqual(data["mem_total_kb"], 1000)
        self.assertEqual(data["load_1m"], 0.5)
        self.assertEqual(data["uptime"], 3600.0)
        self.assertEqual(data["boot_time"], 1_700_000_000)

    def test_prev_se_guarda_crudo_desde_el_primer_ciclo(self):
        a = self._analyzer()
        a._ciclo()
        self.assertEqual(a._prev["stat"], a.procfs.stat_global)
        self.assertEqual(a._prev["mono"], self.clock.mono)

    #endregion

    #region CPU%

    def test_cpu_pct_es_busy_sobre_total(self):
        """delta: 25 busy + 75 idle -> 25%."""
        a = self._analyzer(stat_global=mock_stat_global(cpu=mock_cpu()))
        a._ciclo()
        data = self._second_cycle(a, mock_stat_global(cpu=mock_cpu(user=25, idle=75)))
        self.assertAlmostEqual(data["cpu_pct"], 25.0)

    def test_iowait_cuenta_como_idle(self):
        """iowait NO es CPU ocupada: es idle con una tarea esperando I/O.
        50 user + 50 iowait -> 50%, no 100%."""
        a = self._analyzer()
        a._ciclo()
        data = self._second_cycle(a, mock_stat_global(cpu=mock_cpu(user=50, iowait=50)))
        self.assertAlmostEqual(data["cpu_pct"], 50.0)
        self.assertAlmostEqual(data["cpu_iowait_pct"], 50.0)

    def test_las_diez_categorias_suman_cien(self):
        a = self._analyzer()
        a._ciclo()
        data = self._second_cycle(a, mock_stat_global(
            cpu=mock_cpu(user=10, nice=5, system=20, idle=50, iowait=5,
                         irq=3, softirq=4, steal=3)))
        total = sum(data[field] for field in AnalyzerSystem.CPU_PCT_FIELDS)
        self.assertAlmostEqual(total, 100.0)

    def test_guest_no_se_cuenta_dos_veces(self):
        """El kernel suma el tiempo de guest a 'user' Y a 'guest'. Con delta
        user=100 (de los cuales 40 son guest) e idle=100: el desglose disjunto
        es user=60/200=30%, guest=40/200=20%, idle=50%. Sin restar, user daría
        50% y la fila sumaría 120%."""
        a = self._analyzer()
        a._ciclo()
        data = self._second_cycle(a, mock_stat_global(
            cpu=mock_cpu(user=100, guest=40, idle=100)))
        self.assertAlmostEqual(data["cpu_user_pct"], 30.0)
        self.assertAlmostEqual(data["cpu_guest_pct"], 20.0)
        self.assertAlmostEqual(data["cpu_idle_pct"], 50.0)
        self.assertAlmostEqual(sum(data[f] for f in AnalyzerSystem.CPU_PCT_FIELDS), 100.0)

    def test_guest_nice_se_resta_de_nice(self):
        a = self._analyzer()
        a._ciclo()
        data = self._second_cycle(a, mock_stat_global(
            cpu=mock_cpu(nice=100, guest_nice=40, idle=100)))
        self.assertAlmostEqual(data["cpu_nice_pct"], 30.0)
        self.assertAlmostEqual(data["cpu_guest_nice_pct"], 20.0)

    def test_cpu_pct_no_depende_del_intervalo(self):
        """busy/total es una fracción pura: el mismo reparto de jiffies da el
        mismo % aunque el intervalo sea otro. (Al revés que el CPU% por proceso,
        que sí necesita CLK_TCK y elapsed.)"""
        a = self._analyzer()
        a._ciclo()
        data = self._second_cycle(a, mock_stat_global(cpu=mock_cpu(user=40, idle=60)),
                                  elapsed=7.3)
        self.assertAlmostEqual(data["cpu_pct"], 40.0)

    def test_sin_movimiento_de_jiffies_los_pct_quedan_none(self):
        """Dos lecturas idénticas -> delta total 0 -> no se divide por cero."""
        a = self._analyzer()
        a._ciclo()
        data = self._second_cycle(a, mock_stat_global(cpu=mock_cpu()))
        self.assertIsNone(data["cpu_pct"])
        self.assertIsNone(data["cpu_user_pct"])

    def test_cpu_pct_fields_coincide_con_las_claves_publicadas(self):
        """Contrato con el Display: la constante y las claves reales no se
        pueden separar. Si alguien agrega una categoría en procfs y no acá,
        este test lo caza."""
        a = self._analyzer()
        a._ciclo()
        data = self._data(a)
        for field in AnalyzerSystem.CPU_PCT_FIELDS:
            self.assertIn(field, data)
        self.assertEqual(len(AnalyzerSystem.CPU_PCT_FIELDS), 10)
        self.assertNotIn("cpu_pct", AnalyzerSystem.CPU_PCT_FIELDS)

    #endregion

    #region tasas por segundo

    def test_ctxt_y_forks_por_segundo(self):
        a = self._analyzer(stat_global=mock_stat_global(ctxt=1000, processes=50))
        a._ciclo()
        data = self._second_cycle(a, mock_stat_global(ctxt=3000, processes=110),
                                  elapsed=2.0)
        self.assertAlmostEqual(data["ctxt_switches_per_sec"], 1000.0)
        self.assertAlmostEqual(data["forks_per_sec"], 30.0)

    def test_usa_monotonic_y_no_el_reloj_de_pared(self):
        """Si NTP mueve time() una hora hacia atrás entre dos ciclos, las tasas
        tienen que seguir bien: el elapsed sale de monotonic()."""
        a = self._analyzer(stat_global=mock_stat_global(ctxt=0))
        a._ciclo()
        a.procfs.stat_global = mock_stat_global(ctxt=2000)
        self.clock.mono += 2.0      # 2 segundos reales
        self.clock.t -= 3600.0      # el reloj de pared retrocede una hora
        a._ciclo()
        self.assertAlmostEqual(self._data(a)["ctxt_switches_per_sec"], 1000.0)

    #endregion

    #region conteo de procesos

    def test_conteo_por_estado(self):
        a = self._analyzer(
            pids=[1, 2, 3, 4],
            stats={1: mock_proc_stat("R"), 2: mock_proc_stat("S"),
                   3: mock_proc_stat("S"), 4: mock_proc_stat("Z")},
        )
        a._ciclo()
        data = self._data(a)
        self.assertEqual(data["procs_total"], 4)
        self.assertEqual(data["procs_by_state"]["R"], 1)
        self.assertEqual(data["procs_by_state"]["S"], 2)
        self.assertEqual(data["procs_by_state"]["Z"], 1)
        self.assertEqual(data["procs_by_state"]["D"], 0)   # garantizado por fromkeys

    def test_estado_fuera_de_rsdtz_no_rompe(self):
        """'I' (kernel thread ocioso) no está en _STATES y es comunísimo:
        en una corrida real aparecen ~80. Se agrega como clave nueva."""
        a = self._analyzer(pids=[1], stats={1: mock_proc_stat("I")})
        a._ciclo()
        self.assertEqual(self._data(a)["procs_by_state"]["I"], 1)
        self.assertEqual(self._data(a)["procs_total"], 1)

    def test_threads_total_suma_los_lwps(self):
        a = self._analyzer(
            pids=[1, 2],
            stats={1: mock_proc_stat(num_threads=4), 2: mock_proc_stat(num_threads=7)},
        )
        a._ciclo()
        self.assertEqual(self._data(a)["threads_total"], 11)

    def test_proceso_muerto_no_se_cuenta(self):
        """Murió entre el listado del collector y la lectura: se saltea, no
        rompe el ciclo ni suma al total."""
        a = self._analyzer(
            pids=[1, 2],
            stats={1: mock_proc_stat(num_threads=3), 2: mock_proc_stat(num_threads=5)},
            dead={2: ProcessLookupError()},
        )
        a._ciclo()
        data = self._data(a)
        self.assertEqual(data["procs_total"], 1)
        self.assertEqual(data["threads_total"], 3)

    #endregion

    #region memoria

    def test_meminfo_con_sufijo_kb_y_swap_calculado(self):
        a = self._analyzer(meminfo=mock_meminfo(SwapTotal=1000, SwapFree=400))
        a._ciclo()
        data = self._data(a)
        self.assertEqual(data["mem_total_kb"], 1000)
        self.assertEqual(data["mem_cached_kb"], 400)
        self.assertEqual(data["swap_used_kb"], 600)     # total - free

    def test_mem_available_ausente_da_none(self):
        """MemAvailable no existe antes del kernel 3.14."""
        a = self._analyzer(meminfo=mock_meminfo(MemAvailable=None))
        a._ciclo()
        self.assertIsNone(self._data(a)["mem_available_kb"])

    #endregion

    #region tops (leídos de otras dimensiones del snapshot)

    def test_top_cpu_ordena_desc_y_corta_en_tres(self):
        snapshot = {"cpu": {"ts": 1, "data": {1: 10.0, 2: 90.0, 3: 50.0, 4: 70.0}}}
        a = self._analyzer(snapshot=snapshot)
        a._ciclo()
        self.assertEqual(self._data(a)["top_cpu"],
                         [{"pid": 2, "cpu_pct": 90.0},
                          {"pid": 4, "cpu_pct": 70.0},
                          {"pid": 3, "cpu_pct": 50.0}])

    def test_top_cpu_ignora_los_none(self):
        """Un PID visto por primera vez tiene cpu None; no puede entrar al top
        ni reventar el sort."""
        snapshot = {"cpu": {"ts": 1, "data": {1: None, 2: 5.0}}}
        a = self._analyzer(snapshot=snapshot)
        a._ciclo()
        self.assertEqual(self._data(a)["top_cpu"], [{"pid": 2, "cpu_pct": 5.0}])

    def test_top_mem_ordena_por_rss_e_ignora_kernel_threads(self):
        """Los kernel threads no tienen espacio de usuario: vm_rss es None."""
        snapshot = {"memory": {"ts": 1, "data": {
            1: {"vm_rss": 100}, 2: {"vm_rss": None}, 3: {"vm_rss": 900}}}}
        a = self._analyzer(snapshot=snapshot)
        a._ciclo()
        self.assertEqual(self._data(a)["top_mem"],
                         [{"pid": 3, "rss_kb": 900}, {"pid": 1, "rss_kb": 100}])

    def test_tops_none_si_la_dimension_todavia_no_publico(self):
        """None y no []: 'no sé' es distinto de 'no hay nadie'."""
        a = self._analyzer(snapshot={})
        a._ciclo()
        self.assertIsNone(self._data(a)["top_cpu"])
        self.assertIsNone(self._data(a)["top_mem"])

    #endregion

    #region robustez

    def test_proc_inaccesible_no_publica_nada(self):
        """Si falla una lectura global, mejor no publicar que publicar a medias."""
        a = self._analyzer(globals_raise=FileNotFoundError())
        a._ciclo()
        self.assertNotIn("sistema", a.snapshot)

    def test_proc_inaccesible_no_pisa_el_prev(self):
        a = self._analyzer(stat_global=mock_stat_global(ctxt=777))
        a._ciclo()
        a.procfs.globals_raise = PermissionError()
        a._ciclo()
        self.assertEqual(a._prev["stat"]["ctxt"], 777)

    #endregion


if __name__ == "__main__":
    unittest.main()
