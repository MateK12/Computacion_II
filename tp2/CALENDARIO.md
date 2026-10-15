# Calendario de Trabajo — TP2: Plataforma de Tareas Distribuidas

**Computación II — Universidad de Mendoza — 2026**  
**Fecha de Inicio:** Martes 13/10/2026 (Clase 21)  
**Fecha de Entrega:** Martes 03/11/2026 (Clase 24, al finalizar la clase)  
**Ventana Total de Desarrollo:** 21 días (3 semanas completas)

---

## Filosofía del Cronograma

> *"Hacé bloques de 30-60 minutos, después cerrá, repasá lo que aprendiste y volvé al otro día. El cerebro consolida mejor así."* (Cátedra de Computación II)

Este calendario está estructurado en 3 fases semanales (Sprints), dejando los últimos 2 días como **buffer de contingencia** para pulido, documentación y simulacro de preguntas de defensa oral.

---

## Vista General de Hitos

```
13/10                    20/10                    27/10                    03/11
  │                        │                        │                        │
  ▼                        ▼                        ▼                        ▼
[ SEMANA 1: ESQUELETO ]  [ SEMANA 2: CORE REAL ]  [ SEMANA 3: MEDICIONES ] [ ENTREGA ]
- Modelos Pydantic       - Tarea descargar (I/O)  - 3 Mediciones reales    - README final
- API FastAPI (mocks)    - Tarea hashear (CPU)    - Análisis y gráficos    - Simulación oral
- asyncio.Queue          - Tarea esperar          - Docker compose final   - Repo listo
- Worker Pool (corrut.)  - Cancelación/Timeouts   - dudas.md al día
                         - Shutdown + Dump JSON
```

---

## Semana 1: Diseño, Esqueleto de API y Worker Pool (13/10 - 20/10)

**Objetivo:** Tener la arquitectura armada, los endpoints respondiendo inmediatamente y los workers consumiendo de una cola en segundo plano (con tareas mock).

| Día | Fecha | Tarea / Actividad | Duración Estimada | Estado |
|---|---|---|---|---|
| **Día 1** | Mar 13/10 | **Kickoff y Lectura Crítica**: Leer consigna en detalle, configurar entorno virtual (`venv`), `requirements.txt` básico (`fastapi`, `uvicorn`, `httpx`, `pydantic`). | 1h | [x] |
| **Día 2** | Mié 14/10 | **Modelos de Dominio**: Diseñar schemas Pydantic (`TareaCreate`, `TareaResponse`, enum `EstadoTarea`) y estructura en memoria de tareas (`dict` con metadatos). Discutir por qué no hace falta lock monohilo. | 1h | [x] |
| **Día 3** | Jue 15/10 | **API FastAPI (Esqueleto)**: Implementar endpoints `POST /tareas`, `GET /tareas`, `GET /tareas/{id}` y `GET /estadisticas`. Asegurar que `POST` responda **inmediatamente** con estado `pendiente`. | 1.5h | [x] |
| **Día 4** | Vie 16/10 | **Cola y Worker Pool**: Crear `asyncio.Queue` y función corrutina `worker()`. Discutir diferencia entre `queue.Queue` y `asyncio.Queue`. Lanzar N workers en background. | 1.5h | [ ] |
| **Día 5** | Sáb 17/10 | **Lifespan de FastAPI**: Integrar el ciclo de vida de los workers al startup/shutdown de FastAPI usando `@asynccontextmanager`. Probar tareas dummy encolándose y procesándose. | 1h | [ ] |
| **Día 6** | Dom 18/10 | **Pruebas de Esqueleto y Descanso**: Verificar flujo completo API -> Cola -> Worker dummy -> Estado `completada`. Anotar dudas en `dudas.md`. | 1h | [ ] |
| **Día 7** | Lun 19/10 - Mar 20/10 | **Checkpoint Semana 1**: Revisión de código, modularización en `src/` (`main.py`, `models.py`, `pool.py`, `manager.py`). | 1h | [ ] |

---

## Semana 2: Tareas Reales, Concurrencia, Cancelación y Persistencia (21/10 - 27/10)

**Objetivo:** Las 3 tareas obligatorias funcionando de verdad, executor para CPU-bound, cancelación limpia con timeouts, shutdown ordenado y Docker.

