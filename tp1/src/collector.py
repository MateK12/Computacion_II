class Collector:
    def __init__(self, procfs, shared_pids, shutdown_event, sleep_interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.shutdown_event = shutdown_event
        self.sleep_interval = sleep_interval

    def _ciclo(self):
        """Un solo paso: lee los PIDs y los publica en la estructura compartida."""
        nuevos_pids = list(self.procfs.list_pids())
        # [:] muta el proxy in-place -> el cambio viaja al Manager y lo ven los demás
        self.shared_pids[:] = nuevos_pids

    def collect(self):
        """Loop de vida del recolector: un ciclo cada sleep_interval segundos."""
        while not self.shutdown_event.is_set():
            self._ciclo()
            self.shutdown_event.wait(self.sleep_interval)
