import time

from .pacing import sleep_interval

from src.procfs import ProcFS


class AnalyzerSystem:
    """Analizador de las métricas GLOBALES de la máquina (dimensión 'sistema').
    """

    _STATES = ("R", "S", "D", "T", "Z")

    CPU_PCT_FIELDS = tuple(f"cpu_{field}_pct" for field in ProcFS.CPU_FIELDS)

    def __init__(self, procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval
        # Lectura anterior de /proc/stat, cruda, más su estampa MONOTÓNICA.
        # No es por-PID: es una sola. No hace falta _guard como en cpu/scheduling
        # porque /proc/stat no se recicla (si el sistema rebootea, morimos con él).
        self._prev = None

    # --- métricas de una sola lectura (foto instantánea) ----------------------

    @staticmethod
    def _extract_meminfo(meminfo):
        """Los valores de /proc/meminfo vienen en kB; el sufijo _kb lo deja explícito."""
        return {
            "mem_total_kb": meminfo["MemTotal"],
            "mem_free_kb": meminfo["MemFree"],        # RAM literalmente sin usar (engañosa)
            "mem_available_kb": meminfo.get("MemAvailable"),  # no existe antes de kernel 3.14
            "mem_buffers_kb": meminfo["Buffers"],
            "mem_cached_kb": meminfo["Cached"],       # page cache: reclamable
            "swap_total_kb": meminfo["SwapTotal"],
            "swap_used_kb": meminfo["SwapTotal"] - meminfo["SwapFree"],
        }

    def _count_processes(self):
        """Recorre los PIDs vivos y cuenta procesos por estado y threads totales.

        Único punto donde este analizador itera. Los procesos se mueren mientras
        los leemos, así que el except es igual de necesario que en los demás.
        """
        by_state = dict.fromkeys(self._STATES, 0)
        total = 0
        threads = 0
        for pid in self.shared_pids:
            try:
                stat = self.procfs.read_stat(pid)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue  # murió entre el listado del collector y esta lectura
            total += 1
            state = stat["state"]
            by_state[state] = by_state.get(state, 0) + 1
            threads += stat["num_threads"]
        return {
            "procs_total": total,
            "procs_by_state": by_state,
            "threads_total": threads,
        }

    # --- métricas que necesitan una lectura previa (delta) --------------------

    def _derived(self, stat, now):
        """Todo lo que se calcula por delta contra la lectura anterior.

        En el primer ciclo las claves EXISTEN pero valen None, para que el Display
        no tenga que preguntarse si la dimensión ya arrancó.
        """
        derived = {f"cpu_{field}_pct": None for field in stat["cpu"]}
        derived["cpu_pct"] = None
        derived["ctxt_switches_per_sec"] = None
        derived["forks_per_sec"] = None

        if self._prev is None:
            return derived

        previous = self._prev["stat"]
        elapsed_time = now - self._prev["mono"]

        delta = {field: stat["cpu"][field] - previous["cpu"][field] for field in stat["cpu"]}

        delta["user"] -= delta["guest"]
        delta["nice"] -= delta["guest_nice"]

        total = sum(delta.values())
        if total > 0:
            for field, jiffies in delta.items():
                derived[f"cpu_{field}_pct"] = jiffies / total * 100
            # No hace falta CLK_TCK ni elapsed_time: 'total' YA es la capacidad de
            # CPU de la ventana (todos los cores). Es una fracción pura, las
            # unidades se cancelan. Por eso esto nunca pasa de 100%, a diferencia
            # del CPU% de un proceso, que con 3 cores saturados da 300%.
            idle = delta["idle"] + delta["iowait"]
            derived["cpu_pct"] = (total - idle) / total * 100

        if elapsed_time > 0:
            for key, name in (("ctxt", "ctxt_switches_per_sec"),
                              ("processes", "forks_per_sec")):
                if key in stat and key in previous:
                    derived[name] = (stat[key] - previous[key]) / elapsed_time

        return derived

    # --- tops derivados de otras dimensiones del snapshot ---------------------

    def _top_cpu(self, n=3):
        """Top N por CPU%, leído de la dimensión 'cpu'. None si todavía no publicó."""
        dimension = self.snapshot.get("cpu")
        if not dimension:
            return None
        pairs = [(pid, pct) for pid, pct in dimension["data"].items() if pct is not None]
        pairs.sort(key=lambda pair: pair[1], reverse=True)
        return [{"pid": pid, "cpu_pct": pct} for pid, pct in pairs[:n]]

    def _top_mem(self, n=3):
        """Top N por RSS, leído de la dimensión 'memory'. None si todavía no publicó."""
        dimension = self.snapshot.get("memory")
        if not dimension:
            return None
        pairs = [(pid, info["vm_rss"]) for pid, info in dimension["data"].items()
                 if info.get("vm_rss") is not None]  # los kernel threads no tienen RSS
        pairs.sort(key=lambda pair: pair[1], reverse=True)
        return [{"pid": pid, "rss_kb": rss} for pid, rss in pairs[:n]]

    # --- ciclo ----------------------------------------------------------------

    def _ciclo(self):
        """Un solo paso: lee los archivos globales y publica la dimensión 'sistema'."""
        try:
            stat = self.procfs.read_stat_global()
            meminfo = self.procfs.read_meminfo()
            loadavg = self.procfs.read_loadavg()
            uptime = self.procfs.read_uptime()
        except (FileNotFoundError, PermissionError):
            return  # /proc inaccesible: mejor no publicar nada que publicar basura
        # monotonic() y no time(): esto se va a RESTAR. time() es reloj de pared y
        # un ajuste de NTP o un suspend/resume lo puede mover hacia atrás.
        now = time.monotonic()

        data = {}
        data.update(self._extract_meminfo(meminfo))
        data.update({
            "load_1m": loadavg["load_1m"],    # promedio exponencial de tareas en R + D
            "load_5m": loadavg["load_5m"],
            "load_15m": loadavg["load_15m"],
            "uptime": uptime["uptime"],       # segundos desde el boot
            "boot_time": stat.get("btime"),   # instante del boot, epoch UNIX
        })
        data.update(self._count_processes())
        data.update(self._derived(stat, now))
        data["top_cpu"] = self._top_cpu()
        data["top_mem"] = self._top_mem()

        # una sola asignación al proxy: reemplazo entero (evita el gotcha del Manager.dict)
        self.snapshot["sistema"] = {"ts": time.time(), "data": data}
        self._prev = {"stat": stat, "mono": now}

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            sleep_interval(self.interval)
