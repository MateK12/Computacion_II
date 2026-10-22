import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.models import TareaResponse

logger = logging.getLogger(__name__)


def generar_nombre_archivo() -> str:
    """Genera un nombre de archivo con timestamp UTC para el volcado."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"estado_{timestamp}.json"


def guardar_snapshot(
    tareas: list[TareaResponse], directorio: Path | str = "."
) -> Path:
    """Serializa la colección de tareas y la guarda en un archivo JSON."""
    dir_path = Path(directorio)
    dir_path.mkdir(parents=True, exist_ok=True)

    archivo = dir_path / generar_nombre_archivo()
    payload = [tarea.model_dump(mode="json") for tarea in tareas]

    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info("Snapshot persistido exitosamente en %s (%d tareas)", archivo, len(tareas))
    return archivo


def buscar_volcados_previos(directorio: Path | str = ".") -> list[Path]:
    """Retorna la lista de volcados previos ordenados cronológicamente por nombre."""
    dir_path = Path(directorio)
    if not dir_path.exists():
        return []
    return sorted(dir_path.glob("estado_*.json"))


def reportar_volcados_previos(directorio: Path | str = ".") -> list[Path]:
    """Busca volcados previos y emite un log informativo si existen."""
    volcados = buscar_volcados_previos(directorio)
    if volcados:
        logger.info(
            "Se detectaron %d volcado(s) previo(s) de estado en %s. Último: %s",
            len(volcados),
            directorio,
            volcados[-1].name,
        )
    return volcados
