import hashlib
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from src.main import app, manager
from src.models import EstadoTarea
from src.tasks.hashear import HashearStrategy, computar_hash_iterativo


def test_computar_hash_iterativo_puro():
    """Verifica que la función pura calcule hashes determinísticos y mida duración."""
    texto = "computacion_2"
    
    # 1 iteración
    esperado_1 = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    res_1 = computar_hash_iterativo(texto, 1)
    assert res_1["hash_final"] == esperado_1
    assert res_1["iteraciones"] == 1
    assert res_1["duracion_segundos"] >= 0.0

    # 3 iteraciones encadenadas
    h1 = hashlib.sha256(texto.encode("utf-8")).digest()
    h2 = hashlib.sha256(h1).digest()
    esperado_3 = hashlib.sha256(h2).hexdigest()
    res_3 = computar_hash_iterativo(texto, 3)
    assert res_3["hash_final"] == esperado_3
    assert res_3["iteraciones"] == 3


@pytest.mark.asyncio
async def test_hashear_strategy_ejecucion_exitosa():
    """Verifica que la estrategia ejecute en el executor y retorne el resultado esperado."""
    strategy = HashearStrategy()
    parametros = {"texto": "hola", "iteraciones": 100}
    resultado = await strategy.ejecutar(parametros)

    assert resultado["texto_original"] == "hola"
    assert resultado["iteraciones"] == 100
    assert isinstance(resultado["hash_final"], str)
    assert len(resultado["hash_final"]) == 64
    assert resultado["duracion_segundos"] >= 0.0


@pytest.mark.asyncio
async def test_hashear_strategy_validacion_parametros():
    """Verifica que no se acepten textos vacíos ni iteraciones no positivas."""
    strategy = HashearStrategy()

    with pytest.raises(ValidationError):
        await strategy.ejecutar({"texto": "", "iteraciones": 10})

    with pytest.raises(ValidationError):
        await strategy.ejecutar({"texto": "hola", "iteraciones": 0})

    with pytest.raises(ValidationError):
        await strategy.ejecutar({"texto": "hola", "iteraciones": -5})


@pytest.mark.asyncio
async def test_hashear_flujo_completo_api_worker():
    """Verifica el flujo end-to-end de una tarea CPU-bound: API -> Cola -> Worker -> Executor."""
    manager.limpiar()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/tareas",
                json={"tipo": "hashear", "texto": "computacion_um", "iteraciones": 500},
            )
            assert resp.status_code == 202
            tarea_id = resp.json()["id"]

            cola = app.state.cola
            await cola.join()

            get_resp = await client.get(f"/tareas/{tarea_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["estado"] == EstadoTarea.COMPLETADA
            assert data["resultado"]["iteraciones"] == 500
            assert len(data["resultado"]["hash_final"]) == 64
            assert data["duracion_segundos"] is not None
