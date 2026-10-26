import asyncio
from concurrent.futures import ProcessPoolExecutor
import hashlib
import time
from typing import Any

from src.models import TareaHashearCreate
from src.tasks.base import TareaStrategy

_default_executor: ProcessPoolExecutor | None = None


def obtener_executor() -> ProcessPoolExecutor:
    """Retorna una instancia compartida de ProcessPoolExecutor (Single Source of Truth para CPU-bound)."""
    global _default_executor
    if _default_executor is None:
        _default_executor = ProcessPoolExecutor()
    return _default_executor


def computar_hash_iterativo(texto: str, iteraciones: int) -> dict[str, Any]:
    """Calcula hashes SHA-256 iterativamente en un proceso separado del SO.
    
    Esta función es pura y top-level para ser serializable por pickle en IPC.
    """
    inicio = time.perf_counter()
    actual = hashlib.sha256(texto.encode("utf-8")).digest()
    for _ in range(iteraciones - 1):
        actual = hashlib.sha256(actual).digest()

    duracion = round(time.perf_counter() - inicio, 4)
    return {
        "texto_original": texto,
        "iteraciones": iteraciones,
        "hash_final": actual.hex(),
        "duracion_segundos": duracion,
    }


class HashearStrategy(TareaStrategy):
    """Estrategia para ejecutar hashing iterativo SHA-256 en un ProcessPoolExecutor."""

    def __init__(self, executor: ProcessPoolExecutor | None = None) -> None:
        self._executor = executor

    async def ejecutar(self, parametros: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta el cómputo CPU-bound en el executor sin congelar el event loop (o en loop si usar_executor=False)."""
        if "tipo" not in parametros:
            parametros = {**parametros, "tipo": "hashear"}
        datos = TareaHashearCreate.model_validate(parametros)

        if not datos.usar_executor:
            return computar_hash_iterativo(datos.texto, datos.iteraciones)

        executor = self._executor or obtener_executor()
        loop = asyncio.get_running_loop()
        resultado = await loop.run_in_executor(
            executor,
            computar_hash_iterativo,
            datos.texto,
            datos.iteraciones,
        )
        return resultado
