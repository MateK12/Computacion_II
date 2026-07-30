"""Estado de UI compartido entre main (dueño del teclado) y el display.

Regla de oro: cada campo tiene UN solo proceso escritor y los demás solo
leen. Por eso ninguno lleva lock: lo peor posible es leer un valor viejo
durante un frame o un tick, y se autocorrige en el siguiente.

main escribe lo que se deriva de las teclas; el display escribe lo que solo
él puede saber (qué tabla hay en pantalla): cuántas filas tiene y qué PID
está bajo el cursor.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UIState:
    active_view: object      # Value('i') — escribe main: índice en display.VIEWS
    sort_mode: object        # Value('i') — escribe main: índice en display._SORT_MODES
    intervals: list          # [Value('d')] — escribe main: intervalo por analizador
    selected_row: object     # Value('i') — escribe main: cursor posicional (fila)
    pinned_pid: object       # Value('i') — escribe main: PID pinneado con Enter (-1 = sin pin)
    pid_at_selected: object  # Value('i') — escribe DISPLAY: PID bajo el cursor (-1 = no hay)
    row_count: object        # Value('i') — escribe DISPLAY: filas de la tabla actual
    filter_mode: object        # Value('i') — escribe main: modo de filtro (0 = comando 1= usuario)
    filter_value: object       # Array('u',128) — escribe main: valor del filtro (comando o usuario)