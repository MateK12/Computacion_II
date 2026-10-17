import asyncio
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app, tareas
from src.models import EstadoTarea, TipoTarea
from src.tasks import REGISTRO_ESTRATEGIAS, registrar_estrategia
from src.tasks.base import TareaStrategy


class MockEsperarStrategy(TareaStrategy):
    async def ejecutar(self, parametros: dict[str, Any]) -> Any:
        await asyncio.sleep(0.01)
        return {"mensaje": "espera mock completada"}


class MockErrorStrategy(TareaStrategy):
    async def ejecutar(self, parametros: dict[str, Any]) -> Any:
        raise RuntimeError("Falla simulada en worker")


@pytest.fixture(autouse=True)
def restaurar_estado():
    tareas.clear()
    estrategias_backup = dict(REGISTRO_ESTRATEGIAS)
    yield
    tareas.clear()
    REGISTRO_ESTRATEGIAS.clear()
    REGISTRO_ESTRATEGIAS.update(estrategias_backup)


@pytest.mark.asyncio
async def test_ciclo_completo_lifespan_api_cola_worker():
    """Verifica el flujo end-to-end: API -> Cola -> Worker -> Completada dentro del lifespan."""
    registrar_estrategia(TipoTarea.ESPERAR, MockEsperarStrategy())

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # 1. Enviar la tarea a la API
            post_resp = await client.post(
                "/tareas",
                json={"tipo": "esperar", "segundos": 0.01},
            )
            assert post_resp.status_code == 202
            tarea_id = post_resp.json()["id"]
            assert post_resp.json()["estado"] == EstadoTarea.PENDIENTE

            # 2. Esperar determinísticamente a que el worker la procese
            cola = app.state.cola
            await cola.join()

            # 3. Consultar el estado final a través del endpoint GET
            get_resp = await client.get(f"/tareas/{tarea_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["estado"] == EstadoTarea.COMPLETADA
            assert data["resultado"] == {"mensaje": "espera mock completada"}
            assert data["iniciada_en"] is not None
            assert data["finalizada_en"] is not None


@pytest.mark.asyncio
async def test_lifespan_maneja_tarea_fallida():
    """Verifica que una falla en la estrategia transicione la tarea a FALLIDA."""
    registrar_estrategia(TipoTarea.ESPERAR, MockErrorStrategy())

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            post_resp = await client.post(
                "/tareas",
                json={"tipo": "esperar", "segundos": 0.01},
            )
            assert post_resp.status_code == 202
            tarea_id = post_resp.json()["id"]

            await app.state.cola.join()

            get_resp = await client.get(f"/tareas/{tarea_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["estado"] == EstadoTarea.FALLIDA
            assert "Falla simulada en worker" in (data["error"] or "")


@pytest.mark.asyncio
async def test_lifespan_shutdown_cancela_workers():
    """Verifica que al salir del lifespan_context se cancelen y detengan todos los workers."""
    async with app.router.lifespan_context(app):
        workers = app.state.workers
        assert len(workers) == 3
        # Durante el lifespan, los workers están vivos y esperando tareas
        assert all(not w.done() for w in workers)

    # Una vez finalizado el bloque del lifespan, todos los workers deben estar cancelados/finalizados
    assert all(w.done() for w in workers)
