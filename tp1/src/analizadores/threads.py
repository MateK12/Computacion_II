import time
import os


class AnalyzerThreads:
    def __init__(self, procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval
        # _prev anidado: {pid: {tid: {"starttime", "total_jiffies", "ts"}}}
        # Anidado por PID porque publicamos data[pid][tid] y porque el chequeo
        # de reuso (starttime) es por thread.
        self._prev = {}
        self._clk_tck = os.sysconf("SC_CLK_TCK")

    def _thread_cpu(self, pid, tid, stat, now):
        """CPU% de un thread por delta de jiffies. None si no hay lectura previa
        válida (primer ciclo o reuso del TID)."""
        total_jiffies = stat["utime"] + stat["stime"]
        prev = self._prev.get(pid, {}).get(tid)
        # reuso del TID: si el starttime cambió, el TID es otro thread -> sin delta
        if prev is not None and prev["starttime"] != stat["starttime"]:
            prev = None
        if prev is None:
            return None
        elapsed = now - prev["ts"]
        if elapsed <= 0:
            return None
        return (total_jiffies - prev["total_jiffies"]) / self._clk_tck / elapsed * 100

    def _ciclo(self):
        """Un solo paso: por cada PID recorre sus threads y publica 'threads'."""
        now = time.time()
        data = {}
        new_prev = {}
        for pid in self.shared_pids:
            try:
                tids = list(self.procfs.list_tids(pid))
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue  # el proceso murió o no tenemos permiso sobre sus threads
            threads = {}
            prev_threads = {}
            for tid in tids:
                try:
                    stat = self.procfs.read_thread_stat(pid, tid)
                    status = self.procfs.read_thread_status(pid, tid)
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    continue  # el thread murió a mitad de lectura o sin permiso; lo salteamos
                threads[tid] = {
                    "name": stat["comm"],
                    "state": stat["state"],
                    "cpu": self._thread_cpu(pid, tid, stat, now),
                    "ctxt": {
                        "vol": int(status.get("voluntary_ctxt_switches", 0)),
                        "nonvol": int(status.get("nonvoluntary_ctxt_switches", 0)),
                    },
                }
                prev_threads[tid] = {
                    "starttime": stat["starttime"],
                    "total_jiffies": stat["utime"] + stat["stime"],
                    "ts": now,
                }
            if threads:
                data[pid] = threads
                new_prev[pid] = prev_threads

        self.snapshot["threads"] = {"ts": now, "data": data}
        self._prev = new_prev

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            time.sleep(self.interval)
