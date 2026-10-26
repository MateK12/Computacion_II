"""
Benchmark Medición 2: El Event Loop Bloqueado (CPU-bound vs ProcessPoolExecutor).

Cliente HTTP externo (caja negra) que compara:
1. Peticiones concurrentes a GET /tareas mientras corre una tarea CPU-bound CON ProcessPoolExecutor.
2. Peticiones concurrentes a GET /tareas mientras corre una tarea CPU-bound SIN executor (bloqueando el event loop).

Mide y compara latencia mínima, promedio, mediana y máxima experimentada por los clientes.
"""
import asyncio
import os
import statistics
import sys
import time
from typing import Any

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000")
ITERACIONES = int(os.getenv("ITERACIONES", "3000000"))
INTERVALO_SONDEO = float(os.getenv("INTERVALO_SONDEO", "0.05"))


async def _medir_ping(
    client: httpx.AsyncClient, base_url: str, latencias: list[float]
) -> None:
    """Envía una petición GET /tareas y registra el tiempo de respuesta en milisegundos."""
    t0 = time.perf_counter()
    try:
        resp = await client.get(f"{base_url}/tareas", timeout=15.0)
        resp.raise_for_status()
        latencias.append((time.perf_counter() - t0) * 1000.0)
    except Exception as exc:
        print(f"      [AVISO] Falló ping testigo: {exc}")


async def _generador_trafico(
    client: httpx.AsyncClient,
    base_url: str,
    stop_event: asyncio.Event,
    intervalo: float,
    latencias: list[float],
) -> list[asyncio.Task[None]]:
    """Genera ráfagas periódicas concurrentes de peticiones testigo GET /tareas."""
    tasks: list[asyncio.Task[None]] = []
    while not stop_event.is_set():
        task = asyncio.create_task(_medir_ping(client, base_url, latencias))
        tasks.append(task)
        await asyncio.sleep(intervalo)
    return tasks


async def medir_escenario(
    base_url: str, usar_executor: bool, iteraciones: int
) -> dict[str, Any]:
    """Ejecuta una corrida completa de hashear midiendo latencias concurrentes."""
    latencias: list[float] = []
    stop_event = asyncio.Event()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Encolar tarea CPU-bound
        inicio_cliente = time.perf_counter()
        resp_post = await client.post(
            f"{base_url}/tareas",
            json={
                "tipo": "hashear",
                "texto": "benchmark_bloqueo_cpu",
                "iteraciones": iteraciones,
                "usar_executor": usar_executor,
                "timeout": 30.0,
            },
        )
        resp_post.raise_for_status()
        tarea_id = resp_post.json()["id"]

        # 2. Iniciar generador de tráfico testigo en paralelo
        trafico_task = asyncio.create_task(
            _generador_trafico(
                client, base_url, stop_event, INTERVALO_SONDEO, latencias
            )
        )

        # 3. Sondeo del estado de la tarea
        tarea_finalizada: dict[str, Any] = {}
        while True:
            await asyncio.sleep(0.05)
            try:
                resp_get = await client.get(
                    f"{base_url}/tareas/{tarea_id}", timeout=15.0
                )
                resp_get.raise_for_status()
                tarea = resp_get.json()
                if tarea["estado"] in ("completada", "fallida", "cancelada"):
                    tarea_finalizada = tarea
                    break
            except httpx.HTTPError:
                # Durante el bloqueo del loop la conexión puede demorar; seguimos esperando
                pass

        # 4. Detener generador y recolectar pings
        stop_event.set()
        pings_lanzados = await trafico_task
        if pings_lanzados:
            await asyncio.gather(*pings_lanzados, return_exceptions=True)

        duracion_cliente = time.perf_counter() - inicio_cliente
        duracion_servidor = float(
            tarea_finalizada.get("duracion_segundos") or 0.0
        )

    # 5. Cálculo estadístico de latencias (en ms)
    pings_completados = len(latencias)
    if pings_completados > 0:
        lat_min = min(latencias)
        lat_max = max(latencias)
        lat_avg = statistics.mean(latencias)
        lat_med = statistics.median(latencias)
    else:
        lat_min = lat_max = lat_avg = lat_med = 0.0

    return {
        "usar_executor": usar_executor,
        "iteraciones": iteraciones,
        "duracion_servidor": duracion_servidor,
        "duracion_cliente": duracion_cliente,
        "pings_completados": pings_completados,
        "lat_min_ms": lat_min,
        "lat_avg_ms": lat_avg,
        "lat_med_ms": lat_med,
        "lat_max_ms": lat_max,
        "tarea": tarea_finalizada,
    }


