
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
import shutil
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


def _page_size() -> int:
    """Filas de datos que entran en la terminal actual, descontando el marco
    de la tabla (título, encabezados, bordes)."""
    return max(5, shutil.get_terminal_size().lines - 8)


def _window(selected: int, total: int, page: int) -> tuple:
    """(start, end) de la ventana de `page` filas que mantiene visible la
    selección, centrándola cuando se puede."""
    start = max(0, min(selected - page // 2, total - page))
    return start, start + page


def _apply_selection(view: ViewTable, ui, page: int) -> ViewTable:
    """Resuelve qué fila está seleccionada, publica lo que solo el display
    sabe (row_count y el PID bajo el cursor) y recorta la tabla a una ventana
    alrededor de la selección.

    Con pin activo la selección es identidad (sigue al PID donde esté tras el
    sort); si el PID pinneado murió o no está, cae a la selección posicional.
    Vistas sin columna PID (Sistema, Ayuda) no tienen selección.
    """
    if "PID" not in view.columns or not view.rows:
        ui.row_count.value = 0
        ui.pid_at_selected.value = -1
        return view

    pid_col = view.columns.index("PID")
    ui.row_count.value = len(view.rows)

    selected = None
    pinned = ui.pinned_pid.value
    if pinned != -1:
        selected = next(
            (i for i, row in enumerate(view.rows) if row[pid_col] == pinned), None
        )
    if selected is None:
        # el cursor de main puede apuntar más allá de la tabla actual: clamp
        selected = min(ui.selected_row.value, len(view.rows) - 1)

    ui.pid_at_selected.value = view.rows[selected][pid_col]
    start, end = _window(selected, len(view.rows), page)
    return replace(view, rows=view.rows[start:end], selected=selected - start)


def _inject_filter_prompt(view: ViewTable, ui) -> ViewTable:
    """Si estamos en modo input, agrega un prompt al título de la tabla."""
    mode = ui.filter_mode.value
    if mode == 0:
        return view
    label = "cmd" if mode == 1 else "user"
    text = ui.filter_value.get_obj().value
    prompt = f"filtrar {label}: {text}_"
    return replace(view, title=f"{view.title} | {prompt}")


def _inject_verbose_indicator(view: ViewTable, ui) -> ViewTable:
    """Si el modo verbose está activo, agrega un indicador [V] al título."""
    if ui.verbose_mode.value:
        return replace(view, title=f"{view.title} [V]")
    return view


class Display:
    """Clase que representa la interfaz de usuario del analizador. Se encarga de
    mostrar la información en pantalla y de recibir la entrada del usuario.
    """

    def __init__(self, renderer: IRenderer, snapshot, ui, shutdown_event):
        self.renderer = renderer
        self._snapshot = snapshot  # copia plana del snapshot
        self._ui = ui  # UIState: main escribe las teclas, acá escribimos row_count y pid_at_selected
        self.shutdown_event = shutdown_event

    def _start(self):
        self.renderer.start()

    def stop(self):
        self.renderer.stop()

    def _render(self, view: ViewTable):
        self.renderer.render(view)

    def run_display(self):
        """Método que se encarga de iniciar el renderer, renderizar la vista y detener el renderer."""
        self._start()
        try:
            while not self.shutdown_event.is_set():
                snapshot = dict(self._snapshot)

                view = VIEWS[self._ui.active_view.value]
                mode = self._ui.filter_mode.value
                text = self._ui.filter_value.get_obj().value
                filter_cmd = text if mode == 1 else ""
                filter_user = text if mode == 2 else ""
                verbose = self._ui.verbose_mode.value == 1
                table = _sorted_view(view(snapshot, filter_cmd=filter_cmd, filter_user=filter_user, verbose=verbose), self._ui.sort_mode.value)
                table = _apply_selection(table, self._ui, _page_size())
                table = _inject_filter_prompt(table, self._ui)
                table = _inject_verbose_indicator(table, self._ui)
                self._render(table)
                if self.shutdown_event.wait(1):
                    break
        finally:
            self.stop()
