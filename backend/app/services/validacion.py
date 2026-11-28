
import unicodedata
from itertools import combinations
from typing import Literal, TypedDict

from app.schemas.taller import Taller
from app.services.normalizacion import (
    FilaConError,
    ResultadoNormalizacion,
    TallerNormalizado,
)


Severidad = Literal["error", "advertencia"]

DIAS = (
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
)

ESTADOS_SUSPENDIDOS = {
    "suspendido",
    "suspendida"
}


class AlertaValidacion(TypedDict):
    codigo: str
    severidad: Severidad
    filas: list[int]
    mensaje: str


class ResultadoValidacion(TypedDict):
    talleres: list[TallerNormalizado]
    errores_normalizacion: list[FilaConError]
    alertas: list[AlertaValidacion]
    sin_errores_bloqueantes: bool


def clave_texto(valor: str | None) -> str:

    return " ".join(
        unicodedata.normalize("NFC", valor or "").split()
    ).casefold()


def crear_alerta(
    codigo: str,
    severidad: Severidad,
    filas: list[int],
    mensaje: str
) -> AlertaValidacion:

    return {
        "codigo": codigo,
        "severidad": severidad,
        "filas": sorted(filas),
        "mensaje": mensaje
    }


def esta_suspendido(taller: Taller) -> bool:

    return clave_texto(taller.estado) in ESTADOS_SUSPENDIDOS


def clave_duplicado(taller: Taller) -> tuple:

    return (
        clave_texto(taller.area),
        clave_texto(taller.nombre),
        clave_texto(taller.tutor),
        clave_texto(taller.destinatarios),
        taller.fecha,
        taller.hora_inicio,
        taller.hora_fin,
    )


def horarios_superpuestos(a: Taller, b: Taller) -> bool:

    return (
        a.fecha == b.fecha
        and a.hora_inicio < b.hora_fin
        and b.hora_inicio < a.hora_fin
    )


def validar_individual(
    registro: TallerNormalizado,
    *,
    semana_iso: bool = False
) -> list[AlertaValidacion]:

    taller = registro["taller"]
    fila = registro["fila"]

    alertas: list[AlertaValidacion] = []

    # Comprobar correspondencia entre fecha y día
    dia_esperado = DIAS[taller.fecha.weekday()]

    dia_recibido = (
        clave_texto(taller.dia)
        .replace("é", "e")
        .replace("á", "a")
    )

    if dia_recibido != dia_esperado:

        alertas.append(crear_alerta(
            "DIA_INCONSISTENTE",
            "error",
            [fila],
            f"La fecha {taller.fecha} corresponde a "
            f"{dia_esperado}, no a {taller.dia}."
        ))

    # Validación opcional de semana ISO
    if semana_iso and taller.semana != taller.fecha.isocalendar().week:

        alertas.append(crear_alerta(
            "SEMANA_INCONSISTENTE",
            "error",
            [fila],
            f"Semana ISO esperada: "
            f"{taller.fecha.isocalendar().week}. "
            f"Recibida: {taller.semana}."
        ))

    # Comprobar estado del taller
    if not clave_texto(taller.estado):

        alertas.append(crear_alerta(
            "ESTADO_NO_INFORMADO",
            "advertencia",
            [fila],
            "El taller no tiene un estado informado."
        ))

    # Comprobar asignación de sala
    if (
        not esta_suspendido(taller)
        and clave_texto(taller.sala) in ("", "-")
    ):

        alertas.append(crear_alerta(
            "SALA_NO_ASIGNADA",
            "advertencia",
            [fila],
            "El taller no tiene una sala informada. "
            "Revisar modalidad."
        ))

    return alertas


def detectar_duplicados(
    registros: list[TallerNormalizado]
) -> list[AlertaValidacion]:

    grupos: dict[tuple, list[int]] = {}

    for registro in registros:

        clave = clave_duplicado(registro["taller"])

        grupos.setdefault(clave, []).append(
            registro["fila"]
        )

    return [
        crear_alerta(
            "TALLER_DUPLICADO",
            "error",
            filas,
            "Registros con la misma identidad provisional de taller."
        )
        for filas in grupos.values()
        if len(filas) > 1
    ]


def detectar_conflictos(
    registros: list[TallerNormalizado]
) -> list[AlertaValidacion]:

    activos = [
        registro
        for registro in registros
        if not esta_suspendido(registro["taller"])
    ]

    alertas: list[AlertaValidacion] = []

    for primero, segundo in combinations(activos, 2):

        a = primero["taller"]
        b = segundo["taller"]

        filas = [
            primero["fila"],
            segundo["fila"]
        ]

        if not horarios_superpuestos(a, b):
            continue

        # Evitar alertas redundantes entre duplicados
        if clave_duplicado(a) == clave_duplicado(b):
            continue

        sala_a = clave_texto(a.sala)

        # Conflicto de sala
        if (
            sala_a not in ("", "-")
            and sala_a == clave_texto(b.sala)
        ):

            alertas.append(crear_alerta(
                "CONFLICTO_SALA",
                "error",
                filas,
                f"Horarios superpuestos en {a.sala}."
            ))

        # Conflicto de tutor
        if clave_texto(a.tutor) == clave_texto(b.tutor):

            alertas.append(crear_alerta(
                "CONFLICTO_TUTOR",
                "error",
                filas,
                f"Horarios superpuestos para {a.tutor}."
            ))

    return alertas


def validar_talleres(
    resultado: ResultadoNormalizacion,
    *,
    semana_iso: bool = False
) -> ResultadoValidacion:

    talleres = resultado["talleres"]
    errores = resultado["errores"]

    alertas: list[AlertaValidacion] = []

    if not talleres:

        alertas.append(crear_alerta(
            "SIN_TALLERES",
            "error",
            [],
            "No existen talleres normalizados para procesar."
        ))

    for registro in talleres:

        alertas.extend(
            validar_individual(
                registro,
                semana_iso=semana_iso
            )
        )

    alertas.extend(detectar_duplicados(talleres))
    alertas.extend(detectar_conflictos(talleres))

    sin_errores = (
        not errores
        and not any(
            alerta["severidad"] == "error"
            for alerta in alertas
        )
    )

    return {
        "talleres": talleres.copy(),
        "errores_normalizacion": errores.copy(),
        "alertas": alertas,
        "sin_errores_bloqueantes": sin_errores
    }
