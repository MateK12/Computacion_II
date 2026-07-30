import time

from .pacing import sleep_interval


class AnalyzerMemory:
    # Contadores acumulados de /proc/<pid>/stat que se publican como delta por intervalo.
    FAULT_FIELDS = ("minflt", "cminflt", "majflt", "cmajflt")

    def __init__(self, procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval
        self._prev = {}                    # {pid: faults acumulados + starttime del ciclo anterior}

    def _parse_kb(self, status, key):
        """'1282704 kB' -> 1282704 (int). Devuelve None si el campo no está
        (p. ej. kernel threads, que no tienen sección Vm* porque no tienen
        espacio de direcciones de usuario)."""
        valor = status.get(key)
        if valor is None:
            return None
        return int(valor.split()[0])   # "1282704 kB" -> "1282704" -> 1282704

    def _extract(self, status):
        """Arma la entrada de memoria de un proceso a partir de su status crudo.
        Todo en kB (unidad nativa de /proc); None si el proceso no tiene esa info."""
        return {
            "vm_size": self._parse_kb(status, "VmSize"),   # virtual total
            "vm_rss": self._parse_kb(status, "VmRSS"),     # residente en RAM
            "vm_hwm": self._parse_kb(status, "VmHWM"),     # pico de RSS
            "vm_data": self._parse_kb(status, "VmData"),   # data + heap
            "vm_stack": self._parse_kb(status, "VmStk"),   # stack
            "vm_exe": self._parse_kb(status, "VmExe"),     # text (código)
            "vm_lib": self._parse_kb(status, "VmLib"),     # librerías compartidas
            "vm_swap": self._parse_kb(status, "VmSwap"),   # desalojado a swap
        }

    def _guard(self, pid, stat):
        """Si el starttime no coincide con el guardado, el PID fue reusado por otro
        proceso: se descarta el previo para no restar contadores de un proceso ajeno."""
        if pid in self._prev and self._prev[pid]["starttime"] != stat["starttime"]:
            del self._prev[pid]

    def _fault_deltas(self, pid, stat):
        """Page faults del intervalo: acumulado actual − acumulado del ciclo anterior.
        Primer ciclo de un PID → None (transitorio, la vista lo muestra como guión)."""
        prev = self._prev.get(pid)
        if prev is None:
            return {f"{field}_delta": None for field in self.FAULT_FIELDS}
        return {f"{field}_delta": stat[field] - prev[field] for field in self.FAULT_FIELDS}

    def _rebuild_prev(self, stat):
        """Lo que el próximo ciclo necesita recordar de este proceso."""
        entry = {field: stat[field] for field in self.FAULT_FIELDS}
        entry["starttime"] = stat["starttime"]
        return entry

    def _ciclo(self):
        """Un solo paso: lee status y stat de cada PID y publica la dimensión 'memory'."""
        data = {}
        new_prev = {}
        for pid in self.shared_pids:
            try:
                status = self.procfs.read_status(pid)
                stat = self.procfs.read_stat(pid)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            self._guard(pid, stat)
            data[pid] = {**self._extract(status), **self._fault_deltas(pid, stat)}
            new_prev[pid] = self._rebuild_prev(stat)
        # una sola asignación al proxy: reemplazo entero (evita el gotcha del Manager.dict)
        self.snapshot["memory"] = {"ts": time.time(), "data": data}
        self._prev = new_prev

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            sleep_interval(self.interval)
