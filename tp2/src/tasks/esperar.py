import asyncio
from typing import Any

from src.models import TareaEsperarCreate
from src.tasks.base import TareaStrategy


class EsperarStrategy(TareaStrategy):
    """Estrategia para suspender la ejecución durante N segundos usando asyncio.sleep."""

    async def ejecutar(self, parametros: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta la suspensión asíncrona cooperativa sin bloquear el event loop."""
        if "tipo" not in parametros:
            parametros = {**parametros, "tipo": "esperar"}
        datos = TareaEsperarCreate.model_validate(parametros)

        await asyncio.sleep(datos.segundos)

        return {
            "segundos": datos.segundos,
            "mensaje": f"Espera de {datos.segundos} segundos completada exitosamente",
        }
