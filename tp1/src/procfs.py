import os

class ProcFS:
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
            "utime": int(fields[11]),  # campo 14, en jiffies
            "stime": int(fields[12]),  # campo 15, en jiffies
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