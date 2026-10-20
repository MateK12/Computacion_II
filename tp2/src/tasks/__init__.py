from src.models import TipoTarea
from src.tasks.base import TareaStrategy
from src.tasks.descargar import DescargarStrategy
from src.tasks.esperar import EsperarStrategy
from src.tasks.hashear import HashearStrategy

REGISTRO_ESTRATEGIAS: dict[TipoTarea, TareaStrategy] = {}


def registrar_estrategia(tipo: TipoTarea, estrategia: TareaStrategy) -> None:
    """Registra una estrategia de ejecución asociada a un TipoTarea."""
    REGISTRO_ESTRATEGIAS[tipo] = estrategia


def obtener_estrategia(tipo: TipoTarea) -> TareaStrategy:
    """Obtiene la estrategia registrada para el tipo de tarea indicado."""
    estrategia = REGISTRO_ESTRATEGIAS.get(tipo)
    if not estrategia:
        raise ValueError(
            f"No hay ninguna estrategia registrada para el tipo '{tipo}'"
        )
    return estrategia


# Registro de estrategias por defecto
registrar_estrategia(TipoTarea.DESCARGAR, DescargarStrategy())
registrar_estrategia(TipoTarea.ESPERAR, EsperarStrategy())
registrar_estrategia(TipoTarea.HASHEAR, HashearStrategy())
