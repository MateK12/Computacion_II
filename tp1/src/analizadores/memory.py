import time


class AnalyzerMemory:
    def __init__(self, procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval

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

    def _ciclo(self):
        """Un solo paso: lee el status de cada PID y publica la dimensión 'memory'."""
        data = {}
        for pid in self.shared_pids:
            try:
                status = self.procfs.read_status(pid)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue  # el proceso murió entre el listado y la lectura; lo salteamos
            data[pid] = self._extract(status)
        # una sola asignación al proxy: reemplazo entero (evita el gotcha del Manager.dict)
        self.snapshot["memory"] = {"ts": time.time(), "data": data}

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            time.sleep(self.interval)
