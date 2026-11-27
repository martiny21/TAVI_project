
import re
from datetime import date, datetime, time
from typing import TypedDict

from pydantic import ValidationError

from app.schemas.taller import Taller
from app.services.ingesta import FilaExcel, es_celda_vacia


class TallerNormalizado(TypedDict):
    fila: int
    taller: Taller


class FilaConError(TypedDict):
    fila: int
    datos: dict[str, object]
    errores: list[str]


class ResultadoNormalizacion(TypedDict):
    talleres: list[TallerNormalizado]
    errores: list[FilaConError]


def normalizar_fecha(valor: object) -> date:

    if isinstance(valor, datetime):
        if valor.time() != time(0, 0) or valor.tzinfo is not None:
            raise ValueError(
                "fecha: se esperaba una fecha sin hora ni zona horaria"
            )

        return valor.date()

    if isinstance(valor, date):
        return valor

    if isinstance(valor, str):
        for formato in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(valor.strip(), formato).date()
            except ValueError:
                continue

    raise ValueError("fecha: formato o valor inválido")


def normalizar_horario(valor: object) -> tuple[time, time]:

    if not isinstance(valor, str):
        raise ValueError("horario: se esperaba un texto")

    patron = (
        r"([0-9]{1,2}):([0-9]{2})"
        r"\s*(?:a|-|–)\s*"
        r"([0-9]{1,2}):([0-9]{2})"
    )

    coincidencia = re.fullmatch(
        patron,
        valor.strip(),
        flags=re.IGNORECASE
    )

    if coincidencia is None:
        raise ValueError("horario: formato inválido")

    hi, mi, hf, mf = map(int, coincidencia.groups())

    try:
        return time(hi, mi), time(hf, mf)

    except ValueError as error:
        raise ValueError(
            "horario: horas o minutos fuera de rango"
        ) from error


def normalizar_entero(valor: object, campo: str) -> int:

    if isinstance(valor, bool):
        raise ValueError(f"{campo}: no se acepta un booleano")

    if isinstance(valor, int):
        return valor

    if isinstance(valor, float) and valor.is_integer():
        return int(valor)

    if isinstance(valor, str) and re.fullmatch(
        r"[+-]?[0-9]+", valor.strip()
    ):
        return int(valor.strip())

    raise ValueError(f"{campo}: se esperaba un número entero")


def normalizar_participantes(valor: object) -> int | None:

    if es_celda_vacia(valor) or (
        isinstance(valor, str) and valor.strip() == "-"
    ):
        return None

    return normalizar_entero(valor, "total_participantes")


def normalizar_permanencia(valor: object) -> bool | None:

    if es_celda_vacia(valor):
        return None

    if isinstance(valor, bool):
        return valor

    if isinstance(valor, str):

        texto = valor.strip().casefold()

        if texto in ("sí", "si"):
            return True

        if texto == "no":
            return False

    raise ValueError(
        "ingresado_permanencia: se esperaba Sí o No"
    )


def normalizar_texto_opcional(
    valor: object,
    campo: str
) -> str | None:

    if es_celda_vacia(valor):
        return None

    if not isinstance(valor, str):
        raise ValueError(f"{campo}: se esperaba un texto")

    return valor.strip()


def normalizar_fila(registro: FilaExcel) -> Taller:

    datos = registro["datos"].copy()

    inicio, fin = normalizar_horario(
        datos.pop("horario", None)
    )

    datos["hora_inicio"] = inicio
    datos["hora_fin"] = fin

    datos["fecha"] = normalizar_fecha(datos.get("fecha"))

    datos["semana"] = normalizar_entero(
        datos.get("semana"),
        "semana"
    )

    datos["total_participantes"] = normalizar_participantes(
        datos.get("total_participantes")
    )

    datos["ingresado_permanencia"] = normalizar_permanencia(
        datos.get("ingresado_permanencia")
    )

    for campo in (
        "observaciones",
        "sala",
        "estado",
        "revision_linktree"
    ):
        datos[campo] = normalizar_texto_opcional(
            datos.get(campo),
            campo
        )

    return Taller.model_validate(datos)


def normalizar_filas(
    registros: list[FilaExcel]
) -> ResultadoNormalizacion:

    resultado: ResultadoNormalizacion = {
        "talleres": [],
        "errores": []
    }

    for registro in registros:

        try:
            taller = normalizar_fila(registro)

        except ValidationError as error:

            mensajes = [
                f"{'.'.join(map(str, e['loc'])) or 'taller'}: {e['msg']}"
                for e in error.errors()
            ]

        except ValueError as error:

            mensajes = [str(error)]

        else:

            resultado["talleres"].append({
                "fila": registro["fila"],
                "taller": taller
            })

            continue

        resultado["errores"].append({
            "fila": registro["fila"],
            "datos": registro["datos"].copy(),
            "errores": mensajes
        })

    return resultado
