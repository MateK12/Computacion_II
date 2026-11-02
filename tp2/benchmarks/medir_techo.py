"""
Benchmark Medición 3: Techo del Pool de Workers y Saturación del Sistema.

Cliente HTTP externo (caja negra) que evalúa el comportamiento del sistema
ante ráfagas progresivas de carga concurrente: 10, 50, 100, 500 y 1000 tareas.

Utiliza la tarea `esperar` con una duración corta y controlada para estresar:
1. Ingestión y latencia de encolado en FastAPI (POST /tareas).
2. Throughput y saturación del pool de workers (asyncio.Queue y workers concurrentes).
3. Tiempo de espera en cola (espera_en_cola_segundos), evaluando la Ley de Little.
"""
import asyncio
import statistics
import sys
import time
from typing import Any

import httpx

# Constantes fijas de configuración (sin variables de entorno)
API_URL = "http://localhost:8000"
DURACION_TAREA = 0.05
CONCURRENCIA_POST = 50
INTERVALO_SONDEO = 0.05
TANDAS = [10, 50, 100, 500, 1000]


async def _encolar_tarea(
    client: httpx.AsyncClient,
    base_url: str,
    segundos: float,
    semaforo: asyncio.Semaphore,
) -> tuple[str, float]:
    """Envía una petición POST /tareas controlando la concurrencia de sockets."""
    async with semaforo:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{base_url}/tareas",
            json={"tipo": "esperar", "segundos": segundos},
            timeout=30.0,
        )
        resp.raise_for_status()
        latencia_ms = (time.perf_counter() - t0) * 1000.0
        tarea_id = resp.json()["id"]
        return tarea_id, latencia_ms


async def _esperar_drenado_pool( #pool para saber como vienen las tareas
    client: httpx.AsyncClient,
    base_url: str,
    intervalo: float = INTERVALO_SONDEO,
) -> None:
    """Sondea GET /estadisticas hasta que no queden tareas pendientes ni ejecutando."""
    while True:
        await asyncio.sleep(intervalo)
        resp = await client.get(f"{base_url}/estadisticas", timeout=10.0)
        resp.raise_for_status()
        stats = resp.json()
        if stats["pendientes"] == 0 and stats["ejecutando"] == 0:
            break


async def _obtener_metricas_tareas(
    client: httpx.AsyncClient,
    base_url: str,
    tarea_ids: set[str],
) -> list[dict[str, Any]]:
    """Obtiene el detalle final de las tareas del lote actual."""
    resp = await client.get(f"{base_url}/tareas", timeout=30.0)
    resp.raise_for_status()
    todas = resp.json()
    return [t for t in todas if t["id"] in tarea_ids]


async def ejecutar_tanda(
    base_url: str, n_tareas: int, duracion_tarea: float
) -> dict[str, Any]:
    """Ejecuta una tanda de N tareas midiendo encolado, drenado y espera en cola."""
    semaforo = asyncio.Semaphore(CONCURRENCIA_POST)
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)

    async with httpx.AsyncClient(limits=limits, timeout=60.0) as client:
        # 1. Encolar N tareas concurrentemente
        t_inicio_total = time.perf_counter()
        t_inicio_encolado = time.perf_counter()

        tareas_encolar = [
            _encolar_tarea(client, base_url, duracion_tarea, semaforo)
            for _ in range(n_tareas)
        ]
        resultados_encolado = await asyncio.gather(*tareas_encolar)

        duracion_encolado_total = time.perf_counter() - t_inicio_encolado
        latencias_post = [lat for _, lat in resultados_encolado]
        tarea_ids = {tid for tid, _ in resultados_encolado}

        # 2. Esperar drenado completo del pool (que se terminen todas las tareas)
        await _esperar_drenado_pool(client, base_url) 
        duracion_total = time.perf_counter() - t_inicio_total

        # 3. Recopilar métricas de las tareas del lote
        tareas_lote = await _obtener_metricas_tareas(client, base_url, tarea_ids)

        esperas_cola = [
            t.get("espera_en_cola_segundos") or 0.0 for t in tareas_lote
        ]
        duraciones_ejecucion = [
            t.get("duracion_segundos") or 0.0 for t in tareas_lote
        ]

        throughput = n_tareas / duracion_total if duracion_total > 0 else 0.0

        return {
            "n_tareas": n_tareas,
            "duracion_total_s": round(duracion_total, 3),
            "duracion_encolado_s": round(duracion_encolado_total, 3),
            "throughput_tps": round(throughput, 2),
            "post_lat_min_ms": round(min(latencias_post), 2),
            "post_lat_avg_ms": round(statistics.mean(latencias_post), 2),
            "post_lat_p50_ms": round(statistics.median(latencias_post), 2),
            "post_lat_max_ms": round(max(latencias_post), 2),
            "cola_espera_avg_s": round(statistics.mean(esperas_cola), 3),
            "cola_espera_p50_s": round(statistics.median(esperas_cola), 3),
            "cola_espera_max_s": round(max(esperas_cola), 3),
            "ejecucion_avg_s": round(statistics.mean(duraciones_ejecucion), 3),
        }


