import time

class AnalyzerScheduling:
    def __init__(self, procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval
        self._prev = {}


    def _guard(self,pid, status):
        """Verifica si el startTime es el mismo que el previo. Si no, resetea el previo (un nuevo proceso usa ese PID)"""
        if pid in self._prev:
            if self._prev[pid]["starttime"] != status["starttime"]:
                del self._prev[pid]

    def _build_scheduling_data(self, pid, stat, schedStat, status):
        """Construye el dict de scheduling para un PID.

        Los campos estáticos (nice/priority/policy/afinidad) salen siempre, ya
        disponibles desde la primera lectura. Los de delta (cpu_usage y
        runqueue_wait_pct) arrancan en None y solo se calculan si hay una lectura
        previa del mismo PID.
        """
        data = {
            "priority": stat["priority"],
            "nice": stat["nice"],
            "rt_priority": stat["rt_priority"],
            "policy": self._parse_policy(stat["policy"]),
            "affinity": status.get("Cpus_allowed_list", "N/A"),
            "timeslices": schedStat["timeslices"],
            "cpu_usage": None,          # % del intervalo corriendo en CPU
            "runqueue_wait_pct": None,  # % del intervalo esperando en runqueue
        }

        previous = self._prev.get(pid)
        if previous is None:  # primera vez que vemos este PID: sin delta todavía
            return data

        elapsed_time = time.time() - previous["ts"]  # en segundos
        delta_cpu = schedStat["cpu_time"] - previous["cpu_time"]
        delta_wait = schedStat["runqueue_wait"] - previous["runqueue_wait"]
        # ns -> s (* 1e-9) sobre el tiempo real transcurrido, expresado en %
        data["cpu_usage"] = delta_cpu / elapsed_time * 1e-9 * 100
        data["runqueue_wait_pct"] = delta_wait / elapsed_time * 1e-9 * 100
        return data
    def _ciclo(self):
        """Un solo paso: lee el status de cada PID y publica la dimensión 'scheduling'."""
        data = {}
        new_prev = {}
        for pid in self.shared_pids:
            try:
                stat = self.procfs.read_stat(pid)
                schedStat = self.procfs.read_schedstat(pid)
                status = self.procfs.read_status(pid)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            self._guard(pid, stat)
            data[pid] = self._build_scheduling_data(pid, stat, schedStat,status)
            new_prev[pid] = self._rebuild_prev( stat, schedStat)
        self.snapshot["scheduling"] = {"ts": time.time(), "data": data}
        self._prev = new_prev 

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            time.sleep(self.interval)
            
    def _rebuild_prev(self,status,sched_stat):
        """Reconstruye el diccionario previo a partir del snapshot actual."""

        return {
            "starttime": status["starttime"],
            "cpu_time": sched_stat["cpu_time"],
            "runqueue_wait": sched_stat["runqueue_wait"],
            "timeslices": sched_stat["timeslices"],
            "ts": time.time()
        }
    # Mapa entero -> nombre de la política de scheduling (man sched(7)).
    _POLICIES = {
        0: "SCHED_NORMAL",
        1: "SCHED_FIFO",
        2: "SCHED_RR",
        3: "SCHED_BATCH",
        5: "SCHED_IDLE",
        6: "SCHED_DEADLINE",
    }

    @classmethod
    def _parse_policy(cls, policy: int) -> str:
        """Convierte el entero crudo de /proc/<pid>/stat en una cadena legible."""
        return cls._POLICIES.get(policy, f"UNKNOWN({policy})")