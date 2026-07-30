
import time

from rich.live import Live
from rich.table import Table

from .models import ViewTable
from .renderer import IRenderer

_NO_DATA = "—"


class RichRenderer(IRenderer):
    """Clase que implementa IRenderer usando rich. Cada frame construye una Table NUEVA"""

    def __init__(self, refresh_per_second: int = 4):
        self._live = Live(refresh_per_second=refresh_per_second)

    def start(self) -> None:
        self._live.start()

    def render(self, view: ViewTable) -> None:
        self._live.update(self._build_table(view))

    def stop(self) -> None:
        self._live.stop()

    @staticmethod
    def _build_table(view: ViewTable) -> Table:
        if view.ts is None:
            subtitle = "esperando datos…"
        else:
            subtitle = time.strftime("%H:%M:%S", time.localtime(view.ts))

        table = Table(title=f"{view.title} — {subtitle}")
        for column in view.columns:
            table.add_column(column)
        for i, row in enumerate(view.rows):
            table.add_row(
                *(_NO_DATA if cell is None else str(cell) for cell in row),
                style="reverse" if i == view.selected else None,
            )
        return table
