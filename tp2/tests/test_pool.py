import asyncio
from typing import Any
from uuid import UUID

import pytest

from src.models import EstadoTarea, TareaResponse, TipoTarea
from src.pool import detener_workers, iniciar_workers
from src.tasks import REGISTRO_ESTRATEGIAS, registrar_estrategia
from src.tasks.base import TareaStrategy


class MockEsperarStrategy(TareaStrategy):
    async def ejecutar(self, parametros: dict[str, Any]) -> Any:
        await asyncio.sleep(0.05)
        return {"mensaje": "espera completada"}


class MockFallaStrategy(TareaStrategy):
    async def ejecutar(self, parametros: dict[str, Any]) -> Any:
        raise ValueError("Error forzado para pruebas")


@pytest.fixture(autouse=True)
def restaurar_estrategias():
    copia = dict(REGISTRO_ESTRATEGIAS)
    yield
    REGISTRO_ESTRATEGIAS.clear()
    REGISTRO_ESTRATEGIAS.update(copia)


@pytest.mark.asyncio
async def test_worker_procesa_tarea_exitosamente():
    registrar_estrategia(TipoTarea.ESPERAR, MockEsperarStrategy())

    cola: asyncio.Queue[UUID] = asyncio.Queue()
    tareas: dict[UUID, TareaResponse] = {}

    tarea = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 0.05},
        estado=EstadoTarea.PENDIENTE,
    )
    tareas[tarea.id] = tarea
    await cola.put(tarea.id)

    workers = iniciar_workers(n_workers=2, cola=cola, tareas=tareas)

    # Esperamos que la cola se vacíe y se llame task_done()
    await cola.join()

    assert tarea.estado == EstadoTarea.COMPLETADA
    assert tarea.resultado == {"mensaje": "espera completada"}
    assert tarea.iniciada_en is not None
    assert tarea.finalizada_en is not None
    assert tarea.duracion_segundos is not None
    assert tarea.duracion_segundos >= 0.04

    await detener_workers(workers)


@pytest.mark.asyncio
async def test_worker_captura_excepcion_y_marca_fallida():
    registrar_estrategia(TipoTarea.ESPERAR, MockFallaStrategy())

    cola: asyncio.Queue[UUID] = asyncio.Queue()
    tareas: dict[UUID, TareaResponse] = {}

    tarea = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 0.1},
        estado=EstadoTarea.PENDIENTE,
    )
    tareas[tarea.id] = tarea
    await cola.put(tarea.id)

    workers = iniciar_workers(n_workers=1, cola=cola, tareas=tareas)
    await cola.join()

    assert tarea.estado == EstadoTarea.FALLIDA
    assert "Error forzado para pruebas" in (tarea.error or "")
    assert tarea.iniciada_en is not None
    assert tarea.finalizada_en is not None

    await detener_workers(workers)


@pytest.mark.asyncio
async def test_worker_ignora_tarea_previamente_cancelada():
    registrar_estrategia(TipoTarea.ESPERAR, MockEsperarStrategy())

    cola: asyncio.Queue[UUID] = asyncio.Queue()
    tareas: dict[UUID, TareaResponse] = {}

    tarea = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 0.1},
        estado=EstadoTarea.CANCELADA,
    )
    tareas[tarea.id] = tarea
    await cola.put(tarea.id)

    workers = iniciar_workers(n_workers=1, cola=cola, tareas=tareas)
    await cola.join()

    # El worker debió saltear la ejecución
    assert tarea.estado == EstadoTarea.CANCELADA
    assert tarea.iniciada_en is None
    assert tarea.resultado is None

    await detener_workers(workers)