async def main() -> None:
    print("=" * 70)
    print("  BENCHMARK: MEDICIÓN 2 - EVENT LOOP BLOQUEADO (CPU-BOUND)")
    print(f"  Destino API:           {API_URL}")
    print(f"  Iteraciones SHA-256:   {ITERACIONES:,}")
    print(f"  Frecuencia de sondeo:  cada {INTERVALO_SONDEO * 1000:.0f} ms")
    print("=" * 70)

    # Verificar disponibilidad de la API
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            health = await client.get(f"{API_URL}/estadisticas")
            health.raise_for_status()
        except Exception as exc:
            print(f"\n[ERROR] No se pudo conectar a la API en {API_URL}: {exc}")
            print("Asegurate de que el contenedor o Uvicorn esté corriendo.")
            sys.exit(1)

    print("\n[1/2] Probando CON ProcessPoolExecutor (usar_executor=True)...")
    res_con = await medir_escenario(API_URL, usar_executor=True, iteraciones=ITERACIONES)
    print(f"      -> Duración de la tarea (servidor): {res_con['duracion_servidor']:.3f} s")
    print(f"      -> Pings GET /tareas completados:   {res_con['pings_completados']}")
    print(f"      -> Latencia Promedio:               {res_con['lat_avg_ms']:.2f} ms")
    print(f"      -> Latencia Máxima:                 {res_con['lat_max_ms']:.2f} ms")

    # Pausa de estabilización entre pruebas
    await asyncio.sleep(1.0)

    print("\n[2/2] Probando SIN EXECUTOR - En el Event Loop (usar_executor=False)...")
    res_sin = await medir_escenario(API_URL, usar_executor=False, iteraciones=ITERACIONES)
    print(f"      -> Duración de la tarea (servidor): {res_sin['duracion_servidor']:.3f} s")
    print(f"      -> Pings GET /tareas completados:   {res_sin['pings_completados']}")
    print(f"      -> Latencia Promedio:               {res_sin['lat_avg_ms']:.2f} ms")
    print(f"      -> Latencia Máxima:                 {res_sin['lat_max_ms']:.2f} ms")

    # Comparación de impacto
    degradacion_avg = (
        (res_sin["lat_avg_ms"] / res_con["lat_avg_ms"])
        if res_con["lat_avg_ms"] > 0
        else 0.0
    )
    degradacion_max = (
        (res_sin["lat_max_ms"] / res_con["lat_max_ms"])
        if res_con["lat_max_ms"] > 0
        else 0.0
    )

    print("\n" + "=" * 70)
    print("  RESULTADOS OBTENIDOS - IMPACTO EN LA LATENCIA DE LA API")
    print("=" * 70)
    print(f"  Métrica                    | Con Executor (Async) | Sin Executor (Bloqueo)")
    print(f"  ---------------------------+----------------------+-----------------------")
    print(f"  Duración tarea servidor    | {res_con['duracion_servidor']:>16.3f} s | {res_sin['duracion_servidor']:>17.3f} s")
    print(f"  Pings respondidos          | {res_con['pings_completados']:>20} | {res_sin['pings_completados']:>23}")
    print(f"  Latencia Mínima            | {res_con['lat_min_ms']:>17.2f} ms | {res_sin['lat_min_ms']:>18.2f} ms")
    print(f"  Latencia Mediana (p50)     | {res_con['lat_med_ms']:>17.2f} ms | {res_sin['lat_med_ms']:>18.2f} ms")
    print(f"  Latencia Promedio          | {res_con['lat_avg_ms']:>17.2f} ms | {res_sin['lat_avg_ms']:>18.2f} ms")
    print(f"  Latencia Máxima            | {res_con['lat_max_ms']:>17.2f} ms | {res_sin['lat_max_ms']:>18.2f} ms")
    print(f"  ---------------------------+----------------------+-----------------------")
    print(f"  Factor de degradación promedio: {degradacion_avg:.1f}x más lento sin executor")
    print(f"  Factor de degradación máximo:   {degradacion_max:.1f}x más lento sin executor")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
