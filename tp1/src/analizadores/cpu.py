import time
import os

class AnalyzerCPU:
    def __init__(self, procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval
        self._prev = {}
        self._clk_tck = os.sysconf("SC_CLK_TCK")


    def _guard(self,pid, status):
        """Verifica si el startTime es el mismo que el previo. Si no, resetea el previo (un nuevo proceso usa ese PID)"""
        if pid in self._prev:
            if self._prev[pid]["starttime"] != status["starttime"]:
                del self._prev[pid]

    def _calculate_cpu_usage_interval(self, pid, status):
        """Calcula el uso de CPU en porcentaje para un proceso dado."""
        utime = status["utime"]
        stime = status["stime"]
        total_jiffies = utime + stime
        
        previous_jiffies= self._prev.get(pid, {}).get("total_jiffies", None)
        if previous_jiffies is None: #si es la primera vez que se ve ese PID
            return None
        previous_timestamp = self._prev[pid]["ts"] 
        
        elapsed_time = time.time() - previous_timestamp # en segundos
        

        cpu_usage = (total_jiffies - previous_jiffies) / self._clk_tck / elapsed_time * 100

        return cpu_usage
    def _ciclo(self):
        """Un solo paso: lee el status de cada PID y publica la dimensión 'cpu'."""
        data = {}
        new_prev = {}
        for pid in self.shared_pids:
            try:
                status = self.procfs.read_stat(pid)
            except (FileNotFoundError, ProcessLookupError):
                continue
            self._guard(pid, status)
            data[pid] = self._calculate_cpu_usage_interval(pid, status)
            new_prev[pid] = self._rebuild_prev( status)
        self.snapshot["cpu"] = {"ts": time.time(), "data": data}
        self._prev = new_prev 

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            time.sleep(self.interval)
            
    def _rebuild_prev(self,status):
        """Reconstruye el diccionario previo a partir del snapshot actual."""
        total_jiffies = status["utime"] + status["stime"]
        return {
            "starttime": status["starttime"],
            "total_jiffies": total_jiffies,
            "ts": time.time()
        }