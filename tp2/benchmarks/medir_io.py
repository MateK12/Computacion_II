"""
Benchmark Medición 1: Concurrencia I/O (Descargas).

Compara la ejecución estrictamente secuencial de 20 descargas HTTP frente a
la ejecución concurrente con asyncio.gather (tarea descargar).
Calcula el Speedup = T_sec / T_conc.
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

# Agregar directorio raíz al PYTHONPATH para importar src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from src.tasks.descargar import DescargarStrategy

URLS = [f"https://jsonplaceholder.typicode.com/posts/{i}" for i in range(1, 21)]


async def medir_secuencial(urls: list[str]) -> tuple[float, list[dict[str, Any]]]:
    """Ejecuta 20 descargas en serie estricta usando una misma sesión de httpx."""
    detalles = []
    inicio = time.perf_counter()
    async with httpx.AsyncClient(timeout=15.0) as client:
        for url in urls:
            t0 = time.perf_counter()
            resp = await client.get(url)
            dt = time.perf_counter() - t0
            detalles.append({
                "url": url,
                "status_code": resp.status_code,
                "duracion_segundos": round(dt, 4),
            })
    duracion_total = time.perf_counter() - inicio
    return duracion_total, detalles


async def medir_concurrente_estrategia(
    urls: list[str],
) -> tuple[float, dict[str, Any]]:
    """Ejecuta las descargas concurrentemente usando DescargarStrategy (asyncio.gather)."""
    estrategia = DescargarStrategy()
    inicio = time.perf_counter()
    resultado = await estrategia.ejecutar({"urls": urls, "timeout": 15.0})
    duracion_total = time.perf_counter() - inicio
    return duracion_total, resultado


async def medir_concurrente_api(
    urls: list[str], base_url: str = "http://localhost:8000"
) -> tuple[float, float, dict[str, Any]] | None:
    """Ejecuta las descargas enviando la tarea a la API de FastAPI si está disponible."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            health = await client.get(f"{base_url}/estadisticas")
            if health.status_code != 200:
                return None
        except Exception:
            return None

    async with httpx.AsyncClient(timeout=30.0) as client:
        inicio_cliente = time.perf_counter()
        resp_post = await client.post(
            f"{base_url}/tareas",
            json={"tipo": "descargar", "urls": urls, "timeout": 15.0},
        )
        if resp_post.status_code not in (200, 201, 202):
            return None

        tarea_id = resp_post.json()["id"]

        while True:
            await asyncio.sleep(0.05)
            resp_get = await client.get(f"{base_url}/tareas/{tarea_id}")
            tarea = resp_get.json()
            if tarea["estado"] in ("completada", "fallida", "cancelada"):
                duracion_cliente = time.perf_counter() - inicio_cliente
                duracion_servidor = tarea.get("duracion_segundos") or 0.0
                return duracion_cliente, duracion_servidor, tarea


async def main() -> None:
    print("=" * 65)
    print("  MEDICIÓN 1: CONCURRENCIA I/O (DESCARGAS HTTP)")
    print(f"  Cantidad de URLs: {len(URLS)} (JSONPlaceholder)")
    print("=" * 65)

    print("\n[1/3] Ejecutando descargas SECUENCIALES (una a una)...")
    t_sec, detalles_sec = await medir_secuencial(URLS)
    print(f"      -> Tiempo secuencial total (T_sec): {t_sec:.3f} s")

    print("\n[2/3] Ejecutando descargas CONCURRENTES (DescargarStrategy / gather)...")
    t_conc_directo, res_directo = await medir_concurrente_estrategia(URLS)
    print(f"      -> Tiempo concurrente directo (T_conc): {t_conc_directo:.3f} s")

    speedup_directo = t_sec / t_conc_directo if t_conc_directo > 0 else 0.0
    print(f"      -> Speedup directo (T_sec / T_conc): {speedup_directo:.2f}x")

    print("\n[3/3] Probando vía API FastAPI (POST /tareas)...")
    api_url = os.getenv("API_URL", "http://localhost:8000")
    res_api = await medir_concurrente_api(URLS, base_url=api_url)

    if res_api is not None:
        t_cliente, t_servidor, tarea = res_api
        speedup_api = t_sec / t_cliente if t_cliente > 0 else 0.0
        print(f"      -> Tiempo percibido por cliente (HTTP + Cola + Polling): {t_cliente:.3f} s")
        print(f"      -> Tiempo interno de ejecución en worker: {t_servidor:.3f} s")
        print(f"      -> Speedup end-to-end API: {speedup_api:.2f}x")
    else:
        print("      (API en localhost:8000 no detectada; omitiendo medición end-to-end)")

    print("\n" + "=" * 65)
    print("  RESUMEN DE RESULTADOS")
    print("=" * 65)
    print(f"  * Tiempo Secuencial (T_sec):   {t_sec:.3f} s")
    print(f"  * Tiempo Concurrente (T_conc): {t_conc_directo:.3f} s")
    print(f"  * Speedup obtenido:            {speedup_directo:.2f}x")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
