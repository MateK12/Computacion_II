import asyncio
from typing import Any
import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app, manager
from src.models import EstadoTarea, TipoTarea
from src.tasks.descargar import DescargarStrategy


def mock_http_handler(request: httpx.Request) -> httpx.Response:
    url_str = str(request.url)
    if "fallo" in url_str:
        raise httpx.ConnectError("Error de conexion simulado")
    if "lento" in url_str:
        return httpx.Response(200, content=b"12345")
    return httpx.Response(200, content=b"Hola Mundo", text="Hola Mundo")


@pytest.fixture
def mock_httpx_client(monkeypatch: pytest.MonkeyPatch):
    """Reemplaza httpx.AsyncClient para redirigir peticiones a mock_http_handler."""
    transport = httpx.MockTransport(mock_http_handler)
    original_client = httpx.AsyncClient

    def _client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)


@pytest.mark.asyncio
async def test_descargar_strategy_exitosas(mock_httpx_client: None):
    strategy = DescargarStrategy()
    parametros = {
        "urls": [
            "https://test.com/pagina1",
            "https://test.com/pagina2",
        ]
    }
    resultado = await strategy.ejecutar(parametros)

    assert resultado["total_urls"] == 2
    assert resultado["exitosas"] == 2
    assert resultado["fallidas"] == 0

    detalles = resultado["resultados"]
    assert len(detalles) == 2
    for r in detalles:
        assert r["status_code"] == 200
        assert r["tamano_bytes"] == len(b"Hola Mundo")
        assert r["duracion_segundos"] >= 0.0
        assert r["error"] is None


@pytest.mark.asyncio
async def test_descargar_strategy_manejo_de_errores_individuales(
    mock_httpx_client: None,
):
    strategy = DescargarStrategy()
    parametros = {
        "urls": [
            "https://test.com/buena",
            "https://test.com/fallo",
        ]
    }
    resultado = await strategy.ejecutar(parametros)

    assert resultado["total_urls"] == 2
    assert resultado["exitosas"] == 1
    assert resultado["fallidas"] == 1

    buena = next(r for r in resultado["resultados"] if r["url"] == "https://test.com/buena")
    assert buena["status_code"] == 200
    assert buena["error"] is None

    mala = next(r for r in resultado["resultados"] if r["url"] == "https://test.com/fallo")
    assert mala["status_code"] is None
    assert mala["tamano_bytes"] == 0
    assert "Error de conexion simulado" in mala["error"]


@pytest.mark.asyncio
async def test_descargar_flujo_completo_api_worker(mock_httpx_client: None):
    """Verifica que la tarea descargar funcione end-to-end en la API con el Lifespan."""
    manager.limpiar()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/tareas",
                json={
                    "tipo": "descargar",
                    "urls": ["https://test.com/doc1", "https://test.com/doc2"],
                },
            )
            assert resp.status_code == 202
            tarea_id = resp.json()["id"]

            cola = app.state.cola
            await cola.join()

            get_resp = await client.get(f"/tareas/{tarea_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["estado"] == EstadoTarea.COMPLETADA
            assert data["resultado"]["exitosas"] == 2
            assert data["resultado"]["total_urls"] == 2
