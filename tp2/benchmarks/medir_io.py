"""
Benchmark Medición 1: Concurrencia I/O (Descargas HTTP).

Cliente HTTP externo (caja negra) que compara:
1. Descargas estrictamente secuenciales desde el cliente.
2. Descargas concurrentes delegadas al servidor vía POST /tareas.

Calcula el Speedup = T_sec / T_conc.
"""
import asyncio
import os
import sys
import time
from typing import Any

import httpx

URLS = [f"https://jsonplaceholder.typicode.com/posts/{i}" for i in range(1, 21)]
API_URL = os.getenv("API_URL", "http://localhost:8000")


async def medir_secuencial(urls: list[str]) -> float:
    """Descarga 20 URLs de forma estrictamente secuencial."""
    inicio = time.perf_counter()
    async with httpx.AsyncClient(timeout=15.0) as client:
        for url in urls:
            resp = await client.get(url)
            resp.raise_for_status()
    return time.perf_counter() - inicio


async def medir_concurrente_api(
    urls: list[str], base_url: str
) -> tuple[float, float, dict[str, Any]]:
    """Despacha la tarea a la API y sondea hasta su finalización."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Encolar tarea en la API
        inicio_cliente = time.perf_counter()
        resp_post = await client.post(
            f"{base_url}/tareas",
            json={"tipo": "descargar", "urls": urls, "timeout": 20.0},
        )
        resp_post.raise_for_status()
        tarea_id = resp_post.json()["id"]

        # 2. Polling hasta estado final
        while True:
            await asyncio.sleep(0.05)
            resp_get = await client.get(f"{base_url}/tareas/{tarea_id}")
            resp_get.raise_for_status()
            tarea = resp_get.json()
            if tarea["estado"] in ("completada", "fallida", "cancelada"):
                duracion_cliente = time.perf_counter() - inicio_cliente
                duracion_servidor = float(tarea.get("duracion_segundos") or 0.0)
                return duracion_cliente, duracion_servidor, tarea


async def main() -> None:
    print("=" * 65)
    print("  BENCHMARK: MEDICIÓN 1 - CONCURRENCIA I/O (DESCARGAS)")
    print(f"  Destino API: {API_URL}")
    print(f"  Cantidad de URLs: {len(URLS)} (JSONPlaceholder)")
    print("=" * 65)

    # Verificar disponibilidad de la API
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            health = await client.get(f"{API_URL}/estadisticas")
            health.raise_for_status()
        except Exception as exc:
            print(f"\n[ERROR] No se pudo conectar a la API en {API_URL}: {exc}")
            print("Asegurate de que el contenedor o Uvicorn esté corriendo.")
            sys.exit(1)

    print("\n[1/2] Ejecutando 20 descargas SECUENCIALES...")
    t_sec = await medir_secuencial(URLS)
    print(f"      -> Tiempo Secuencial (T_sec): {t_sec:.3f} s")

    print("\n[2/2] Ejecutando tarea CONCURRENTE en el servidor...")
    t_cliente, t_servidor, tarea = await medir_concurrente_api(URLS, API_URL)
    print(f"      -> Tiempo interno del worker en servidor: {t_servidor:.3f} s")
    print(f"      -> Tiempo total cliente (POST + Cola + Polling): {t_cliente:.3f} s")

    speedup_servidor = t_sec / t_servidor if t_servidor > 0 else 0.0
    speedup_cliente = t_sec / t_cliente if t_cliente > 0 else 0.0

    print("\n" + "=" * 65)
    print("  RESULTADOS OBTENIDOS")
    print("=" * 65)
    print(f"  * Tiempo Secuencial (T_sec):        {t_sec:.3f} s")
    print(f"  * Tiempo Concurrente Servidor:      {t_servidor:.3f} s  (Speedup: {speedup_servidor:.2f}x)")
    print(f"  * Tiempo Total Cliente (End-to-End): {t_cliente:.3f} s  (Speedup: {speedup_cliente:.2f}x)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
