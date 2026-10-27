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

El objetivo de esta medición es demostrar de manera cuantitativa el impacto de ejecutar tareas intensivas de CPU directamente dentro del hilo del event loop frente a delegarlas a un pool de procesos (`ProcessPoolExecutor`).

#### Metodología

Se ejecutó el benchmark automatizado [`benchmarks/medir_bloqueo.py`](benchmarks/medir_bloqueo.py) contra la API corriendo en Docker:
1. Se encoló una tarea `hashear` con **3.000.000 de iteraciones SHA-256 encadenadas**.
2. De forma concurrente, el cliente emitió ráfagas periódicas de peticiones de lectura a `GET /tareas` cada 50 ms para registrar las latencias experimentadas por otros usuarios.
3. Se evaluaron dos condiciones:
   - **Con Executor (`usar_executor: true`)**: La tarea delega el cómputo a un proceso hijo mediante `loop.run_in_executor(ProcessPoolExecutor, ...)`.
   - **Sin Executor (`usar_executor: false`)**: La tarea ejecuta el bucle de hashing directamente dentro de la corrutina en el hilo principal del event loop.

#### Resultados Obtenidos

| Métrica de Rendimiento | Con ProcessPoolExecutor | Sin Executor (En Event Loop) | Impacto / Factor de Degradación |
|------------------------|-------------------------|------------------------------|---------------------------------|
| **Duración de la tarea (Servidor)** | 1.673 s | 1.664 s | Tiempo de cómputo equivalente (~1.67 s) |
| **Pings `GET /tareas` Respondidos** | 34 | 33 | Cobertura durante la ventana de ejecución |
| **Latencia Mínima** | **1.56 ms** | 62.92 ms | $40.3\times$ mayor |
| **Latencia Mediana ($p_{50}$)** | **2.20 ms** | 866.28 ms | **$393.8\times$ mayor** |
| **Latencia Promedio** | **4.02 ms** | 865.38 ms | **$215.0\times$ más lento** |
| **Latencia Máxima** | **56.72 ms** | **1666.60 ms** | **$29.4\times$ más lento** (~1.67 s de espera) |

#### Interpretación y Fundamento Teórico

1. **Monopolio del hilo de ejecución (Starvation del Event Loop)**: En el modelo de concurrencia cooperativa de `asyncio`, todas las corrutinas comparten un único hilo del SO. Si una corrutina ejecuta un bucle cerrado de CPU sin puntos de suspensión (`await`), el runtime no puede conmutar de contexto. El hilo queda 100% ocupado ejecutando instrucciones aritméticas y no puede invocar al multiplexor de E/S (`epoll`).
2. **Retención en el Listen Backlog del Kernel**: Durante el segundo y medio de bloqueo, las solicitudes HTTP entrantes se acumulan en la cola TCP del kernel (`listen backlog`). Cuando la corrutina finalmente termina, el loop se reactiva y atiende todas las peticiones represadas en ráfaga. Por esta razón, la latencia máxima observada (1666.60 ms) coincide casi exactamente con la duración neta del cómputo CPU-bound (1664 ms).
3. **Evasión del GIL mediante Procesos Separados**: A diferencia de los hilos de Python (que compiten por el Global Interpreter Lock impidiendo el paralelismo de CPU), el `ProcessPoolExecutor` lanza procesos independientes del sistema operativo con su propio espacio de memoria e intérprete. El hilo principal se limita a delegar el trabajo y esperar de forma no bloqueante a través de un descriptor de socket/pipe IPC, permitiendo que la API continúe despachando peticiones con latencias del orden de 2 a 4 ms.

---

### Medición 3: Techo del Pool y Saturación

Se evaluó la capacidad de absorción y procesamiento de la plataforma ante ráfagas crecientes de tareas concurrentes ($N \in \{10, 50, 100, 500, 1000\}$). Se utilizó la tarea `esperar` con una duración base de $0.05\text{ s}$ ejecutada en el contenedor Docker con $N_{\text{workers}} = 3$.

#### Resultados Empíricos

| Tareas ($N$) | T. Encolado | T. Total Drenado | Throughput Real | POST Latencia ($p_{50}$) | POST Latencia Máx | Espera en Cola Promedio | Espera en Cola Máx |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **10** | 0.067 s | 0.293 s | **34.17 t/s** | 59.39 ms | 66.43 ms | 0.061 s | 0.147 s |
| **50** | 0.146 s | 0.965 s | **51.80 t/s** | 99.65 ms | 121.26 ms | 0.395 s | 0.801 s |
| **100** | 0.298 s | 1.841 s | **54.31 t/s** | 84.26 ms | 216.87 ms | 0.742 s | 1.436 s |
| **500** | 2.413 s | 8.531 s | **58.61 t/s** | 148.06 ms | 1346.61 ms | 3.074 s | 6.035 s |
| **1000** | 4.867 s | 17.035 s | **58.70 t/s** | 152.44 ms | 1598.57 ms | 6.085 s | 12.067 s |

#### Interpretación y Fundamento Teórico

1. **Convergencia al Techo Teórico de Throughput**: Con $N=3$ workers y tareas de duración $t = 0.05\text{ s}$, la tasa máxima teórica de procesamiento es:
   $$\mu = \frac{N_{\text{workers}}}{t} = \frac{3}{0.05\text{ s}} = 60.0\text{ tareas/segundo}$$
   Los datos empíricos demuestran cómo el sistema amortiza la sobrecarga de arranque y converge asintóticamente a su asíntota teórica: desde $34.17\text{ t/s}$ en lotes pequeños hasta **$58.70\text{ t/s}$** con 1.000 tareas (**$97.8\%$ de eficiencia teórica**).
2. **Buffer Elástico y Ley de Little**: La tasa de llegada de tareas a la API superó con creces la capacidad de drenado ($\lambda \approx 205\text{ t/s} > \mu \approx 60\text{ t/s}$). La cola monohilo `asyncio.Queue` actuó como amortiguador en memoria sin descartar peticiones. Siguiendo la Ley de Little ($L = \lambda W$), a mayor saturación acumulada, el tiempo de espera en cola escala de manera proporcional: mientras las primeras tareas son tomadas de inmediato, las últimas tareas de la tanda de 1.000 esperaron hasta $12.067\text{ s}$ antes de ser atendidas por un worker libre.
3. **Desacoplamiento entre Ingestión HTTP y Workers**: A pesar de inyectar 1.000 peticiones en ráfaga, la latencia mediana de `POST /tareas` ($p_{50}$) se mantuvo en el rango de los $\sim 150\text{ ms}$. Esto demuestra la efectividad de la arquitectura asíncrona: la API confirma la recepción y cede el trabajo a la cola de forma no bloqueante, aislando a los clientes web de la congestión interna del pool.

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

### Ejecutar Benchmark de Event Loop Bloqueado (CPU-bound)

```bash
python benchmarks/medir_bloqueo.py
```

### Ejecutar Benchmark de Techo del Pool y Saturación

```bash
python benchmarks/medir_techo.py
```
