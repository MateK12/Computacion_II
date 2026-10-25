import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from src.manager import TaskManager, calcular_estadisticas
from src.models import (
    EstadisticasResponse,
    EstadoTarea,
    TareaCreate,
    TareaResponse,
    TipoTarea,
)
from src.persistencia import reportar_volcados_previos
from src.pool import apagar_sistema, iniciar_workers

# Instancia global de TaskManager para persistencia en memoria (Single Source of Truth)
manager = TaskManager()
# Alias tareas para compatibilidad con tests e integraciones existentes
tareas = manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicación: arranque y apagado ordenado."""
    dir_snapshots = os.getenv("SNAPSHOT_DIR", ".")
    reportar_volcados_previos(dir_snapshots)

    n_workers = int(os.getenv("N_WORKERS", "3"))
    cola: asyncio.Queue[UUID] = asyncio.Queue()

    app.state.cola = cola
    app.state.manager = manager
    app.state.tareas = manager

    workers = iniciar_workers(
        n_workers=n_workers, cola=cola, tareas=app.state.tareas
    )
    app.state.workers = workers

    try:
        yield
    finally:
        timeout_gracia = float(os.getenv("SHUTDOWN_TIMEOUT", "5.0"))
        await apagar_sistema(
            workers=workers,
            manager=app.state.manager,
            timeout_gracia=timeout_gracia,
            directorio_snapshot=dir_snapshots,
        )


def get_cola(request: Request) -> asyncio.Queue[UUID]:
    """Dependencia para inyectar la cola de tareas."""
    cola = getattr(request.app.state, "cola", None)
    if cola is None:
        cola = asyncio.Queue()
        request.app.state.cola = cola
    return cola


def get_manager(request: Request) -> TaskManager:
    """Dependencia para inyectar el TaskManager en memoria."""
    return getattr(request.app.state, "manager", manager)


def get_tareas(request: Request) -> TaskManager:
    """Alias de compatibilidad para inyectar el almacén de tareas."""
    return get_manager(request)


app = FastAPI(
    title="Plataforma de Tareas Distribuidas",
    description="API asíncrona para procesamiento distribuido de tareas (Computación II - UM 2026)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post(
    "/tareas",
    response_model=TareaResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear y encolar una nueva tarea",
)
async def crear_tarea(
    tarea_in: TareaCreate,
    cola: asyncio.Queue[UUID] = Depends(get_cola),
    manager_db: TaskManager = Depends(get_manager),
) -> TareaResponse:
    tarea = TareaResponse(
        tipo=TipoTarea(tarea_in.tipo),
        parametros=tarea_in.model_dump(exclude={"tipo"}),
        estado=EstadoTarea.PENDIENTE,
    )
    manager_db.guardar(tarea)
    await cola.put(tarea.id)
    return tarea


@app.get(
    "/tareas",
    response_model=list[TareaResponse],
    summary="Listar tareas registradas",
)
async def listar_tareas(
    estado: EstadoTarea | None = Query(
        default=None, description="Filtrar por estado de la tarea"
    ),
    manager_db: TaskManager = Depends(get_manager),
) -> list[TareaResponse]:
    return manager_db.listar(estado=estado)


@app.get(
    "/tareas/{tarea_id}",
    response_model=TareaResponse,
    summary="Obtener detalle de una tarea por ID",
)
async def obtener_tarea(
    tarea_id: UUID,
    manager_db: TaskManager = Depends(get_manager),
) -> TareaResponse:
    tarea = manager_db.obtener(tarea_id)
    if not tarea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarea con ID {tarea_id} no encontrada",
        )
    return tarea


@app.get(
    "/estadisticas",
    response_model=EstadisticasResponse,
    summary="Obtener métricas y estadísticas del sistema",
)
async def obtener_estadisticas(
    manager_db: TaskManager = Depends(get_manager),
) -> EstadisticasResponse:
    return calcular_estadisticas(manager_db.listar())


def _validar_cancelacion(
    tarea: TareaResponse | None, tarea_id: UUID
) -> dict[str, Any] | None:
    """Valida si una tarea existe y es elegible para ser cancelada."""
    if not tarea:
        return {
            "status": status.HTTP_404_NOT_FOUND,
            "detail": f"Tarea con ID {tarea_id} no encontrada",
        }
    if tarea.estado in {
        EstadoTarea.COMPLETADA,
        EstadoTarea.FALLIDA,
        EstadoTarea.CANCELADA,
    }:
        return {
            "status": status.HTTP_400_BAD_REQUEST,
            "detail": f"La tarea ya se encuentra en estado '{tarea.estado.value}' y no puede ser cancelada",
        }
    return None


@app.delete(
    "/tareas/{tarea_id}",
    response_model=TareaResponse,
    summary="Cancelar una tarea pendiente o en ejecución",
)
async def cancelar_tarea(
    tarea_id: UUID,
    manager_db: TaskManager = Depends(get_manager),
) -> TareaResponse:
    tarea = manager_db.obtener(tarea_id)
    error = _validar_cancelacion(tarea, tarea_id)
    if error:
        raise HTTPException(
            status_code=error["status"],
            detail=error["detail"],
        )

    assert tarea is not None
    if tarea.estado == EstadoTarea.PENDIENTE:
        tarea.estado = EstadoTarea.CANCELADA
        tarea.finalizada_en = datetime.now(timezone.utc)
    elif tarea.estado == EstadoTarea.EJECUTANDO:
        runner = manager_db.obtener_runner(tarea_id)
        if runner and not runner.done():
            runner.cancel()
        tarea.estado = EstadoTarea.CANCELADA
        tarea.finalizada_en = datetime.now(timezone.utc)

    return tarea

