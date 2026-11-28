
import pytest

from app.schemas.taller import Taller
from app.services.validacion import (
    horarios_superpuestos,
    validar_talleres
)


def registro(fila=2, **cambios):

    datos = {
        "area": "AOS",
        "nombre": "Taller A",
        "tutor": "Tutor A",
        "destinatarios": "Todas las Facultades",
        "descripcion": "Descripción",
        "semana": 39,
        "fecha": "2026-09-23",
        "dia": "Miércoles",
        "hora_inicio": "11:25",
        "hora_fin": "12:45",
        "sala": "Sala 12",
        "estado": "Vigente"
    }

    datos.update(cambios)

    return {
        "fila": fila,
        "taller": Taller(**datos)
    }


def evaluar(*registros, errores=None, semana_iso=False):

    return validar_talleres(
        {
            "talleres": list(registros),
            "errores": errores if errores is not None else []
        },
        semana_iso=semana_iso
    )


def codigos(resultado):

    return {
        alerta["codigo"]
        for alerta in resultado["alertas"]
    }


def test_lote_valido():

    r = registro()

    resultado = evaluar(r)

    assert resultado["sin_errores_bloqueantes"] is True
    assert resultado["alertas"] == []
    assert resultado["talleres"] == [r]


def test_dia_inconsistente():

    resultado = evaluar(registro(dia="Lunes"))

    assert codigos(resultado) == {"DIA_INCONSISTENTE"}
    assert resultado["alertas"][0]["filas"] == [2]
    assert not resultado["sin_errores_bloqueantes"]


@pytest.mark.parametrize("inicio,fin,esperado", [
    ("12:00", "13:30", True),
    ("10:00", "11:25", False),
    ("12:45", "13:30", False),
    ("11:30", "12:00", True),
    ("11:25", "12:45", True),
    ("13:00", "14:00", False)
])
def test_superposicion(inicio, fin, esperado):

    a = registro()["taller"]

    b = registro(
        hora_inicio=inicio,
        hora_fin=fin
    )["taller"]

    assert horarios_superpuestos(a, b) is esperado


def test_conflicto_sala():

    resultado = evaluar(
        registro(),
        registro(
            3,
            nombre="Taller B",
            tutor="Tutor B",
            sala="  SALA   12 ",
            hora_inicio="12:00",
            hora_fin="13:30"
        )
    )

    assert codigos(resultado) == {"CONFLICTO_SALA"}
    assert resultado["alertas"][0]["filas"] == [2, 3]
    assert not resultado["sin_errores_bloqueantes"]


def test_conflicto_tutor():

    resultado = evaluar(
        registro(),
        registro(
            3,
            nombre="Taller B",
            sala="Sala 13"
        )
    )

    assert codigos(resultado) == {"CONFLICTO_TUTOR"}


def test_duplicados():

    resultado = evaluar(
        registro(),
        registro(3, nombre="  TALLER   A "),
        registro(4)
    )

    assert codigos(resultado) == {"TALLER_DUPLICADO"}
    assert resultado["alertas"][0]["filas"] == [2, 3, 4]
    assert len(resultado["talleres"]) == 3
    assert not resultado["sin_errores_bloqueantes"]


def test_fechas_distintas():

    resultado = evaluar(
        registro(),
        registro(
            3,
            fecha="2026-09-24",
            dia="Jueves"
        )
    )

    assert resultado["alertas"] == []


def test_suspendido():

    resultado = evaluar(
        registro(),
        registro(
            3,
            nombre="Taller B",
            estado="Suspendido"
        )
    )

    assert resultado["alertas"] == []


def test_advertencias():

    resultado = evaluar(
        registro(
            sala=None,
            estado=None
        )
    )

    assert codigos(resultado) == {
        "SALA_NO_ASIGNADA",
        "ESTADO_NO_INFORMADO"
    }

    assert all(
        alerta["severidad"] == "advertencia"
        for alerta in resultado["alertas"]
    )

    assert resultado["sin_errores_bloqueantes"]


def test_salas_desconocidas_no_colisionan():

    resultado = evaluar(
        registro(sala="-"),
        registro(
            3,
            nombre="Taller B",
            tutor="Tutor B",
            sala="-"
        )
    )

    assert codigos(resultado) == {"SALA_NO_ASIGNADA"}
    assert len(resultado["alertas"]) == 2


def test_error_normalizacion_bloquea():

    errores = [
        {
            "fila": 3,
            "datos": {"horario": "mal"},
            "errores": ["horario inválido"]
        }
    ]

    resultado = evaluar(
        registro(),
        errores=errores
    )

    assert resultado["errores_normalizacion"] == errores
    assert not resultado["sin_errores_bloqueantes"]


def test_lote_vacio():

    resultado = evaluar()

    assert codigos(resultado) == {"SIN_TALLERES"}
    assert not resultado["sin_errores_bloqueantes"]


def test_semana_iso_opcional():

    r = registro(semana=4)

    assert evaluar(r)["alertas"] == []

    assert codigos(
        evaluar(r, semana_iso=True)
    ) == {"SEMANA_INCONSISTENTE"}


def test_conflictos_simultaneos():

    resultado = evaluar(
        registro(),
        registro(3, nombre="Taller B")
    )

    assert codigos(resultado) == {
        "CONFLICTO_SALA",
        "CONFLICTO_TUTOR"
    }


def test_dia_sin_tilde():

    resultado = evaluar(
        registro(dia=" MIERCOLES ")
    )

    assert resultado["alertas"] == []


def test_no_modificar_talleres():

    r = registro(dia="Lunes")

    antes = r["taller"].model_dump()

    evaluar(r)

    assert r["taller"].model_dump() == antes
