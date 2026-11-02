import asyncio
import time
from typing import Any

import httpx

from src.models import TareaDescargarCreate
from src.tasks.base import TareaStrategy


class DescargarStrategy(TareaStrategy):
    """Estrategia para descargar una lista de URLs concurrentemente con httpx."""

    async def _descargar_una(
        self, client: httpx.AsyncClient, url: str
    ) -> dict[str, Any]:
        """Descarga una URL individual, midiendo status, tamaño y duración."""
        inicio = time.perf_counter()
        try:
            response = await client.get(url)
            duracion = round(time.perf_counter() - inicio, 4)
            return {
                "url": url,
                "status_code": response.status_code,
                "tamano_bytes": len(response.content),
                "duracion_segundos": duracion,
                "error": None,
            }
        except Exception as exc:
            duracion = round(time.perf_counter() - inicio, 4)
            return {
                "url": url,
                "status_code": None,
                "tamano_bytes": 0,
                "duracion_segundos": duracion,
                "error": str(exc),
            }

    async def ejecutar(self, parametros: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta las descargas de forma concurrente utilizando asyncio.gather."""
        if "tipo" not in parametros:
            parametros = {**parametros, "tipo": "descargar"}
        datos = TareaDescargarCreate.model_validate(parametros)

        timeout = datos.timeout if datos.timeout is not None else 10.0
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            tareas = [self._descargar_una(client, url) for url in datos.urls] #concurrentemente
            resultados = await asyncio.gather(*tareas, return_exceptions=True) #permite devolver las excepciones

        reportes: list[dict[str, Any]] = []
        for i, res in enumerate(resultados):
            if isinstance(res, Exception): #de esta forma se reporta el error individualmete
                reportes.append(
                    {
                        "url": datos.urls[i],
                        "status_code": None,
                        "tamano_bytes": 0,
                        "duracion_segundos": 0.0,
                        "error": str(res),
                    }
                )
            else:
                reportes.append(res)

        return {
            "total_urls": len(datos.urls),
            "exitosas": sum(1 for r in reportes if r["error"] is None),
            "fallidas": sum(1 for r in reportes if r["error"] is not None),
            "resultados": reportes,
        }
