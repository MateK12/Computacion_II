# Dudas y Registro Conceptual — TP2: Plataforma de Tareas Distribuidas

**Computación II — Universidad de Mendoza — 2026**

Este archivo registra las dudas conceptuales, casos borde y preguntas surgidas durante el desarrollo para llevar a consulta o discutir con el tutor.

---

## Plantilla de Duda

```markdown
### [Fecha] - [Tema o Concepto]
- **Contexto:** ¿Qué estaba intentando hacer o implementar?
- **La duda concreta:** ¿Qué comportamiento o concepto no me queda claro?
- **Hipótesis propia:** ¿Qué creo yo que está pasando antes de consultar?
- **Resolución:** ¿Qué aprendí tras verificar con código/documentación/profesores?
```

---

## Registro de Dudas

### 18/10/2026 - Sincronización en Memoria: ¿Por qué no usamos Lock en el diccionario de tareas?
- **Contexto:** Al tener la API FastAPI atendiendo múltiples peticiones concurrentes y un pool de 3 workers modificando el diccionario `tareas` en memoria.
- **La duda concreta:** ¿Por qué no ocurre una condición de carrera (race condition) ni se corrompe el diccionario en memoria si no usamos un `Lock`?
- **Hipótesis propia:** Pensar inicialmente que no hay conflicto porque cada worker procesa un `tarea_id` diferente que saca de la cola.
- **Resolución:** En Python con `asyncio`, el runtime ejecuta en un **único hilo** bajo **multitarea cooperativa**. Las corrutinas no son desalojadas arbitrariamente por el sistema operativo (no hay preemption de bytecode en un solo thread). Un cambio de contexto ocurre **exclusivamente** en puntos de `await`. Modificar o consultar un diccionario (`dict[id] = ...`) es código síncrono puro que se ejecuta de forma estrictamente atómica frente al event loop. Solo se requeriría un `asyncio.Lock` si existiera un punto de suspensión (`await`) intercalado entre la lectura y la actualización del estado.

