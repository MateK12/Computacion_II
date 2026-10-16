from abc import ABC, abstractmethod
from typing import Any


class TareaStrategy(ABC):
    """Interfaz base para las estrategias de ejecución de tareas."""

    @abstractmethod
    async def ejecutar(self, parametros: dict[str, Any]) -> Any:
        """Parsea los parámetros a su modelo Pydantic y ejecuta la tarea asíncronamente."""
        pass
