from datetime import date, time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

class Taller(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

    # Información general
    area: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    tutor: str = Field(min_length=1)
    destinatarios: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)

    # Información de planificación
    semana: int = Field(ge=1, le=53)
    fecha: date
    dia: str = Field(min_length=1)
    hora_inicio: time
    hora_fin: time

    # Información administrativa
    observaciones: str | None = None
    sala: str | None = None
    estado: str | None = None
    total_participantes: int | None = Field(default=None, ge=0)
    ingresado_permanencia: bool | None = None
    revision_linktree: str | None = None


    @model_validator(mode="after")
    def validar_horario(self) -> Self:
        if self.hora_fin <= self.hora_inicio:
            raise ValueError(
                "La hora de término debe ser posterior a la de inicio."
                )
        
        return self