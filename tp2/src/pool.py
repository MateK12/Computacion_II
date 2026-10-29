import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from src.manager import TaskManager
from src.models import EstadoTarea, TareaResponse
from src.persistencia import guardar_snapshot
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
                runner = asyncio.create_task(
                    estrategia.ejecutar(tarea.parametros),
                    name=f"runner-{tarea_id}",
                )
                if hasattr(tareas, "registrar_runner"):
                    tareas.registrar_runner(tarea.id, runner)

                timeout = tarea.parametros.get("timeout")
                try:
                    if timeout:
                        resultado = await asyncio.wait_for(
                            runner, timeout=float(timeout)
                        )
                    else:
                        resultado = await runner
                    tarea.resultado = resultado
                    tarea.estado = EstadoTarea.COMPLETADA
                except TimeoutError:
                    tarea.estado = EstadoTarea.FALLIDA
                    tarea.error = (
                        f"Tiempo límite de ejecución excedido ({timeout}s)"
                    )
                except asyncio.CancelledError:
                    tarea.estado = EstadoTarea.CANCELADA # Se vuelve a poner como cancelado (evita race condition})
                    current_task = asyncio.current_task()
                    if current_task and current_task.cancelling() > 0:
                        raise
                finally:
                    if hasattr(tareas, "desregistrar_runner"):
                        tareas.desregistrar_runner(tarea.id)
            except asyncio.CancelledError:
                tarea.estado = EstadoTarea.CANCELADA
                current_task = asyncio.current_task()
                if current_task and current_task.cancelling() > 0:
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


async def apagar_sistema(
    workers: list[asyncio.Task[Any]],
    manager: TaskManager,
    timeout_gracia: float = 5.0,
    directorio_snapshot: Path | str = ".",
) -> Path:
    """Orquesta el apagado ordenado del sistema y persiste su estado en disco.

    1. Cancela las tareas pendientes para que los workers no inicien nuevo trabajo.
    2. Espera a los runners activos con un tiempo de gracia; si expiran, los cancela.
    3. Detiene a los workers del pool.
    4. Guarda un snapshot del estado de todas las tareas en un archivo JSON.
    """
    logger.info("Iniciando apagado ordenado (timeout de gracia: %.1fs)...", timeout_gracia)

    # 1. Cancelar tareas pendientes
    pendientes = manager.listar(EstadoTarea.PENDIENTE)
    for t in pendientes:
        t.estado = EstadoTarea.CANCELADA
        t.error = "Cancelada por apagado del servidor"
        t.finalizada_en = datetime.now(timezone.utc)
    if pendientes:
        logger.info("Canceladas %d tarea(s) pendiente(s) en cola", len(pendientes))

    # 2. Esperar runners activos con timeout de gracia
    runners = manager.listar_runners()
    if runners:
        logger.info("Esperando %d runner(s) activo(s)...", len(runners))
        done, pending = await asyncio.wait(runners, timeout=timeout_gracia)
        if pending:
            logger.warning(
                "Timeout de gracia expirado. Cancelando %d runner(s) que no terminaron a tiempo",
                len(pending),
            )
            for r in pending:
                r.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    # 3. Detener a los workers del pool
    await detener_workers(workers)

    # 4. Volcar snapshot a disco
    archivo_snapshot = guardar_snapshot(manager.values(), directorio=directorio_snapshot)
    logger.info("Apagado ordenado finalizado con éxito en %s", archivo_snapshot.name)
    return archivo_snapshot
