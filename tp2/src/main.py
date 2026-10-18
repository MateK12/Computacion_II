import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status

from src.manager import TaskManager, calcular_estadisticas
from src.models import (
    EstadisticasResponse,
    EstadoTarea,
    TareaCreate,
    TareaResponse,
    TipoTarea,
)
from src.pool import detener_workers, iniciar_workers

# Instancia global de TaskManager para persistencia en memoria (Single Source of Truth)
manager = TaskManager()
# Alias tareas para compatibilidad con tests e integraciones existentes
tareas = manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """En el inicio (antes del yield) se crea y guarda la cola y el manager."""
    n_workers = int(os.getenv("N_WORKERS", "3"))
    # Se usa una variable de entorno porque uvicorn genera problemas para pasar flags
    cola: asyncio.Queue[UUID] = asyncio.Queue()

    app.state.cola = cola
    app.state.manager = manager
    app.state.tareas = manager

    workers = iniciar_workers(
        n_workers=n_workers, cola=cola, tareas=app.state.tareas
    )
    app.state.workers = workers

    try:  # Sin este try cualquier error abortaría la corrutina en el yield, sin ejecutarse el finally
        yield
    finally:
        await detener_workers(workers)


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

