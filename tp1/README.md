# Monitor de Procesos y Threads

**Computación II — Universidad de Mendoza — 2026**

Monitor en tiempo real del sistema Linux, parecido a `htop` pero con énfasis en la **anatomía interna** de cada proceso y sus threads. Lee directamente de `/proc` (sin `psutil` ni herramientas externas) y está construido como un **sistema multiproceso** donde cada componente corre en paralelo.

---

## ¿Qué hace?

- Lista todos los procesos del sistema leyendo `/proc/<pid>`.
- Muestra 7 vistas alternables:
  1. **Resumen** — estado, CPU%, RSS, threads, comando.
  2. **Memoria** — segmentos (VmSize, RSS, Data, Stack, etc.) y page faults.
  3. **File Descriptors** — FDs abiertos, tipo y destino.
  4. **Threads** — LWPs con CPU% y context switches.
  5. **Señales** — máscaras decodificadas (bloqueadas, ignoradas, capturadas, pendientes).
  6. **Scheduling** — nice, priority, policy, affinity, context switches.
  7. **Sistema** — CPU global, memoria, load average, uptime, tops.

- Navegación en vivo: cambio de vista, ordenamiento, pin de proceso, filtros por comando/usuario y ajuste de intervalos.
- Modo verbose (toggle con `SIGUSR2`) que expande columnas y muestra más detalle.
- Shutdown limpio ante `SIGINT`/`SIGTERM`, reload de config con `SIGHUP`, dump a JSON con `SIGUSR1`.

---

## Arquitectura

```
┌─────────────────────────────────────────┐
│           SNAPSHOT GLOBAL               │
│      (Manager.dict compartido)          │
│  ┌───────────────────────────────────┐  │
│  │ "summary"   : {...}  ts: ...      │  │
│  │ "cpu"       : {...}  ts: ...      │  │
│  │ "memory"    : {...}  ts: ...      │  │
│  │ "fds"       : {...}  ts: ...      │  │
│  │ "threads"   : {...}  ts: ...      │  │
│  │ "signals"   : {...}  ts: ...      │  │
│  │ "scheduling": {...}  ts: ...      │  │
│  │ "sistema"   : {...}  ts: ...      │  │
│  └───────────────────────────────────┘  │
└────────▲─────────────────────▲──────────┘
         │ escriben            │ lee
┌────────┼─────────┬───────────┴─────────┐
│        │         │                     │
┌─▼───┐ ┌─▼────┐ ┌─▼─────┐  ...  ┌──────▼─────┐
│Resum│ │Memori│ │FDs    │       │   Display  │
│2s   │ │3s    │ │5s     │       │  (TUI rich)│
└─────┘ └──────┘ └───────┘       └────────────┘

Recolector ──► shared_pids (Manager.list)
```

Componentes:

| Proceso | Responsabilidad |
|---------|-----------------|
| **main** | Orquestador: maneja señales, teclado, ajusta intervalos, coordina shutdown |
| **recolector** | Lista PIDs desde `/proc` y publica en `shared_pids` cada 2 s |
| **7 analizadores** | Cada uno lee `/proc` para una dimensión y escribe su clave en el snapshot |
| **display** | Renderiza la vista activa leyendo el snapshot; es otro proceso hijo |

Comunicación:
- `shared_pids` → `Manager.list` (todos los analizadores leen la misma lista).
- `snapshot` → `Manager.dict` con 8 claves, una por dimensión.
- Intervalos → `multiprocessing.Value('d')` por analizador (ajustable en caliente con `+`/`-`).
- `shutdown_event` → `multiprocessing.Event` para shutdown limpio.

---

## Decisiones de diseño

### ¿Por qué `Manager` y no `Value`/`Array` para el snapshot?

La cantidad de procesos es **variable** (nacen y mueren). `Array` es de tamaño fijo, así que habría que sobre-reservar y llevar un contador. `Manager.list` y `Manager.dict` crecen dinámicamente. Además, el snapshot es una estructura anidada (`snapshot["memory"]["data"][pid]["vm_rss"]`) que `Value`/`Array` no soportan de forma natural.

La contrapartida es que el `Manager` vive en un proceso servidor aparte; cada acceso al proxy viaja por IPC. Ese costo es aceptable porque los datos de `/proc` ya son una caché del kernel y los volúmenes son pequeños (~300–800 procesos).

### ¿Por qué no `Queue` para distribuir PIDs?

Una `Queue` consume el ítem con `get()`: si le pasamos la lista de PIDs a un analizador, los otros 6 no la reciben. La lista de PIDs es **estado compartido que todos leen**, no trabajo a repartir. Por eso `Manager.list` con reemplazo in-place (`shared_pids[:] = nuevos_pids`).

### ¿Por qué `fork` explícito?

