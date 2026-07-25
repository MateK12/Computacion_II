
from abc import ABC, abstractmethod

from .models import ViewTable


class IRenderer(ABC):
    """Ciclo de vida de un renderer: start() una vez, render() por frame,
    stop() al bajar. render() dibuja el frame COMPLETO
    """

    @abstractmethod
    def start(self) -> None:
        """Prepara la pantalla (entrar al modo TUI, ocultar cursor, etc.)."""

    @abstractmethod
    def render(self, view: ViewTable) -> None:
        """Dibuja un frame completo a partir de la vista."""

    @abstractmethod
    def stop(self) -> None:
        """Restaura la terminal al estado previo a start()."""
