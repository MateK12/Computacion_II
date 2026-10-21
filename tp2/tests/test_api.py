import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app, tareas
from src.models import EstadoTarea


@pytest.fixture(autouse=True) #indica que esto se ejecuta antes y despues de cada test
def limpiar_tareas():
    tareas.clear()
    yield # el yield permite hacer la division entre setUp y tearDown
    tareas.clear()


@pytest.mark.asyncio #este tests se ejecuta como una corrutina de asyncio
async def test_crear_tarea_retorna_202_y_estado_pendiente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "tipo": "esperar",
            "segundos": 2.5,
        }
        response = await client.post("/tareas", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["tipo"] == "esperar"
        assert data["estado"] == EstadoTarea.PENDIENTE
        assert data["parametros"]["segundos"] == 2.5
        assert "id" in data
        assert data["creada_en"] is not None
        assert data["iniciada_en"] is None
        assert data["finalizada_en"] is None


@pytest.mark.asyncio
async def test_crear_tarea_payload_invalido_retorna_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Falta campo obligatorio 'segundos' para tipo 'esperar'
        response = await client.post("/tareas", json={"tipo": "esperar"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_listar_tareas_y_filtrar_por_estado():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/tareas", json={"tipo": "esperar", "segundos": 1.0})
        await client.post(
            "/tareas",
            json={
                "tipo": "descargar",
                "urls": ["https://example.com"],
            },
        )

        response = await client.get("/tareas")
        assert response.status_code == 200
        assert len(response.json()) == 2

        response_filtro = await client.get("/tareas?estado=pendiente")
        assert response_filtro.status_code == 200
        assert len(response_filtro.json()) == 2

        response_filtro_vacio = await client.get("/tareas?estado=completada")
        assert response_filtro_vacio.status_code == 200
        assert len(response_filtro_vacio.json()) == 0


@pytest.mark.asyncio
async def test_obtener_tarea_por_id_existente_e_inexistente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/tareas", json={"tipo": "esperar", "segundos": 1.0}
        )
        tarea_id = create_resp.json()["id"]

        get_resp = await client.get(f"/tareas/{tarea_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == tarea_id

        not_found = await client.get(
            "/tareas/00000000-0000-0000-0000-000000000000"
        )
        assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_obtener_estadisticas():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/tareas", json={"tipo": "esperar", "segundos": 1.0})
        await client.post(
            "/tareas",
            json={
                "tipo": "hashear",
                "texto": "hola",
                "iteraciones": 1000,
            },
        )

        resp = await client.get("/estadisticas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["pendientes"] == 2
        assert data["ejecutando"] == 0
        assert data["completadas"] == 0
        assert data["tiempo_promedio_ejecucion_segundos"] == 0.0


@pytest.mark.asyncio
async def test_cancelar_tarea_inexistente_retorna_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            "/tareas/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404
        assert "no encontrada" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cancelar_tarea_pendiente_retorna_200():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        post_resp = await client.post(
            "/tareas", json={"tipo": "esperar", "segundos": 1.0}
        )
        tarea_id = post_resp.json()["id"]

        del_resp = await client.delete(f"/tareas/{tarea_id}")
        assert del_resp.status_code == 200
        data = del_resp.json()
        assert data["id"] == tarea_id
        assert data["estado"] == EstadoTarea.CANCELADA
        assert data["finalizada_en"] is not None

        # Reintentar cancelar una tarea ya cancelada da 400
        del_again = await client.delete(f"/tareas/{tarea_id}")
        assert del_again.status_code == 400
        assert "no puede ser cancelada" in del_again.json()["detail"]


@pytest.mark.asyncio
async def test_cancelar_tarea_ejecutando_cancela_runner():
    import asyncio
    from uuid import UUID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        post_resp = await client.post(
            "/tareas", json={"tipo": "esperar", "segundos": 5.0}
        )
        tarea_id = UUID(post_resp.json()["id"])

        # Simulamos que un worker la tomó y registró su runner
        tarea = tareas.obtener(tarea_id)
        assert tarea is not None
        tarea.estado = EstadoTarea.EJECUTANDO

        async def corrutina_larga():
            await asyncio.sleep(10)

        runner = asyncio.create_task(corrutina_larga())
        tareas.registrar_runner(tarea_id, runner)

        try:
            del_resp = await client.delete(f"/tareas/{tarea_id}")
            assert del_resp.status_code == 200
            assert del_resp.json()["estado"] == EstadoTarea.CANCELADA
            assert runner.cancelling() > 0 or runner.cancelled()
        finally:
            if not runner.done():
                runner.cancel()
            try:
                await runner
            except asyncio.CancelledError:
                pass
