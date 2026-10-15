from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


class EstadoTarea(StrEnum):
    PENDIENTE = "pendiente"
    EJECUTANDO = "ejecutando"
    COMPLETADA = "completada"
    FALLIDA = "fallida"
    CANCELADA = "cancelada"


class TipoTarea(StrEnum):
    DESCARGAR = "descargar"
    HASHEAR = "hashear"
    ESPERAR = "esperar"


class TareaBaseCreate(BaseModel):
    timeout: float | None = Field(
        default=None,
        gt=0,
        description="Tiempo máximo de ejecución en segundos antes de forzar cancelación",
    )


class TareaDescargarCreate(TareaBaseCreate):
    tipo: Literal["descargar"] = "descargar"
    urls: list[str] = Field(
        ...,
        min_length=1,
        description="Lista de URLs a descargar concurrentemente",
    )


class TareaHashearCreate(TareaBaseCreate):
    tipo: Literal["hashear"] = "hashear"
    texto: str = Field(..., min_length=1, description="Texto base para hashear")
    iteraciones: int = Field(
        default=1_000_000,
        gt=0,
        description="Cantidad de iteraciones SHA-256 (CPU-bound)",
    )


class TareaEsperarCreate(TareaBaseCreate):
    tipo: Literal["esperar"] = "esperar"
    segundos: float = Field(
        ...,
        gt=0,
        description="Tiempo en segundos a suspender la tarea (I/O simulado)",
    )


TareaCreate = Annotated[
    Union[TareaDescargarCreate, TareaHashearCreate, TareaEsperarCreate],
    Field(discriminator="tipo"),
]


class TareaResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tipo: TipoTarea
    estado: EstadoTarea = EstadoTarea.PENDIENTE
    parametros: dict[str, Any]
    resultado: Any | None = None
    error: str | None = None
    creada_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    iniciada_en: datetime | None = None
    finalizada_en: datetime | None = None

    @computed_field
    @property
    def duracion_segundos(self) -> float | None:
        """Tiempo neto de ejecución por el worker."""
        if self.iniciada_en and self.finalizada_en:
            return round(
                (self.finalizada_en - self.iniciada_en).total_seconds(), 4
            )
        return None

    @computed_field
    @property
    def espera_en_cola_segundos(self) -> float | None:
        """Tiempo que la tarea esperó en cola antes de ser tomada por un worker."""
        if self.iniciada_en:
            return round((self.iniciada_en - self.creada_en).total_seconds(), 4)
        return None


class EstadisticasResponse(BaseModel):
    total: int
    pendientes: int
    ejecutando: int
    completadas: int
    fallidas: int
    canceladas: int
    tiempo_promedio_ejecucion_segundos: float = 0.0
