from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from src.manager import TaskManager, calcular_estadisticas
from src.models import EstadoTarea, TareaResponse, TipoTarea


def test_task_manager_guardar_y_obtener():
    manager = TaskManager()
    tarea = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 1.0},
        estado=EstadoTarea.PENDIENTE,
    )

    manager.guardar(tarea)

    assert len(manager) == 1
    assert manager.obtener(tarea.id) == tarea
    assert manager.obtener(uuid4()) is None


def test_task_manager_listar_con_y_sin_filtro():
    manager = TaskManager()
    t1 = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 1.0},
        estado=EstadoTarea.PENDIENTE,
    )
    t2 = TareaResponse(
        tipo=TipoTarea.HASHEAR,
        parametros={"texto": "abc", "iteraciones": 10},
        estado=EstadoTarea.COMPLETADA,
    )
    manager.guardar(t1)
    manager.guardar(t2)

    assert len(manager.listar()) == 2
    assert manager.listar(estado=EstadoTarea.PENDIENTE) == [t1]
    assert manager.listar(estado=EstadoTarea.COMPLETADA) == [t2]
    assert manager.listar(estado=EstadoTarea.FALLIDA) == []


def test_task_manager_eliminar_y_limpiar():
    manager = TaskManager()
    tarea = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 1.0},
    )
    manager.guardar(tarea)

    assert manager.eliminar(tarea.id) is True
    assert manager.eliminar(tarea.id) is False
    assert len(manager) == 0

    manager.guardar(tarea)
    manager.limpiar()
    assert len(manager) == 0


def test_calcular_estadisticas_vacio():
    stats = calcular_estadisticas([])
    assert stats.total == 0
    assert stats.pendientes == 0
    assert stats.ejecutando == 0
    assert stats.completadas == 0
    assert stats.fallidas == 0
    assert stats.canceladas == 0
    assert stats.tiempo_promedio_ejecucion_segundos == 0.0


def test_calcular_estadisticas_con_datos():
    ahora = datetime.now(timezone.utc)
    t1 = TareaResponse(
        tipo=TipoTarea.ESPERAR,
        parametros={"segundos": 2.0},
        estado=EstadoTarea.COMPLETADA,
        iniciada_en=ahora,
        finalizada_en=ahora + timedelta(seconds=2.0),
    )
    t2 = TareaResponse(
        tipo=TipoTarea.HASHEAR,
        parametros={"texto": "test", "iteraciones": 100},
        estado=EstadoTarea.COMPLETADA,
        iniciada_en=ahora,
        finalizada_en=ahora + timedelta(seconds=4.0),
    )
    t3 = TareaResponse(
        tipo=TipoTarea.DESCARGAR,
        parametros={"urls": ["http://test"]},
        estado=EstadoTarea.FALLIDA,
        error="Network error",
    )

    stats = calcular_estadisticas([t1, t2, t3])
    assert stats.total == 3
    assert stats.completadas == 2
    assert stats.fallidas == 1
    assert stats.pendientes == 0
    # Promedio entre 2.0s y 4.0s = 3.0s
    assert stats.tiempo_promedio_ejecucion_segundos == 3.0
