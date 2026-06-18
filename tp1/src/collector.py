import time


class Collector:
    def __init__(self, procfs, shared_pids, sleep_interval):   
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.sleep_interval = sleep_interval

    def _ciclo(self):
        """Un solo paso: lee los PIDs y los publica en la estructura compartida."""
        nuevos_pids = list(self.procfs.list_pids())
        # [:] muta el proxy in-place -> el cambio viaja al Manager y lo ven los demás
        self.shared_pids[:] = nuevos_pids

    def collect(self):
        """Loop de vida del recolector: un ciclo cada sleep_interval segundos."""
        while True:
            self._ciclo()
            time.sleep(self.sleep_interval)
