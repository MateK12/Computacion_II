import time
from src.procfs import ProcFS


class AnalyzerSummary:
    def __init__(self, procfs: ProcFS, shared_pids, snapshot, interval: int):
        self.procfs = procfs
        self.shared_pids = shared_pids
        self.snapshot = snapshot
        self.interval = interval

    def _extract(self, status: dict) -> dict:
        """Arma la entrada de resumen de un proceso a partir de su status crudo."""
        return {
            "name": status["Name"],
            "state": status["State"][0],  
            "ppid": int(status["PPid"]),
            "uid": int(status["Uid"].split()[0]),
            "gid": int(status["Gid"].split()[0]),
            "threads": int(status["Threads"]),
        }

    def _ciclo(self):
        """Un solo paso: lee el status de cada PID y publica la dimensión 'summary'."""
        data = {}
        for pid in self.shared_pids:
            try:
                status = self.procfs.read_status(pid)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue  # el proceso murió entre el listado y la lectura; lo salteamos
            data[pid] = self._extract(status)
        self.snapshot["summary"] = {"ts": time.time(), "data": data}

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            time.sleep(self.interval)