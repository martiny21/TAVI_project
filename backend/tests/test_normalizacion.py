
from datetime import date, datetime, time

import pytest

from app.services.normalizacion import (
    normalizar_fila,
    normalizar_filas
)


def fila_ejemplo():
    return {
        "fila": 2,
        "datos": {
            "area": "AOS",
            "nombre": "Taller A",
            "tutor": "Tutor A",
            "destinatarios": "Todas las Facultades",
            "descripcion": "Descripción",
            "semana": 39.0,
            "fecha": datetime(2026, 9, 23),
            "dia": "Miércoles",
            "horario": "11:25 a 12:45",
            "observaciones": "  ",
            "sala": "Sala 12",
            "estado": "  Vigente  ",
            "total_participantes": "-",
            "ingresado_permanencia": "No",
            "revision_linktree": "Ok"
        }
    }


def test_normalizar_fila():

    fila = fila_ejemplo()
    original = fila["datos"].copy()

    taller = normalizar_fila(fila)

    assert taller.fecha == date(2026, 9, 23)
    assert taller.hora_inicio == time(11, 25)
    assert taller.hora_fin == time(12, 45)
    assert taller.semana == 39
    assert taller.total_participantes is None
    assert taller.ingresado_permanencia is False
    assert taller.observaciones is None
    assert taller.estado == "Vigente"

    assert fila["datos"] == original


@pytest.mark.parametrize("fecha", [
    date(2026, 9, 23),
    "2026-09-23",
    "23/09/2026"
])
def test_formatos_fecha(fecha):

    fila = fila_ejemplo()
    fila["datos"]["fecha"] = fecha

    assert normalizar_fila(fila).fecha == date(2026, 9, 23)


def test_cero_y_si():

    fila = fila_ejemplo()
    fila["datos"]["total_participantes"] = 0
    fila["datos"]["ingresado_permanencia"] = " SÍ "

    taller = normalizar_fila(fila)

    assert taller.total_participantes == 0
    assert taller.ingresado_permanencia is True


@pytest.mark.parametrize("campo,valor,mensaje", [
    ("horario", "25:00 a 26:00", "horario"),
    ("horario", "15:00 a 14:00", "hora de término"),
    ("fecha", "31/02/2026", "fecha"),
    ("semana", 39.5, "semana"),
    ("total_participantes", -1, "total_participantes"),
    ("ingresado_permanencia", "Quizás", "ingresado_permanencia"),
    ("nombre", "  ", "nombre")
])
def test_fila_invalida(campo, valor, mensaje):

    fila = fila_ejemplo()
    fila["datos"][campo] = valor

    resultado = normalizar_filas([fila])

    assert resultado["talleres"] == []
    assert resultado["errores"][0]["fila"] == 2
    assert resultado["errores"][0]["datos"][campo] == valor
    assert mensaje in resultado["errores"][0]["errores"][0]


def test_lote_mixto():

    valida = fila_ejemplo()

    invalida = fila_ejemplo()
    invalida["fila"] = 3
    invalida["datos"]["horario"] = "desconocido"

    resultado = normalizar_filas([invalida, valida])

    assert [r["fila"] for r in resultado["talleres"]] == [2]
    assert [r["fila"] for r in resultado["errores"]] == [3]


def test_lote_vacio():

    assert normalizar_filas([]) == {
        "talleres": [],
        "errores": []
    }
