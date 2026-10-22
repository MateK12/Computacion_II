import json
import logging
from pathlib import Path
from uuid import uuid4

import pytest

from src.models import EstadoTarea, TareaResponse, TipoTarea
from src.persistencia import (
    buscar_volcados_previos,
    generar_nombre_archivo,
    guardar_snapshot,
    reportar_volcados_previos,
)


def test_generar_nombre_archivo():
    nombre = generar_nombre_archivo()
    assert nombre.startswith("estado_")
    assert nombre.endswith(".json")


def test_guardar_snapshot_crea_archivo_valido(tmp_path: Path):
    tarea1 = TareaResponse(
        id=uuid4(),
        tipo=TipoTarea.ESPERAR,
        estado=EstadoTarea.COMPLETADA,
        parametros={"segundos": 1.0},
        resultado={"mensaje": "ok"},
    )
    tarea2 = TareaResponse(
        id=uuid4(),
        tipo=TipoTarea.DESCARGAR,
        estado=EstadoTarea.CANCELADA,
        parametros={"urls": ["http://test.com"]},
    )

    archivo = guardar_snapshot([tarea1, tarea2], directorio=tmp_path)

    assert archivo.exists()
    assert archivo.parent == tmp_path
    assert archivo.name.startswith("estado_")

    contenido = json.loads(archivo.read_text(encoding="utf-8"))
    assert len(contenido) == 2
    assert contenido[0]["id"] == str(tarea1.id)
    assert contenido[0]["estado"] == "completada"
    assert contenido[0]["resultado"] == {"mensaje": "ok"}
    assert contenido[1]["id"] == str(tarea2.id)
    assert contenido[1]["estado"] == "cancelada"


def test_guardar_snapshot_lista_vacia(tmp_path: Path):
    archivo = guardar_snapshot([], directorio=tmp_path)
    assert archivo.exists()
    contenido = json.loads(archivo.read_text(encoding="utf-8"))
    assert contenido == []


def test_buscar_volcados_previos(tmp_path: Path):
    # Sin archivos previos
    assert buscar_volcados_previos(tmp_path) == []

    # Crear archivos con nombres cronológicos
    f1 = tmp_path / "estado_20261020_100000.json"
    f2 = tmp_path / "estado_20261021_120000.json"
    otro = tmp_path / "otro_archivo.txt"

    f1.write_text("[]", encoding="utf-8")
    f2.write_text("[]", encoding="utf-8")
    otro.write_text("nada", encoding="utf-8")

    encontrados = buscar_volcados_previos(tmp_path)
    assert encontrados == [f1, f2]


def test_buscar_volcados_directorio_inexistente(tmp_path: Path):
    no_existe = tmp_path / "sub_inexistente"
    assert buscar_volcados_previos(no_existe) == []


def test_reportar_volcados_previos_con_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    f1 = tmp_path / "estado_20261022_150000.json"
    f1.write_text("[]", encoding="utf-8")

    with caplog.at_level(logging.INFO):
        volcados = reportar_volcados_previos(tmp_path)

    assert len(volcados) == 1
    assert "Se detectaron 1 volcado(s) previo(s)" in caplog.text
    assert f1.name in caplog.text


def test_reportar_volcados_previos_sin_archivos(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO):
        volcados = reportar_volcados_previos(tmp_path)

    assert len(volcados) == 0
    assert "Se detectaron" not in caplog.text
