from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ViewTable:
    """Contrato de salida de toda vista: lo único que el renderer sabe dibujar.    """
    title: str
    columns: list
    rows: list = field(default_factory=list)   # una fila por proceso, mismas posiciones que columns
    ts: float | None = None                    # None si la dimensión aún no existe
