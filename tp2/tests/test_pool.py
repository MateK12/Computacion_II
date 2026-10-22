import asyncio
from typing import Any
from uuid import UUID

import pytest

from src.manager import TaskManager
from src.models import EstadoTarea, TareaResponse, TipoTarea
from src.pool import apagar_sistema, detener_workers, iniciar_workers
from src.tasks import REGISTRO_ESTRATEGIAS, registrar_estrategia
from src.tasks.base import TareaStrategy


class MockEsperarStrategy(TareaStrategy):
    async def ejecutar(self, parametros: dict[str, Any]) -> Any:
        await asyncio.sleep(0.05)
        return {"mensaje": "espera completada"}


class MockFallaStrategy(TareaStrategy):
    async def ejecutar(self, parametros: dict[str, Any]) -> Any:
        raise ValueError("Error forzado para pruebas")


class MockLentaStrategy(TareaStrategy):
    async def ejecutar(self, parametros: dict[str, Any]) -> Any:
        await asyncio.sleep(2.0)
        return {"mensaje": "completada tarde"}


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


@pytest.mark.asyncio
async def test_worker_cancela_runner_y_continua_vivo():
    registrar_estrategia(TipoTarea.ESPERAR, MockLentaStrategy())
    registrar_estrategia(TipoTarea.HASHEAR, MockEsperarStrategy())

    cola: asyncio.Queue[UUID] = asyncio.Queue()
    manager = TaskManager()

    t1 = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 2.0},
        estado=EstadoTarea.PENDIENTE,
    )
    t2 = TareaResponse(
        tipo=TipoTarea.HASHEAR,
        parametros={"texto": "abc"},
        estado=EstadoTarea.PENDIENTE,
    )
    manager.guardar(t1)
    manager.guardar(t2)

    await cola.put(t1.id)
    await cola.put(t2.id)

    workers = iniciar_workers(n_workers=1, cola=cola, tareas=manager)

    # Esperamos a que t1 pase a EJECUTANDO y tenga un runner
    for _ in range(50):
        if t1.estado == EstadoTarea.EJECUTANDO and manager.obtener_runner(t1.id):
            break
        await asyncio.sleep(0.01)

    runner = manager.obtener_runner(t1.id)
    assert runner is not None
    runner.cancel()

    await cola.join()

    # t1 debe quedar cancelada y desregistrada
    assert t1.estado == EstadoTarea.CANCELADA
    assert manager.obtener_runner(t1.id) is None

    # t2 debe haberse completado (prueba que el worker no murió con la cancelación de t1)
    assert t2.estado == EstadoTarea.COMPLETADA
    assert t2.resultado == {"mensaje": "espera completada"}

    await detener_workers(workers)


@pytest.mark.asyncio
async def test_worker_timeout_marca_fallida_y_continua_vivo():
    registrar_estrategia(TipoTarea.ESPERAR, MockLentaStrategy())
    registrar_estrategia(TipoTarea.HASHEAR, MockEsperarStrategy())

    cola: asyncio.Queue[UUID] = asyncio.Queue()
    manager = TaskManager()

    t1 = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"timeout": 0.05},
        estado=EstadoTarea.PENDIENTE,
    )
    t2 = TareaResponse(
        tipo=TipoTarea.HASHEAR,
        parametros={"texto": "abc"},
        estado=EstadoTarea.PENDIENTE,
    )
    manager.guardar(t1)
    manager.guardar(t2)

    await cola.put(t1.id)
    await cola.put(t2.id)

    workers = iniciar_workers(n_workers=1, cola=cola, tareas=manager)
    await cola.join()

    assert t1.estado == EstadoTarea.FALLIDA
    assert "Tiempo límite de ejecución excedido (0.05s)" in (t1.error or "")
    assert manager.obtener_runner(t1.id) is None

    # El worker siguió con t2
    assert t2.estado == EstadoTarea.COMPLETADA

    await detener_workers(workers)


@pytest.mark.asyncio
async def test_apagar_sistema_cancela_pendientes_y_persiste(tmp_path):
    manager = TaskManager()
    cola: asyncio.Queue[UUID] = asyncio.Queue()

    t_pendiente = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 1.0},
        estado=EstadoTarea.PENDIENTE,
    )
    t_completada = TareaResponse(
        tipo=TipoTarea.HASHEAR,
        parametros={"texto": "abc"},
        estado=EstadoTarea.COMPLETADA,
    )
    manager.guardar(t_pendiente)
    manager.guardar(t_completada)

    workers = iniciar_workers(n_workers=2, cola=cola, tareas=manager)

    archivo = await apagar_sistema(
        workers=workers,
        manager=manager,
        timeout_gracia=0.5,
        directorio_snapshot=tmp_path,
    )

    # 1. Tarea pendiente marcada como cancelada
    assert t_pendiente.estado == EstadoTarea.CANCELADA
    assert "Cancelada por apagado del servidor" in (t_pendiente.error or "")
    assert t_pendiente.finalizada_en is not None

    # 2. Workers detenidos
    assert all(w.done() for w in workers)

    # 3. Snapshot creado en tmp_path
    assert archivo.exists()
    assert archivo.parent == tmp_path


@pytest.mark.asyncio
async def test_apagar_sistema_espera_runners_y_cancela_excedidos(tmp_path):
    class RapidaStrategy(TareaStrategy):
        async def ejecutar(self, parametros: dict[str, Any]) -> Any:
            await asyncio.sleep(0.02)
            return "rapida ok"

    class EternaStrategy(TareaStrategy):
        async def ejecutar(self, parametros: dict[str, Any]) -> Any:
            await asyncio.sleep(10.0)
            return "no deberia llegar"

    registrar_estrategia(TipoTarea.ESPERAR, RapidaStrategy())
    registrar_estrategia(TipoTarea.HASHEAR, EternaStrategy())

    manager = TaskManager()
    cola: asyncio.Queue[UUID] = asyncio.Queue()

    t_rapida = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 0.02},
        estado=EstadoTarea.PENDIENTE,
    )
    t_lenta = TareaResponse(
        tipo=TipoTarea.HASHEAR,
        parametros={"texto": "lenta"},
        estado=EstadoTarea.PENDIENTE,
    )
    manager.guardar(t_rapida)
    manager.guardar(t_lenta)

    await cola.put(t_rapida.id)
    await cola.put(t_lenta.id)

    workers = iniciar_workers(n_workers=2, cola=cola, tareas=manager)

    # Esperar un instante para que ambos workers tomen las tareas y arranquen los runners
    await asyncio.sleep(0.01)
    assert len(manager.listar_runners()) >= 1

    # Apagar el sistema con gracia de 0.1s (la rápida termina en 0.02s, la lenta no llega)
    await apagar_sistema(
        workers=workers,
        manager=manager,
        timeout_gracia=0.1,
        directorio_snapshot=tmp_path,
    )

    assert t_rapida.estado == EstadoTarea.COMPLETADA
    assert t_rapida.resultado == "rapida ok"

    assert t_lenta.estado == EstadoTarea.CANCELADA
    assert all(w.done() for w in workers)
