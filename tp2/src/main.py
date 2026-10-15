from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, status

from src.models import (
    EstadisticasResponse,
    EstadoTarea,
    TareaCreate,
    TareaResponse,
    TipoTarea,
)

app = FastAPI(
    title="Plataforma de Tareas Distribuidas",
    description="API asíncrona para procesamiento distribuido de tareas (Computación II - UM 2026)",
    version="0.1.0",
)

# Estado global en memoria para las tareas
tareas: dict[UUID, TareaResponse] = {}


@app.post(
    "/tareas",
    response_model=TareaResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear y encolar una nueva tarea",
)
async def crear_tarea(tarea_in: TareaCreate) -> TareaResponse:
    tarea = TareaResponse(
        tipo=TipoTarea(tarea_in.tipo),
        parametros=tarea_in.model_dump(exclude={"tipo"}),
        estado=EstadoTarea.PENDIENTE,
    )
    tareas[tarea.id] = tarea
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
) -> list[TareaResponse]:
    if estado is not None:
        return [t for t in tareas.values() if t.estado == estado]
    return list(tareas.values())


@app.get(
    "/tareas/{tarea_id}",
    response_model=TareaResponse,
    summary="Obtener detalle de una tarea por ID",
)
async def obtener_tarea(tarea_id: UUID) -> TareaResponse:
    tarea = tareas.get(tarea_id)
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
async def obtener_estadisticas() -> EstadisticasResponse:
    total = len(tareas)
    pendientes = sum(
        1 for t in tareas.values() if t.estado == EstadoTarea.PENDIENTE
    )
    ejecutando = sum(
        1 for t in tareas.values() if t.estado == EstadoTarea.EJECUTANDO
    )
    completadas = sum(
        1 for t in tareas.values() if t.estado == EstadoTarea.COMPLETADA
    )
    fallidas = sum(
        1 for t in tareas.values() if t.estado == EstadoTarea.FALLIDA
    )
    canceladas = sum(
        1 for t in tareas.values() if t.estado == EstadoTarea.CANCELADA
    )

    duraciones = [
        t.duracion_segundos
        for t in tareas.values()
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
