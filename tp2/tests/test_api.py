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
