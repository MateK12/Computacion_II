
from .models import ViewTable
from .renderer import IRenderer
from .vista import (
    view_summary,
    view_memory,
    view_fds,
    view_threads,
    view_signals,
    view_scheduling,
    view_sistema,
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
]


def _on_sigterm(signum, frame):
    """Handler de SIGTERM: solo levanta SystemExit para que la limpieza
    corra en el flujo normal (async-signal-safe: acá no se toca ningún objeto).
    """
    sys.exit(0)


class Display:
    """Clase que representa la interfaz de usuario del analizador. Se encarga de
    mostrar la información en pantalla y de recibir la entrada del usuario.
    """

    def __init__(self, renderer: IRenderer, snapshot, active_view):
        self.renderer = renderer
        self._snapshot = snapshot  # copia plana del snapshot
        self._active_view = active_view  # mp.Value('i'): índice de la vista activa en VIEWS

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
                # Un solo escritor (main) y lectura de un int: no hace falta get_lock()
                view = VIEWS[self._active_view.value]
                self._render(view(snapshot))
                time.sleep(1)
        finally: #corre en systemExit
            self.stop()
