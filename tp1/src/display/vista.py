"""Vistas del display: funciones puras que transforman una copia plana del
snapshot en una tabla lista para renderizar.

Acá no entra rich ni ningún proxy de multiprocessing: dict común -> ViewTable.
El proceso display hace `dict(snapshot)` una vez por frame y nos pasa esa copia;
el renderer recibe el ViewTable y lo dibuja sin saber de qué vista vino.
"""

import signal as _signal

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
# Page faults del último intervalo (deltas que publica AnalyzerMemory). Van en
# una lista aparte porque NO entran al filtro de kthreads: un None acá es
# transitorio (primer ciclo, PID reusado) y no debe sacar la fila — si entraran
# al filtro, el primer frame del monitor mostraría la tabla vacía.
_MEMORY_FAULT_COLUMNS = [
    ("minflt_delta", "MinFlt"),
    ("majflt_delta", "MajFlt"),
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
    """Vista Memoria: una fila por proceso con información de memoria: VM size, RSS, HWM, Data, Stack, Exe, Lib y Swap,
    más los page faults (minor/major) del último intervalo.
    La dimensión base es `memory`: un proceso sin entrada ahí no tiene fila. Todo esta expresado en kB
    """
    summary = data.get("summary", _EMPTY_DIM)
    memory_data = data.get("memory", _EMPTY_DIM)
    keys = [key for key, _ in _MEMORY_COLUMNS]
    fault_keys = [key for key, _ in _MEMORY_FAULT_COLUMNS]
    labels = [label for _, label in _MEMORY_COLUMNS + _MEMORY_FAULT_COLUMNS]

    # el filtro mira SOLO las vm_* (None estructural = kthread); los *_delta
    # en None son transitorios y la fila se muestra igual
    filtered_memory_data = _filter_none_procs(keys, memory_data["data"])
    rows = []
    for pid in sorted(filtered_memory_data):
        proc = summary["data"].get(pid, None)
        mem = memory_data["data"].get(pid)
        rows.append([
            pid,
            * (mem[key] for key in keys),
            * (mem[key] for key in fault_keys),
            proc["name"] if proc else None,
        ])

    return ViewTable(
        title="Memoria",
        columns=["PID"] + labels + ["Comando"],
        rows=rows,
        ts=memory_data["ts"],
    )

# Tipos que clasifica AnalyzerFileDescriptor; lo que no matchea acá cae en "Otros".
_FD_TYPE_COLUMNS = [
    ("file", "File"),
    ("socket", "Sock"),
    ("pipe", "Pipe"),
    ("anon_inode", "Anon"),
]
# Cuántos FDs entran en la columna de muestra (los de numeración más baja:
# 0/1/2 suelen ser stdin/stdout/stderr y dicen mucho del proceso).
_FD_SAMPLE_SIZE = 2


def _fmt_fd_sample(fds: dict) -> str:
    """Muestra de los FDs más bajos con su destino: '0:/dev/pts/1, 1:pipe:[123]'.
    Sin FDs -> '' (kthreads y procesos ajenos sin permiso de lectura)."""
    sample = sorted(fds)[:_FD_SAMPLE_SIZE]
    return ", ".join(f"{fd}:{fds[fd]['dest']}" for fd in sample)


def view_fds(data: dict) -> ViewTable:
    """Vista File Descriptors: una fila por proceso con el total de FDs abiertos,
    el conteo por tipo y una muestra de los FDs más bajos con sus destinos.
    La dimensión base es `fds`: un proceso sin entrada ahí no tiene fila.
    (El detalle completo por proceso queda para cuando haya selección por teclado.)
    """
    summary = data.get("summary", _EMPTY_DIM)
    fds_data = data.get("fds", _EMPTY_DIM)
    labels = [label for _, label in _FD_TYPE_COLUMNS]

    rows = []
    for pid in sorted(fds_data["data"]):
        proc = summary["data"].get(pid)
        fds = fds_data["data"][pid]
        types = [fd["type"] for fd in fds.values()]
        counts = [types.count(key) for key, _ in _FD_TYPE_COLUMNS]
        rows.append([
            pid,
            len(fds),
            *counts,
            len(fds) - sum(counts),   # Otros: lo que el analizador marcó unknown
            _fmt_fd_sample(fds),
            proc["name"] if proc else None,
        ])

    return ViewTable(
        title="File Descriptors",
        columns=["PID", "Total"] + labels + ["Otros", "Destinos", "Comando"],
        rows=rows,
        ts=fds_data["ts"],
    )


def view_threads(data: dict) -> ViewTable:
    """Vista Threads: una fila por thread con información de estado, CPU%, y cambios de contexto.
    La dimensión base es `threads`: un thread sin entrada ahí no tiene fila.
    """
    summary = data.get("summary", _EMPTY_DIM)
    threads_data = data.get("threads", _EMPTY_DIM)
    rows = []
    for pid in sorted(threads_data["data"]):
        proc = summary["data"].get(pid, None)
        for tid, thread in sorted(threads_data["data"][pid].items()):
            rows.append([
                pid,
                tid,
                thread["name"],
                thread["state"],
                thread["cpu"],
                thread["ctxt"]["vol"],
                thread["ctxt"]["nonvol"],
                proc["name"] if proc else None,
            ])

    return ViewTable(
        title="Hilos",
        columns=["PID","TID","Nombre","Estado","CPU%","Contextos Vol.","Contextos No Vol.","Comando"],
        rows=rows,
        ts=threads_data["ts"],
    )


_SCHEDULING_COLUMNS = [
    ("policy", "Política"),
    ("nice", "Nice"),
    ("priority", "Prio"),
    ("rt_priority", "PrioRT"),
    ("affinity", "CPUs"),
    ("timeslices", "Timeslices"),
    ("cpu_usage", "CPU%"),
    ("runqueue_wait_pct", "EsperaRQ%"),
]


def view_scheduling(data: dict) -> ViewTable:
    """Vista Scheduling: una fila por proceso con política, prioridades, afinidad
    y los porcentajes de CPU y de espera en runqueue del último intervalo.
    La dimensión base es `scheduling`: un proceso sin entrada ahí no tiene fila.
    """
    summary = data.get("summary", _EMPTY_DIM)
    sched_data = data.get("scheduling", _EMPTY_DIM)
    keys = [key for key, _ in _SCHEDULING_COLUMNS]
    labels = [label for _, label in _SCHEDULING_COLUMNS]

    rows = []
    for pid in sorted(sched_data["data"]):  
        proc = summary["data"].get(pid)
        sched = sched_data["data"][pid]
        rows.append([
            pid,
            * (sched[key] for key in keys),
            proc["name"] if proc else None,
        ])

    return ViewTable(
        title="Scheduling",
        columns=["PID"] + labels + ["Comando"],
        rows=rows,
        ts=sched_data["ts"],
    )


def _signal_name(num: int) -> str:
    """9 -> 'KILL', 15 -> 'TERM'. Los números sin nombre en este kernel quedan como número."""
    try:
        return _signal.Signals(num).name.removeprefix("SIG")
    except ValueError:
        return str(num)


def _fmt_pending(nums: list) -> str:
    """Pendientes: conteo y además cuáles, porque una señal pendiente es lo
    urgente de esta vista. [] -> '0'; [2, 15] -> '2: INT,TERM'."""
    if not nums:
        return "0"
    return f"{len(nums)}: " + ",".join(_signal_name(n) for n in nums)


def view_signals(data: dict) -> ViewTable:
    """Vista Señales: una fila por proceso con el conteo de señales bloqueadas,
    ignoradas y capturadas, y las pendientes (conteo + cuáles).
    La dimensión base es `signals`: un proceso sin entrada ahí no tiene fila.
    """
    summary = data.get("summary", _EMPTY_DIM)
    signals_data = data.get("signals", _EMPTY_DIM)

    rows = []
    for pid in sorted(signals_data["data"]):  # orden estable entre frames
        proc = summary["data"].get(pid)
        sig = signals_data["data"][pid]
        rows.append([
            pid,
            len(sig["blocked"]),
            len(sig["ignored"]),
            len(sig["caught"]),
            _fmt_pending(sig["pending_thread"]),
            _fmt_pending(sig["pending_shared"]),
            proc["name"] if proc else None,
        ])

    return ViewTable(
        title="Señales",
        columns=["PID", "Bloqueadas", "Ignoradas", "Capturadas", "Pend(thr)", "Pend(shr)", "Comando"],
        rows=rows,
        ts=signals_data["ts"],
    )