`multiprocessing.set_start_method("fork")` tiene dos ventajas clave para este diseño:
1. Los hijos heredan los **proxies del Manager** sin necesidad de serializarlos con pickle.
2. Los hijos heredan la instancia de `ProcFS` y el estado del módulo ya cargado.

Con `spawn`, cada hijo recrearía el intérprete y el `Manager` necesitaría que todo sea pickleable (incluyendo proxies y bound methods, que no lo son).

### ¿Cómo se evitan race conditions?

Cada campo del estado compartido tiene **un único escritor**:

| Campo | Escritor |
|-------|----------|
| `snapshot["summary"]` | AnalyzerSummary |
| `snapshot["memory"]` | AnalyzerMemory |
| ... | ... |
| `ui.active_view` | main (teclado) |
| `ui.intervals[i]` | main (teclado) |
| `ui.row_count` | display |
| `ui.pid_at_selected` | display |

Como hay un solo escritor por campo, no hace falta lock: lo peor que puede pasar es leer un valor viejo durante un frame, y se autocorrige en el siguiente.

El único lugar con múltiples lectores/escritores es el `Manager.dict` mismo, pero sus operaciones top-level ya están serializadas internamente por el proceso Manager.

### Patrón de escritura en analizadores

Los proxies de `Manager.dict` no propagan mutaciones anidadas. `snapshot["memory"]["data"][pid] = x` **no viaja**. Por eso cada analizador construye un dict local normal y hace una única asignación top-level:

```python
self.snapshot["memory"] = {"ts": time.time(), "data": data}
```

### Shutdown limpio

- `main` pone `SIGINT = SIG_IGN` **antes** de crear hijos → los 9 hijos nacen ignorando `SIGINT` sin ventana de race.
- `SIGTERM` queda en default (`SIG_DFL`) en los hijos a propósito: es la palanca de `main` para terminarlos con `p.terminate()` si no salen solos.
- Recién después `main` instala su handler con el patrón **self-pipe**: el handler de señal solo escribe un byte en un pipe; el loop principal de `main` lee ese byte con `select` y decide la acción. Esto es async-signal-safe y evita que el handler haga cosas complejas.

### Degradación con gracia ante `PermissionError`

Muchos archivos de `/proc` (como `/proc/<pid>/fd/*`) están protegidos por ptrace. Como usuario común, leer procesos ajenos da `PermissionError`. El monitor no exige `sudo`: saltea esos procesos con `continue` y muestra lo que puede. Esto es consistente con `ps aux`, que también muestra parcialmente.

### TUI desacoplada de la librería

Se eligió `rich` por expresividad y menos boilerplate que `curses`, pero el acoplamiento es mínimo:
- Las **vistas** son funciones puras `snapshot → ViewTable` (testeables sin terminal).
- `IRenderer` define una interfaz neutra: `start()` / `render(view)` / `stop()`.
- `RichRenderer` es la única implementación que importa `rich`.

Si en el futuro se quiere cambiar a `curses` o `blessed`, solo se reemplaza `RichRenderer`.

### Intervalos por defecto

Los defaults vienen de la consigna y reflejan el costo relativo de cada dimensión:

| Vista | Default | Mínimo | Razón |
|-------|---------|--------|-------|
| Resumen | 2 s | 0.5 s | Datos ligeros (solo `status`) |
| Memoria | 3 s | 1 s | Lee `status` + `stat` + `maps` |
| FDs | 5 s | 2 s | Recorre symlinks de `/proc/<pid>/fd/*` |
| Threads | 2 s | 0.5 s | Recorre `/proc/<pid>/task/*` |
| Señales | 10 s | 5 s | Máscaras hexadecimales pesadas de parsear |
| Scheduling | 10 s | 5 s | Lee `stat` + `schedstat` + `status` |
| Sistema | 2 s | 1 s | Lee archivos globales (`/proc/stat`, `/proc/meminfo`) |

---

## Conceptos del curso aplicados

- **fork() y COW**: por eso no basta con un `dict` normal entre procesos. El fork comparte páginas hasta la primera escritura, que las divorcia. Si cada analizador escribiera en un `dict` normal, cada uno tendría su copia privada y el display no vería nada. El `Manager.dict` resuelve esto poniendo los datos en un proceso servidor aparte.

- **Proceso vs Thread**: los 7 analizadores son **procesos**, no threads. La consigna exige arquitectura multiproceso, y además el GIL de Python serializaría threads CPU-bound (parseo de `/proc`). Como procesos, cada uno tiene su propio GIL y corren en paralelo real sobre distintos cores.

- **Estados de proceso (R/S/D/T/Z)**: se leen del campo 3 de `/proc/<pid>/stat`. En la vista Sistema se cuentan explícitamente para mostrar cuántos hay en cada estado. Los procesos en estado **Z** (zombie) aparecen en el listado porque todavía tienen entrada en `/proc` — su padre no hizo `wait()` aún.

