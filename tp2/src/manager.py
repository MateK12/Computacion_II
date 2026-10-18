from uuid import UUID

from src.models import (
    EstadisticasResponse,
    EstadoTarea,
    TareaResponse,
)


class TaskManager:
    """Gestiona el almacenamiento y ciclo de vida de las tareas en memoria."""

    def __init__(self) -> None:
        self._tareas: dict[UUID, TareaResponse] = {}

    def guardar(self, tarea: TareaResponse) -> TareaResponse:
        """Almacena o actualiza una tarea en el repositorio."""
        self._tareas[tarea.id] = tarea
        return tarea

    def obtener(self, tarea_id: UUID) -> TareaResponse | None:
        """Obtiene una tarea por su identificador único."""
        return self._tareas.get(tarea_id)

    def listar(
        self, estado: EstadoTarea | None = None
    ) -> list[TareaResponse]:
        """Lista las tareas almacenadas, con filtrado opcional por estado."""
        if estado is not None:
            return [t for t in self._tareas.values() if t.estado == estado]
        return list(self._tareas.values())

    def eliminar(self, tarea_id: UUID) -> bool:
        """Elimina una tarea por su ID. Retorna True si existía y fue removida."""
        return self._tareas.pop(tarea_id, None) is not None

    def limpiar(self) -> None:
        """Limpia todo el almacén de tareas (útil para tests o reinicio)."""
        self._tareas.clear()

    def clear(self) -> None:
        """Alias de limpiar() para compatibilidad con interfaces de mapping/dict."""
        self.limpiar()

    def get(
        self, tarea_id: UUID, default: TareaResponse | None = None
    ) -> TareaResponse | None:
        """Alias de obtener() con soporte para valor por defecto."""
        return self._tareas.get(tarea_id, default)

    def __getitem__(self, tarea_id: UUID) -> TareaResponse:
        return self._tareas[tarea_id]

    def __setitem__(self, tarea_id: UUID, tarea: TareaResponse) -> None:
        self._tareas[tarea_id] = tarea

    def __contains__(self, tarea_id: UUID) -> bool:
        return tarea_id in self._tareas

    def __len__(self) -> int:
        return len(self._tareas)

    def values(self) -> list[TareaResponse]:
        """Retorna una lista con todas las tareas registradas."""
        return list(self._tareas.values())


def calcular_estadisticas(tareas: list[TareaResponse]) -> EstadisticasResponse:
    """Calcula las métricas consolidadas del sistema a partir de una colección de tareas."""
    total = len(tareas)
    pendientes = sum(1 for t in tareas if t.estado == EstadoTarea.PENDIENTE)
    ejecutando = sum(1 for t in tareas if t.estado == EstadoTarea.EJECUTANDO)
    completadas = sum(1 for t in tareas if t.estado == EstadoTarea.COMPLETADA)
    fallidas = sum(1 for t in tareas if t.estado == EstadoTarea.FALLIDA)
    canceladas = sum(1 for t in tareas if t.estado == EstadoTarea.CANCELADA)

    duraciones = [
        t.duracion_segundos
        for t in tareas
        if t.duracion_segundos is not None
    ]
    tiempo_promedio = (
        round(sum(duraciones) / len(duraciones), 4) if duraciones else 0.0
    )

    return EstadisticasResponse(
        total=total,
        pendientes=pendientes,
        ejecutando=ejecutando,
        completadas=completadas,
        fallidas=fallidas,
        canceladas=canceladas,
        tiempo_promedio_ejecucion_segundos=tiempo_promedio,
    )
