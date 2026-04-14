import os

def info_proceso(pid):
    """Lee información de un proceso desde /proc."""
    base = f"/proc/{pid}" # ruta base del proceso

    try:
        # Comando
        with open(f"{base}/cmdline", "rb") as f:
            cmdline = f.read().replace(b"\x00", b" ").decode().strip()

        # Estado
        with open(f"{base}/status") as f:
            status = {}
            for linea in f:
                if ":" in linea:
                    k, v = linea.split(":", 1)
                    status[k.strip()] = v.strip()

        # File descriptors
        fds = os.listdir(f"{base}/fd")

        return {
            "pid": pid,
            "cmdline": cmdline,
            "name": status.get("Name"),
            "state": status.get("State"),
            "ppid": status.get("PPid"),
            "threads": status.get("Threads"),
            "memory_vm": status.get("VmSize"),
            "memory_rss": status.get("VmRSS"),
            "open_fds": len(fds),
        }
    except (FileNotFoundError, PermissionError) as e:
        return {"error": str(e)}

# Ejemplo: info del proceso actual
info = info_proceso(2264)
for k, v in info.items():
    print(f"{k}: {v}")