- **CPU% con delta de jiffies**: no existe un archivo que diga "este proceso usa X% de CPU". Se calcula como `(jiffies_ahora - jiffies_antes) / clk_tck / segundos * 100`. Eso requiere estado entre ciclos (`_prev`) y explica por qué el primer frame muestra `None`.

- **Señales**: se usaron máscaras de 64 bits (`SigBlk`, `SigIgn`, `SigCgt`) y se decodificaron a nombres (`SIGTERM`, `SIGINT`) bit a bit. El patrón self-pipe garantiza que el handler sea async-signal-safe.

- **Context switches voluntarios vs involuntarios**: se leen de `voluntary_ctxt_switches` y `nonvoluntary_ctxt_switches` en `/proc/<pid>/status`. Los CPU-bound tienen muchos involuntarios porque el scheduler los saca de la CPU cuando se acaba su quantum.

- **Memoria virtual**: la vista Memoria muestra `VmSize` (virtual total), `VmRSS` (residente real), `VmData` (data+heap), `VmStk` (stack), etc. Esto conecta con el modelo de memoria virtual visto en clase (heap/stack/text/data).

---

## Limitaciones conocidas

- Sin `sudo` / `CAP_SYS_PTRACE`, no se pueden leer los FDs de procesos ajenos (`/proc/<pid>/fd/*` devuelve `PermissionError`). El monitor saltea esos procesos con gracia.
- El **primer ciclo** de cada analizador que usa deltas (CPU%, scheduling, memory faults) muestra `None` porque necesita una lectura previa para calcular la diferencia.
- El **pin de proceso** y el scroll pueden tener 1 frame de atraso en la publicación de `row_count` / `pid_at_selected` desde el display hacia main. Es aceptable porque es solo presentación.
- Los **tops por CPU/memoria** se derivan del snapshot actual; pueden estar desfasados 1–2 segundos respecto al estado real.
- No implementa modo daemon, jerarquía tipo `pstree`, ni histórico de series temporales.

---

## Cómo correr y testear

### Local (requiere Linux)

```bash
cd Computacion_II/tp1
python3 -m src.main
```

### Con Docker

La aplicación es **interactiva** (recibe teclas en tiempo real). Por eso hay que usar `docker compose run`, que conecta el stdin del host al contenedor. `docker compose up` no pasa el teclado.

```bash
cd Computacion_II/tp1
docker compose run --rm monitor
```

Si querés forzar el rebuild antes de arrancar:

```bash
docker compose run --rm --build monitor
```

> El contenedor necesita `tty: true`, `stdin_open: true` y `pid: host` para que la TUI reciba teclas y pueda ver los procesos del host.

### Tests

```bash
cd Computacion_II/tp1
python3 -m pytest tests/ -q
```

Suite actual: **234+ tests unitarios** + tests de integración.

---

## Decisiones sobre la TUI

- **Rich** se eligió por expresividad (tablas con estilos, colores, Live) y menos código repetitivo que `curses`.
- **Separación vista/renderer**: las funciones en `vista.py` son puras y no saben de rich. `RichRenderer` es la única que importa la librería. Esto permite testear la lógica de presentación sin abrir una terminal.
- **ViewTable**: un dataclass con columnas, filas, título y timestamp. El renderer recibe esto y lo traduce a una `rich.Table`. Las vistas no saben qué renderer las dibuja.

---

## Lo que aprendí

El gotcha que más me costó entender fue el **proxy del Manager**: pensaba que podía mutar un dict anidado directamente (`snapshot["k"][pid] = x`) y que el cambio se vería en los demás procesos, pero no viaja. El proxy solo intercepta operaciones top-level, así que hay que construir un dict local y reasignar la clave entera. Eso me hizo replantear cómo estructurar los analizadores para que cada uno arme su dimensión completa antes de publicar.

Otro punto clave fue el manejo de **señales con fork**. No es lo mismo poner `SIG_IGN` antes o después de crear hijos: si lo hacés después, hay una ventana de race donde los hijos pueden morir antes de que les llegue la señal. Aprendí que la disposición se hereda, y que dejar `SIGTERM` en default en los hijos es una palanca útil para que el padre pueda terminarlos limpiamente con `terminate()`.

También me sorprendió descubrir que el **load average de Linux incluye procesos en D-state** (uninterruptible sleep), no solo los que están corriendo o esperando CPU. Eso explica por qué a veces el load está alto pero el uso de CPU es bajo: hay tareas bloqueadas en I/O.

Por último, entender por qué `spawn` no servía para este diseño me clarificó cómo funciona **pickle en multiprocessing**. Con `spawn`, los argumentos del `Process` se serializan, y los bound methods y los proxies del Manager no son pickleables. Eso nos llevó a usar `fork` explícito y funciones libres como `target`, lo que simplificó mucho el cableado.
