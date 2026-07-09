
import os
import time

class AnalyzerFileDescriptor:
    def __init__(self,procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval

    def add_summary(self, key, value):
        self._summary[key] = value

    def get_summary(self):
        return self._summary
    
    def _ciclo(self):
        for pid in self.shared_pids:
            pass

        
    def _parse_fd_type(self, fd_dest: str) -> str:
        """Devuelve 'file', 'socket', 'pipe' o 'unknown' según el tipo de FD."""
        if fd_dest.startswith("socket:"):
            return "socket"
        elif fd_dest.startswith("pipe:"):
            return "pipe"
        elif os.path.exists(fd_dest):
            return "file"
        else:
            return "unknown"