def imprimir_tabla_resultados(resultados: list[dict[str, Any]]) -> None:
    """Imprime una tabla formateada con los resultados de todas las tandas."""
    print("\n" + "=" * 94)
    print("                      RESULTADOS MEDICIÓN 3: TECHO DEL POOL")
    print("=" * 94)
    headers = [
        "Tareas (N)",
        "T. Encolado",
        "T. Total",
        "Throughput",
        "POST p50",
        "POST Max",
        "Cola Avg",
        "Cola Max",
    ]
    fmt = "{:>10} | {:>11} | {:>9} | {:>12} | {:>10} | {:>10} | {:>9} | {:>9}"
    print(fmt.format(*headers))
    print("-" * 94)

    for r in resultados:
        print(
            fmt.format(
                str(r["n_tareas"]),
                f"{r['duracion_encolado_s']} s",
                f"{r['duracion_total_s']} s",
                f"{r['throughput_tps']} t/s",
                f"{r['post_lat_p50_ms']} ms",
                f"{r['post_lat_max_ms']} ms",
                f"{r['cola_espera_avg_s']} s",
                f"{r['cola_espera_max_s']} s",
            )
        )
    print("=" * 94)


async def main() -> None:
    print("=" * 70)
    print("  BENCHMARK: MEDICIÓN 3 - TECHO DEL POOL Y SATURACIÓN")
    print(f"  Destino API: {API_URL}")
    print(f"  Duración tarea base: {DURACION_TAREA} s (esperar)")
    print(f"  Concurrencia cliente POST: {CONCURRENCIA_POST}")
    print(f"  Tandas de prueba: {TANDAS}")
    print("=" * 70)

    # Verificar disponibilidad de la API
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            health = await client.get(f"{API_URL}/estadisticas")
            health.raise_for_status()
            stats = health.json()
            print(f"[OK] Conectado a la API. Tareas actuales en memoria: {stats.get('total', 0)}")
        except Exception as exc:
            print(f"[ERROR] No se pudo conectar a la API en {API_URL}: {exc}")
            print("Asegurate de iniciar la API primero:")
            print("  uvicorn src.main:app --port 8000")
            print("  o con Docker: docker compose up")
            sys.exit(1)

    todos_los_resultados: list[dict[str, Any]] = []

    for n in TANDAS:
        print(f"\n--> Iniciando tanda con N = {n} tareas concurrentes...")
        res = await ejecutar_tanda(API_URL, n, DURACION_TAREA)
        todos_los_resultados.append(res)
        print(
            f"    [COMPLETADA N={n}] Total: {res['duracion_total_s']}s | "
            f"Throughput: {res['throughput_tps']} t/s | "
            f"POST p50: {res['post_lat_p50_ms']}ms | "
            f"Cola Avg: {res['cola_espera_avg_s']}s | Cola Max: {res['cola_espera_max_s']}s"
        )
        # Breve pausa para estabilizar sockets entre tandas
        await asyncio.sleep(1.0)

    imprimir_tabla_resultados(todos_los_resultados)


if __name__ == "__main__":
    asyncio.run(main())
