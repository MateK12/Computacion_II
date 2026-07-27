import os

class ProcFS:
    # Categorías de la línea 'cpu' de /proc/stat, en el orden en que las escribe el kernel.
    # Ojo: 'user' YA INCLUYE 'guest' y 'nice' YA INCLUYE 'guest_nice' (el kernel suma el
    # tiempo de guest a los dos contadores). Quien las use tiene que restar para no contar doble.
    CPU_FIELDS = ("user", "nice", "system", "idle", "iowait",
                  "irq", "softirq", "steal", "guest", "guest_nice")

    # Líneas de /proc/stat que traen un único valor escalar.
    STAT_SCALARS = ("ctxt", "btime", "processes", "procs_running", "procs_blocked")

    def __init__(self, procfs_path):
        self.procfs_path = procfs_path

    def _read_file(self, filename):
        with open(f"{self.procfs_path}/{filename}", "r") as f:
            return f.read()

    def read_stat(self, pid: int) -> dict:
        """Lee el archivo /proc/[pid]/stat y devuelve su contenido como un diccionario."""
        return self.parse_stat(self._read_file(f"{pid}/stat"))

    @staticmethod
    def parse_stat(stat_content: str) -> dict:
        """Parsea el contenido de /proc/[pid]/stat, esto es necesario porque el commando puede contener espacios y está entre paréntesis"""
        
        last_parenthesis = stat_content.rfind(")")
        pid_str, _, comm = stat_content[:last_parenthesis].partition("(")
        fields = stat_content[last_parenthesis + 1:].split()
        return {
            "pid": int(pid_str),
            "comm": comm,
            "state": fields[0],   # campo 3 del man
            "ppid": int(fields[1]),   # campo 4
            "minflt": int(fields[7]),  # campo 10, page faults menores
            "cminflt": int(fields[8]),  # campo 11, page faults
            "majflt": int(fields[9]),  # campo 12, page faults mayores
            "cmajflt": int(fields[10]),  # campo 13, page faults
            "utime": int(fields[11]),  # campo 14, en jiffies
            "stime": int(fields[12]),  # campo 15, en jiffies
            "priority": int(fields[15]),   # campo 18: prioridad interna del kernel
            "nice": int(fields[16]),   # campo 19: perilla del usuario -20..+19
            "num_threads": int(fields[17]),   # campo 20: cantidad de threads (LWPs) del proceso
            "starttime": int(fields[19]), #campo 22: tiempo de inicio en jiffies desde el boot
            "rt_priority": int(fields[37]),   # campo 40: 1..99 para FIFO/RR, 0 si normal
            "policy": int(fields[38])   # campo 41: entero crudo, lo traduce el analizador
        }

    def read_status(self, pid: int) -> dict:
        """Lee /proc/[pid]/status y lo devuelve parseado."""
        return self.parse_status(self._read_file(f"{pid}/status"))

    @staticmethod
    def parse_status(status_content: str) -> dict:
        """Parsea /proc/[pid]/status: una línea por dato, formato 'Clave:<tab>valor'.

        Devuelve TODAS las claves, con los valores como strings crudos.
        Nota:(unidades 'kB')
        """
        result = {}
        for line in status_content.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                result[key] = value.strip()
        return result
    def list_pids(self):
        """Generador que lista los PID de los procesos en /proc (carpetas numéricas)."""
        with os.scandir(self.procfs_path) as it:
            for entry in it:
                if entry.is_dir() and entry.name.isdigit():
                    yield int(entry.name)
    def list_tids(self, pid: int):
        """Generador que lista los TID de un proceso (carpetas de /proc/<pid>/task).

        En un proceso mono-thread hay una sola entrada, con tid == pid.
        """
        with os.scandir(f"{self.procfs_path}/{pid}/task") as it:
            for entry in it:
                if entry.is_dir() and entry.name.isdigit():
                    yield int(entry.name)

    def read_thread_stat(self, pid: int, tid: int) -> dict:
        """Lee /proc/<pid>/task/<tid>/stat. Mismo formato que <pid>/stat."""
        return self.parse_stat(self._read_file(f"{pid}/task/{tid}/stat"))

    def read_thread_status(self, pid: int, tid: int) -> dict:
        """Lee /proc/<pid>/task/<tid>/status. Mismo formato que <pid>/status."""
        return self.parse_status(self._read_file(f"{pid}/task/{tid}/status"))

    def read_schedstat(self, pid: int) -> dict:
        """Lee /proc/<pid>/schedstat y devuelve sus tres números crudos.

        Una sola línea: 'cpu_time runqueue_wait timeslices', todos en ns los dos
        primeros. runqueue_wait depende de CONFIG_SCHEDSTATS (puede venir 0).
        """
        return self.parse_schedstat(self._read_file(f"{pid}/schedstat"))

    @staticmethod
    def parse_schedstat(schedstat_content: str) -> dict:
        """Parsea la línea de /proc/<pid>/schedstat. Solo nombra, no interpreta."""
        cpu_time, runqueue_wait, timeslices = schedstat_content.split()
        return {
            "cpu_time": int(cpu_time),           # ns acumulados en CPU
            "runqueue_wait": int(runqueue_wait), # ns acumulados esperando en runqueue
            "timeslices": int(timeslices),
        }

    def read_fd_links(self, pid: int) -> dict:
        """Devuelve {fd: destino_crudo} para los FDs abiertos por el proceso.

        Solo lee el symlink; la interpretación del tipo es del analizador.
        """
        fd_dir = f"{self.procfs_path}/{pid}/fd"
        result = {}
        with os.scandir(fd_dir) as it:
            for entry in it:
                if entry.is_symlink():
                    result[int(entry.name)] = os.readlink(entry.path)
        return result

    # ------------------------------------------------------------------
    # Lecturas GLOBALES: archivos de la raíz de /proc, no de /proc/<pid>/.
    # No dependen de ningún proceso, así que no mueren con FileNotFoundError.
    # ------------------------------------------------------------------

    def read_stat_global(self) -> dict:
        """Lee /proc/stat (el global, no el de un pid) y lo devuelve parseado."""
        return self.parse_stat_global(self._read_file("stat"))

    @staticmethod
    def parse_stat_global(stat_content: str) -> dict:
        """Parsea /proc/stat: la línea 'cpu' agregada más los contadores escalares.

        La línea 'cpu' (sin número) YA es la suma de todos los cores; las 'cpu0',
        'cpu1', ... son el desglose por core y acá se ignoran, igual que 'intr' y
        'softirq' (vectores largos que el TP no usa).

        Todos los valores son CONTADORES ACUMULADOS desde el boot y hay que
        derivarlos por delta, salvo 'btime' (instante del boot, constante) y
        'procs_running'/'procs_blocked' (foto instantánea).
        Los de 'cpu' están en jiffies (USER_HZ, típicamente 100 por segundo por core).
        """
        result = {"cpu": dict.fromkeys(ProcFS.CPU_FIELDS, 0)}
        for line in stat_content.splitlines():
            fields = line.split()
            if not fields:
                continue
            key, values = fields[0], fields[1:]
            if key == "cpu":
                # zip corta en la secuencia más corta: si un kernel viejo no reporta
                # steal/guest/guest_nice, esas categorías se quedan en el 0 del fromkeys
                # en vez de reventar con IndexError.
                result["cpu"].update(
                    {name: int(value) for name, value in zip(ProcFS.CPU_FIELDS, values)}
                )
            elif key in ProcFS.STAT_SCALARS:
                result[key] = int(values[0])
        return result

    def read_meminfo(self) -> dict:
        """Lee /proc/meminfo y lo devuelve parseado."""
        return self.parse_meminfo(self._read_file("meminfo"))

    @staticmethod
    def parse_meminfo(meminfo_content: str) -> dict:
        """Parsea /proc/meminfo: una línea por dato, formato 'Clave:<espacios>valor kB'.

        Devuelve TODAS las claves con el valor como int. La UNIDAD ES kB y se
        descarta acá: quien muestre estos números tiene que saberlo (24293772 son
        ~23 GiB, no 24 MB). Algunas líneas (HugePages_Total, etc.) vienen sin unidad;
        el split() cubre los dos casos.
        """
        result = {}
        for line in meminfo_content.splitlines():
            key, sep, value = line.partition(":")
            parts = value.split()
            if sep and parts:
                result[key] = int(parts[0])
        return result

    def read_loadavg(self) -> dict:
        """Lee /proc/loadavg y lo devuelve parseado."""
        return self.parse_loadavg(self._read_file("loadavg"))

    @staticmethod
    def parse_loadavg(loadavg_content: str) -> dict:
        """Parsea la única línea de /proc/loadavg: '0.43 1.04 0.74 1/1534 16514'.

        Los tres primeros son promedios exponenciales de tareas en estado R + D
        (Linux cuenta el I/O ininterrumpible, no solo lo runnable). El cuarto campo
        es compuesto: 'runnable/total', y total cuenta THREADS, no procesos.
        """
        l1, l5, l15, entities, last_pid = loadavg_content.split()
        runnable, total_threads = entities.split("/")
        return {
            "load_1m": float(l1),
            "load_5m": float(l5),
            "load_15m": float(l15),
            "runnable": int(runnable),          # tareas en R en este instante
            "total_threads": int(total_threads),  # LWPs totales del sistema
            "last_pid": int(last_pid),          # último PID asignado por el kernel
        }

    def read_uptime(self) -> dict:
        """Lee /proc/uptime y lo devuelve parseado."""
        return self.parse_uptime(self._read_file("uptime"))

    @staticmethod
    def parse_uptime(uptime_content: str) -> dict:
        """Parsea la única línea de /proc/uptime: 'segundos_desde_boot segundos_idle'.

        El segundo campo está SUMADO sobre todos los cores, por eso suele ser
        mayor que el primero (en 8 cores puede ser hasta 8x).
        """
        uptime, idle = uptime_content.split()
        return {"uptime": float(uptime), "idle": float(idle)}