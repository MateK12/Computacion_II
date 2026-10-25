# Plataforma de Tareas Distribuidas

**Computación II — Universidad de Mendoza — 2026**

Servicio asíncrono para delegación y procesamiento distribuido de tareas vía API HTTP, construido con **FastAPI**, **asyncio** y **Docker**. Diseñado para atender múltiples clientes concurrentes en un único hilo de ejecución sin bloquear el event loop, distinguiendo formalmente cargas de trabajo I/O-bound y CPU-bound.

---

## Arquitectura del Sistema

```
   Cliente HTTP (curl / benchmark)
                 │
                 ▼
   ┌───────────────────────────┐         ┌───────────────────────────┐
   │     API REST (FastAPI)    │────────>│       Cola de Tareas      │
   │  POST   /tareas           │         │      (asyncio.Queue)      │
   │  GET    /tareas           │         └─────────────┬─────────────┘
   │  GET    /tareas/{id}      │                       │
   │  DELETE /tareas/{id}      │                       ▼
   │  GET    /estadisticas     │         ┌───────────────────────────┐
   └─────────────┬─────────────┘         │      Pool de Workers      │
                 │                       │  N corrutinas concurrentes│
                 ▼                       │  (Consumen UUIDs de cola) │
   ┌───────────────────────────┐         └─────────────┬─────────────┘
   │   Repositorio en Memoria  │<──────────────────────┤
   │       (TaskManager)       │  actualizan estado    │
   │  Single Source of Truth   │                       ▼
   └─────────────┬─────────────┘         ┌───────────────────────────┐
                 │                       │   ProcessPoolExecutor     │
                 ▼                       │ (CPU-bound: hashear SHA)  │
   ┌───────────────────────────┐         └───────────────────────────┘
   │   Persistencia Snapshot   │
   │   (estado_<ts>.json)      │
   └───────────────────────────┘
```

### Componentes Principales

| Componente | Rol y Responsabilidad |
|------------|-----------------------|
| **FastAPI API** | Expone los endpoints HTTP. Inyecta tareas en cola y responde inmediatamente con estado `pendiente` (HTTP 202). |
| **TaskManager** | Repositorio de estado en memoria (SSOT). Registra modelos `TareaResponse` y referencias a los `asyncio.Task` activos (`runners`) para permitir cancelación granular. |
| **asyncio.Queue** | Cola en memoria donde se transmiten únicamente los identificadores (`UUID`) de las tareas pendientes. |
| **Worker Pool** | Conjunto de $N$ corrutinas que consumen identificadores de la cola secuencialmente, despachan a la estrategia correspondiente y administran timeouts. |
| **ProcessPoolExecutor** | Pool de procesos separados del sistema operativo para aislar tareas CPU-bound (`hashear`) del GIL y del event loop. |
| **Persistencia** | Serializador de snapshots JSON ante apagado ordenado (`SIGINT`/`SIGTERM`) y recuperador de historial previo. |

---

## Mediciones Obligatorias

### Medición 1: Concurrencia I/O (Descargas HTTP)

El objetivo de esta medición es verificar empíricamente la ventaja de la multiplexación de I/O no bloqueante frente al procesamiento estrictamente secuencial al realizar operaciones de red concurrentes.

#### Metodología

Se ejecutó el benchmark automatizado [`benchmarks/medir_io.py`](benchmarks/medir_io.py) descargando 20 recursos JSON independientes desde la API pública JSONPlaceholder (`https://jsonplaceholder.typicode.com/posts/{1..20}`):

1. **Modo Secuencial**: El cliente ejecuta las 20 descargas en serie estricta usando una sesión HTTP (`httpx.AsyncClient`), esperando el ciclo completo de cada request antes de enviar el siguiente.
2. **Modo Concurrente Servidor**: El cliente delega la tarea al servidor (`POST /tareas` con tipo `descargar`). El worker despacha los 20 requests concurrentemente usando `asyncio.gather` dentro del event loop.
3. **Modo Concurrente End-to-End**: Mide el tiempo total percibido por el cliente desde que envía el `POST /tareas`, la tarea viaja por la `asyncio.Queue`, es procesada por el worker, y el cliente obtiene el resultado vía polling a `GET /tareas/{id}`.

#### Resultados Obtenidos

| Modalidad | Tiempo Total | Speedup ($T_{sec} / T$) | Notas |
|-----------|--------------|-------------------------|-------|
| **Secuencial (Serie)** | **0.411 s** | $1.00\times$ (Base) | Cada request espera secuencialmente el RTT completo del anterior. |
| **Concurrente Servidor** | **0.159 s** | **$2.58\times$** | Medición interna neta del worker procesando con `asyncio.gather`. |
| **Concurrente End-to-End (Cliente)** | **0.192 s** | **$2.14\times$** | Incluye HTTP `POST`, encolado, polling cada 50ms y respuesta JSON. |

#### Interpretación y Fundamento Teórico

1. **Multiplexación de sockets sin bloqueo**: En el enfoque secuencial, el tiempo total es la suma de las latencias de cada petición ($T_{sec} \approx \sum_{i=1}^{20} RTT_i$). En contraste, `DescargarStrategy` inicializa todos los sockets de red casi en simultáneo. El sistema operativo notifica al event loop vía `epoll` a medida que llegan los paquetes de cada socket.
2. **Acotamiento por el request más lento**: En un esquema concurrente ideal, el tiempo total no es la suma sino que converge al tiempo del request individual con mayor latencia más el overhead del runtime ($T_{conc} \approx \max_{i}(RTT_i) + \varepsilon$). Por eso se observa un speedup de más del doble ($2.58\times$) aun compitiendo por el mismo ancho de banda local.
3. **Overhead del ciclo de vida REST**: La diferencia entre el tiempo neto del servidor (0.159 s) y el percibido por el cliente (0.192 s) refleja la sobrecarga del protocolo HTTP externo, el serializado Pydantic, la contención mínima de la cola y el intervalo de sondeo (polling) del cliente.

---

### Medición 2: El Event Loop Bloqueado (CPU-bound)
*(A completar según cronograma)*

---

### Medición 3: Techo del Pool y Saturación
*(A completar según cronograma)*

---

## Ejecución y Pruebas

### Levantar con Docker

```bash
docker compose up --build
```

### Ejecutar Suite de Tests

```bash
pytest
```

### Ejecutar Benchmark de Concurrencia I/O

```bash
python benchmarks/medir_io.py
```
