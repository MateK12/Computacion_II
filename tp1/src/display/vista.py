"""Vistas del display: funciones puras que transforman una copia plana del
snapshot en una tabla lista para renderizar.

Acá no entra rich ni ningún proxy de multiprocessing: dict común -> ViewTable.
El proceso display hace `dict(snapshot)` una vez por frame y nos pasa esa copia;
el renderer recibe el ViewTable y lo dibuja sin saber de qué vista vino.
"""

from .models import ViewTable


# Dimensión vacía: lo que asumimos cuando un analizador todavía no publicó nada
# (los primeros segundos de vida del monitor, o si ese analizador murió).
_EMPTY_DIM = {"ts": None, "data": {}}
# (clave en la dimensión memory, etiqueta para el encabezado) — todo en kB,
# unidad nativa de /proc; los nombres Vm* son los de /proc/<pid>/status.
_MEMORY_COLUMNS = [
    ("vm_size", "VmSize(kB)"),
    ("vm_rss", "VmRSS(kB)"),
    ("vm_hwm", "VmHWM(kB)"),
    ("vm_data", "VmData(kB)"),
    ("vm_stack", "VmStk(kB)"),
    ("vm_exe", "VmExe(kB)"),
    ("vm_lib", "VmLib(kB)"),
    ("vm_swap", "VmSwap(kB)"),
]

def view_summary(data: dict) -> ViewTable:
    """Vista Resumen: una fila por proceso con estado, CPU%, RSS, threads y comando.
    La dimensión base es `summary`: un proceso sin entrada ahí no tiene fila.
    """
    summary = data.get("summary", _EMPTY_DIM)
    cpu_data = data.get("cpu", _EMPTY_DIM)["data"]
    memory_data = data.get("memory", _EMPTY_DIM)["data"]

    rows = []
    for pid in sorted(summary["data"]): 
        proc = summary["data"][pid]
        mem = memory_data.get(pid)
        rows.append([
            pid,
            proc["state"],
            cpu_data.get(pid),                   
            mem["vm_rss"] if mem else None,       # kB | None
            proc["threads"],
            proc["name"],
        ])

    return ViewTable(
        title="Resumen",
        columns=["PID", "Estado", "CPU%", "RSS(kB)", "Threads", "Comando"],
        rows=rows,
        ts=summary["ts"],
    )

def _filter_none_procs(cols, procs):
    """Devuelve un dict nuevo solo con los procesos que tienen valor (no None)
    en todas las columnas de interés.
    """
    return {
        pid: proc
        for pid, proc in procs.items()
        if all(proc[col] is not None for col in cols)
    }


def view_memory(data: dict) -> ViewTable:
    """Vista Memoria: una fila por proceso con información de memoria: VM size, RSS, HWM, Data, Stack, Exe, Lib y Swap.
    La dimensión base es `memory`: un proceso sin entrada ahí no tiene fila. Todo esta expresado en kB
    """
    summary = data.get("summary", _EMPTY_DIM)
    memory_data = data.get("memory", _EMPTY_DIM)
    keys = [key for key, _ in _MEMORY_COLUMNS]
    labels = [label for _, label in _MEMORY_COLUMNS]

    filtered_memory_data = _filter_none_procs(keys, memory_data["data"])
    rows = []
    for pid in sorted(filtered_memory_data):
        proc = summary["data"].get(pid, None)
        mem = memory_data["data"].get(pid)
        rows.append([
            pid,
            * (mem[key] for key in keys),
            proc["name"] if proc else None,
        ])

    return ViewTable(
        title="Memoria",
        columns=["PID"] + labels + ["Comando"],
        rows=rows,
        ts=memory_data["ts"],
    )
