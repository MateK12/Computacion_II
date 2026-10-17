import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status

from src.models import (
    EstadisticasResponse,
    EstadoTarea,
    TareaCreate,
    TareaResponse,
    TipoTarea,
)
from src.pool import detener_workers, iniciar_workers

# Estado global en memoria para las tareas (Single Source of Truth)
tareas: dict[UUID, TareaResponse] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """En el inicio (antes del yield) se crea y guarda la cola y se guarda el dict global con tareas"""
    n_workers = int(os.getenv("N_WORKERS", "3")) 
    #se usa una variable de entorno porque univcorn 
    #nos genera problema para pasar flags
    cola: asyncio.Queue[UUID] = asyncio.Queue()

    app.state.cola = cola
    app.state.tareas = tareas

    workers = iniciar_workers(
        n_workers=n_workers, cola=cola, tareas=app.state.tareas
    )
    app.state.workers = workers

    try:#sin este try cualquier error abortaria la corrutina en el yield, sin poderse ejecutar el finally
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


def get_tareas(request: Request) -> dict[UUID, TareaResponse]:
    """Dependencia para inyectar el diccionario de tareas en memoria."""
    return getattr(request.app.state, "tareas", tareas)


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
    tareas_db: dict[UUID, TareaResponse] = Depends(get_tareas),
) -> TareaResponse:
    tarea = TareaResponse(
        tipo=TipoTarea(tarea_in.tipo),
        parametros=tarea_in.model_dump(exclude={"tipo"}),
        estado=EstadoTarea.PENDIENTE,
    )
    tareas_db[tarea.id] = tarea
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
    tareas_db: dict[UUID, TareaResponse] = Depends(get_tareas),
) -> list[TareaResponse]:
    if estado is not None:
        return [t for t in tareas_db.values() if t.estado == estado]
    return list(tareas_db.values())


@app.get(
    "/tareas/{tarea_id}",
    response_model=TareaResponse,
    summary="Obtener detalle de una tarea por ID",
)
async def obtener_tarea(
    tarea_id: UUID,
    tareas_db: dict[UUID, TareaResponse] = Depends(get_tareas),
) -> TareaResponse:
    tarea = tareas_db.get(tarea_id)
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
    tareas_db: dict[UUID, TareaResponse] = Depends(get_tareas),
) -> EstadisticasResponse:
    total = len(tareas_db)
    pendientes = sum(
        1 for t in tareas_db.values() if t.estado == EstadoTarea.PENDIENTE
    )
    ejecutando = sum(
        1 for t in tareas_db.values() if t.estado == EstadoTarea.EJECUTANDO
    )
    completadas = sum(
        1 for t in tareas_db.values() if t.estado == EstadoTarea.COMPLETADA
    )
    fallidas = sum(
        1 for t in tareas_db.values() if t.estado == EstadoTarea.FALLIDA
    )
    canceladas = sum(
        1 for t in tareas_db.values() if t.estado == EstadoTarea.CANCELADA
    )

    duraciones = [
        t.duracion_segundos
        for t in tareas_db.values()
        if t.duracion_segundos is not None
    ]
    tiempo_promedio = (
        round(sum(duraciones) / len(duraciones), 4) if duraciones else 0.0
    )

    return EstadisticasResponse(
        total=total,
        pendientes=pendientes,
        ejecutando=ejecutando,
        completadas=completadas,
        fallidas=fallidas,
        canceladas=canceladas,
        tiempo_promedio_ejecucion_segundos=tiempo_promedio,
    )
