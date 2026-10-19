import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from src.main import app, manager
from src.models import EstadoTarea
from src.tasks.esperar import EsperarStrategy


@pytest.mark.asyncio
async def test_esperar_strategy_ejecucion_exitosa():
    strategy = EsperarStrategy()
    parametros = {"segundos": 0.05}
    resultado = await strategy.ejecutar(parametros)

    assert resultado["segundos"] == 0.05
    assert "completada exitosamente" in resultado["mensaje"]


@pytest.mark.asyncio
async def test_esperar_strategy_valida_segundos_positivos():
    strategy = EsperarStrategy()
    with pytest.raises(ValidationError):
        await strategy.ejecutar({"segundos": -1.0})

    with pytest.raises(ValidationError):
        await strategy.ejecutar({"segundos": 0.0})


@pytest.mark.asyncio
async def test_esperar_flujo_completo_api_worker(): #test de integración, prueba la API
    """Verifica que la tarea esperar se procese end-to-end con el Lifespan y workers."""
    manager.limpiar()
    async with app.router.lifespan_context(app): #dispara ciclo de vida de fast API (función lifespan)
        transport = ASGITransport(app=app) #configura cliente HTTP, se comunica con server por memoria
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/tareas",
                json={"tipo": "esperar", "segundos": 0.05},
            )
            assert resp.status_code == 202
            tarea_id = resp.json()["id"]

            cola = app.state.cola
            await cola.join()

            get_resp = await client.get(f"/tareas/{tarea_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["estado"] == EstadoTarea.COMPLETADA
            assert data["resultado"]["segundos"] == 0.05
            assert data["duracion_segundos"] is not None
            assert data["duracion_segundos"] >= 0.04
