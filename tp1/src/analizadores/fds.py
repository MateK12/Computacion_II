import time


class AnalyzerFileDescriptor:
    def __init__(self, procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval

    def _parse_fd_type(self, fd_dest: str) -> str:
        """Devuelve 'socket', 'pipe', 'anon_inode', 'file' o 'unknown' según el
        destino crudo del symlink de /proc/<pid>/fd."""
        if fd_dest.startswith("socket:"):
            return "socket"
        elif fd_dest.startswith("pipe:"):
            return "pipe"
        elif fd_dest.startswith("anon_inode:"):
            return "anon_inode"
        elif fd_dest.startswith("/"):
            return "file"
        else:
            return "unknown"

    def _ciclo(self):
        """Un solo paso: lee los FDs de cada PID y publica la dimensión 'fds'."""
        data = {}
        for pid in self.shared_pids:
            try:
                fd_list = self.procfs.read_fd_links(pid)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue  # el proceso murió entre el listado y la lectura; lo salteamos
            data[pid] = {
                fd: {"dest": dest, "type": self._parse_fd_type(dest)}
                for fd, dest in fd_list.items()
            }
        # una sola asignación al proxy: reemplazo entero (evita el gotcha del Manager.dict)
        self.snapshot["fds"] = {"ts": time.time(), "data": data}

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            time.sleep(self.interval)
