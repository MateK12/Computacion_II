import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from src.models import EstadoTarea, TareaResponse
from src.tasks import obtener_estrategia

logger = logging.getLogger(__name__)


async def worker(
    worker_id: int,
    cola: asyncio.Queue[UUID],
    tareas: dict[UUID, TareaResponse],
) -> None:
    """Consume y procesa tareas de la cola de forma secuencial."""
    logger.info("Worker-%d iniciado y esperando tareas", worker_id)
    while True:
        tarea_id = await cola.get()
        try:
            tarea = tareas.get(tarea_id)
            if not tarea or tarea.estado == EstadoTarea.CANCELADA:
                continue

            tarea.estado = EstadoTarea.EJECUTANDO
            tarea.iniciada_en = datetime.now(timezone.utc)

            try:
                estrategia = obtener_estrategia(tarea.tipo)
                resultado = await estrategia.ejecutar(tarea.parametros)
                tarea.resultado = resultado
                tarea.estado = EstadoTarea.COMPLETADA
            except asyncio.CancelledError:
                tarea.estado = EstadoTarea.CANCELADA
                raise
            except Exception as exc:
                tarea.estado = EstadoTarea.FALLIDA
                tarea.error = str(exc)
                logger.error(
                    "Error ejecutando tarea %s en Worker-%d: %s",
                    tarea_id,
                    worker_id,
                    exc,
                )
            finally:
                tarea.finalizada_en = datetime.now(timezone.utc)
        finally:
            cola.task_done()


def iniciar_workers(
    n_workers: int,
    cola: asyncio.Queue[UUID],
    tareas: dict[UUID, TareaResponse],
) -> list[asyncio.Task]:
    """Crea y planifica n corrutinas worker en el event loop."""
    return [
        asyncio.create_task(
            worker(i + 1, cola, tareas),
            name=f"worker-{i + 1}",
        )
        for i in range(n_workers)
    ]


async def detener_workers(workers: list[asyncio.Task]) -> None:
    """Cancela todos los workers del pool y espera su finalización limpia."""
    for task in workers:
        task.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
