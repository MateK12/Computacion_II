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


def view_summary(data: dict) -> ViewTable:
    """Vista Resumen: una fila por proceso con estado, CPU%, RSS, threads y comando.

    La dimensión base es `summary`: un proceso sin entrada ahí no tiene fila.
    `cpu` y `memory` se cruzan por PID, pero pueden faltar enteras o no tener
    un PID que summary sí tiene (cada analizador corre a su propio ritmo y
    publica lo suyo cuando puede) -> esas celdas quedan en None.
    """
    summary = data.get("summary", _EMPTY_DIM)
    cpu_data = data.get("cpu", _EMPTY_DIM)["data"]
    memory_data = data.get("memory", _EMPTY_DIM)["data"]

    rows = []
    for pid in sorted(summary["data"]):  # orden estable entre frames
        proc = summary["data"][pid]
        mem = memory_data.get(pid)
        rows.append([
            pid,
            proc["state"],
            cpu_data.get(pid),                    # float | None (1er ciclo o ausente)
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
