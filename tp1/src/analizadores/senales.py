import time


class AnalyzerSignals:
    def __init__(self, procfs, shared_pids, snapshot, interval):
        self.procfs = procfs
        self.shared_pids = shared_pids     # proxy (Manager.list)
        self.snapshot = snapshot           # proxy (Manager.dict)
        self.interval = interval

    def _decode_mask(self, hex_str):
        """
        Decodifica mascara (en hexa) proveniente de /proc/<pid>/status a lista de señales (int).
        """
        mask = int(hex_str, 16)            
        signals = []
        for i in range(64):
            if mask & (1 << i):            # ¿está prendido el bit i?
                signals.append(i + 1)      # bit i -> señal i+1
        return signals

    def _extract(self, status):
        """Arma la entrada de señales de un proceso a partir de su status crudo.
        """
        return {
            "blocked": self._decode_mask(status["SigBlk"]),   
            "ignored": self._decode_mask(status["SigIgn"]),   
            "caught": self._decode_mask(status["SigCgt"]),    
            "pending_thread": self._decode_mask(status["SigPnd"]),   
            "pending_shared": self._decode_mask(status["ShdPnd"]),   
        }

    def _ciclo(self):
        """Un solo paso: lee el status de cada PID y publica la dimensión 'signals'."""
        data = {}
        for pid in self.shared_pids:
            try:
                status = self.procfs.read_status(pid)
            except (FileNotFoundError, ProcessLookupError):
                continue  # el proceso murió entre el listado y la lectura; lo salteamos
            data[pid] = self._extract(status)
        self.snapshot["signals"] = {"ts": time.time(), "data": data}

    def analyze(self):
        """Loop de vida del analizador: un ciclo cada `interval` segundos."""
        while True:
            self._ciclo()
            time.sleep(self.interval)