| Día | Fecha | Tarea / Actividad | Duración Estimada | Estado |
|---|---|---|---|---|
| **Día 8** | Mié 21/10 | **Tarea `descargar` (I/O-bound)**: Implementar descarga de lista de URLs concurrentemente con `httpx.AsyncClient` y `asyncio.gather`. Medir que el tiempo sea el del request más lento y no la suma. | 1.5h | [ ] |
| **Día 9** | Jue 22/10 | **Tarea `esperar`**: Implementar tarea que duerme $N$ segundos con `await asyncio.sleep()`. Servirá como banco de pruebas para cancelación y timeouts. | 45m | [ ] |
| **Día 10** | Vie 23/10 | **Tarea `hashear` (CPU-bound) & Executor**: Implementar hash SHA-256 iterativo. Discutir GIL y resolverlo con `run_in_executor` (`ProcessPoolExecutor` vs `ThreadPoolExecutor`). Explicar por qué no bloquea la API. | 2h | [ ] |
| **Día 11** | Sáb 24/10 | **Cancelación y Timeouts**: Implementar `DELETE /tareas/{id}`. Cancelar tareas encoladas y en ejecución (`task.cancel()`, captura de `asyncio.CancelledError`). Configurar timeout por tarea. | 2h | [ ] |
| **Día 12** | Dom 25/10 | **Apagado Ordenado (Graceful Shutdown)**: Capturar `SIGINT` y `SIGTERM`. Dejar de aceptar tareas nuevas, esperar tareas activas con límite y persistir el estado a `estado_<timestamp>.json`. Loguear al iniciar si existe dump. | 1.5h | [ ] |
| **Día 13** | Lun 26/10 | **Dockerización**: Armar `Dockerfile` y `docker-compose.yml`. Verificar que levante con `docker compose up --build` y que el puerto sea accesible desde el host. | 1.5h | [ ] |
| **Día 14** | Mar 27/10 | **Checkpoint Semana 2**: Sistema funcional de punta a punta dentro de Docker. Guardar snapshot conceptual en Engram. | 1h | [ ] |

---

## Semana 3: Benchmarks, Informe Técnico (README) y Defensa (28/10 - 03/11)

**Objetivo:** Obtener las 3 mediciones empíricas con scripts automatizados, redactar el `README.md` exhaustivo y preparar la defensa oral.

| Día | Fecha | Tarea / Actividad | Duración Estimada | Estado |
|---|---|---|---|---|
| **Día 15** | Mié 28/10 | **Medición 1 (Concurrencia I/O)**: Script de 20 descargas secuenciales vs 20 concurrentes. Calcular Speedup real. | 1.5h | [ ] |
| **Día 16** | Jue 29/10 | **Medición 2 (Event Loop Bloqueado)**: Script que mide latencia de `GET /tareas` mientras corre `hashear` sin executor vs con executor. | 1.5h | [ ] |
| **Día 17** | Vie 30/10 | **Medición 3 (Techo del Pool)**: Incrementar tareas concurrentes hasta saturar. Encontrar el límite del sistema (sockets, CPU, RAM) y explicar el porqué. | 1.5h | [ ] |
| **Día 18** | Sáb 31/10 | **Redacción del `README.md` (Parte 1)**: Diagrama de arquitectura, guía de uso con ejemplos `curl`, justificación de decisiones (Queue, Executor, Lock, Cancelación). | 2h | [ ] |
| **Día 19** | Dom 01/11 | **Redacción del `README.md` (Parte 2)**: Incorporar tablas de mediciones, interpretación de números, conexión con las clases teóricas (select/epoll, event loop, GIL) y lo aprendido. | 2h | [ ] |
| **Día 20** | Lun 02/11 | **Buffer de Contingencia & Simulación Oral**: Repasar preguntas de examen oral de la cátedra. Verificar `docker compose up --build` desde cero. Limpieza de código (PEP 8). | 1.5h | [ ] |
| **Día 21** | **Mar 03/11** | **ENTREGA FINAL (Clase 24)**: Verificar repositorio público en GitHub, links, badges y entregar en horario de clase. | 30m | [ ] |

---

## Puntos de Control y Criterios de Aprobación

- [ ] **Funcionalidad (25%)**: ¿La API responde de inmediato al POST? ¿Las tareas transicionan correctamente por los estados?
- [ ] **Asincronismo (30%)**: ¿El event loop jamás se bloquea? ¿Las descargas son concurrentes? ¿La cancelación limpia recursos sin dejar corrutinas colgadas?
- [ ] **Mediciones (15%)**: ¿Están los números reales de las 3 mediciones con su speedup y análisis?
- [ ] **README (20%)**: ¿Están justificadas las decisiones y conectadas con las clases 13 a 22?
- [ ] **Código y Docker (10%)**: ¿Todo levanta con `docker compose up --build` de forma reproducible?
