
from dataclasses import replace

from .models import ViewTable
from .renderer import IRenderer
from .formatters import parse_kb
from .vista import (
    view_summary,
    view_memory,
    view_fds,
    view_threads,
    view_signals,
    view_scheduling,
    view_sistema,
    view_help,
)
import signal
import sys
import time

# Contrato del índice de vista activa: la posición N de esta lista es lo que
# significa active_view == N. El orden es el de la tabla de la consigna
# (teclas 1..7); main traduce tecla -> índice contra este mismo orden.
VIEWS = [
    view_summary,
    view_memory,
    view_fds,
    view_threads,
    view_signals,
    view_scheduling,
    view_sistema,
    view_help,     # índice 7 (sin tecla numérica: se llega con 'h' / '?')
]


# Contrato del modo de orden (tecla 'c'): main cicla 0→1→2→0 y acá se define
# qué significa cada modo. Cada entrada dice qué etiquetas de columna busca en
# el ViewTable y cómo convertir la celda a un número comparable. El modo 0 es
# el orden natural de las vistas (PID), por eso no reordena nada.
_SORT_MODES = [
    None,
    ("CPU%", ("CPU%",), None),
    ("RSS", ("RSS", "VmRSS"), parse_kb),
]


def _sorted_view(view: ViewTable, mode: int) -> ViewTable:
    """Copia del ViewTable con las filas reordenadas según el modo global.
    Es presentación, así que las vistas no se enteran: si la vista no tiene la
    columna del modo, se muestra tal cual vino. Descendente, None al final.
    """
    spec = _SORT_MODES[mode]
    if spec is None:
        return view
    name, labels, to_number = spec
    col = next((view.columns.index(l) for l in labels if l in view.columns), None)
    if col is None:
        return view

    def key(row):
        value = to_number(row[col]) if to_number else row[col]
        if not isinstance(value, (int, float)):
            return (True, 0.0)  # None (o basura) al final
        return (False, -value)

    return replace(view, rows=sorted(view.rows, key=key), title=f"{view.title} ↓{name}")


def _on_sigterm(signum, frame):
    """Handler de SIGTERM: solo levanta SystemExit para que la limpieza
    corra en el flujo normal (async-signal-safe: acá no se toca ningún objeto).
    """
    sys.exit(0)


class Display:
    """Clase que representa la interfaz de usuario del analizador. Se encarga de
    mostrar la información en pantalla y de recibir la entrada del usuario.
    """

    def __init__(self, renderer: IRenderer, snapshot, active_view, sort_mode):
        self.renderer = renderer
        self._snapshot = snapshot  # copia plana del snapshot
        self._active_view = active_view  # mp.Value('i'): índice de la vista activa en VIEWS
        self._sort_mode = sort_mode  # mp.Value('i'): índice en _SORT_MODES

    def _start(self):
        self.renderer.start()

    def stop(self):
        self.renderer.stop()

    def _render(self, view: ViewTable):
        self.renderer.render(view)

    def run_display(self):
        """Método que se encarga de iniciar el renderer, renderizar la vista y detener el renderer."""
        signal.signal(signal.SIGTERM, _on_sigterm)
        self._start()
        try:
            while True:
                snapshot = dict(self._snapshot)
                
                view = VIEWS[self._active_view.value]
                self._render(_sorted_view(view(snapshot), self._sort_mode.value))
                time.sleep(1)
        finally: #corre en systemExit
            self.stop()
