
from datetime import date, time

import pytest
from pydantic import ValidationError

from app.schemas.taller import Taller


def datos_taller():
    return {
        "area": "física",
        "nombre": "electricidad y magnetismo",
        "tutor": "alberto einstein",
        "destinatarios": "facultad de física",
        "descripcion": "Taller de campos magneticos y eléctricos",
        "semana": 39,
        "fecha": "2026-09-23",
        "dia": "Miércoles",
        "hora_inicio": "11:25",
        "hora_fin": "12:45",
        "sala": "Sala N°12 PAIEP",
        "estado": "Vigente",
        "ingresado_permanencia": False,
        "revision_linktree": "Ok"
    }


def test_taller_valido():
    taller = Taller(**datos_taller())

    assert taller.fecha == date(2026, 9, 23)
    assert taller.hora_inicio == time(11, 25)
    assert taller.total_participantes is None
    assert taller.ingresado_permanencia is False


def test_horario_invalido():
    datos = datos_taller()
    datos["hora_fin"] = "10:00"

    with pytest.raises(ValidationError, match="hora de término"):
        Taller(**datos)


def test_nombre_vacio():
    datos = datos_taller()
    datos["nombre"] = "   "

    with pytest.raises(ValidationError):
        Taller(**datos)


def test_semana_invalida():
    datos = datos_taller()
    datos["semana"] = 54

    with pytest.raises(ValidationError):
        Taller(**datos)


def test_participantes_negativos():
    datos = datos_taller()
    datos["total_participantes"] = -1

    with pytest.raises(ValidationError):
        Taller(**datos)


def test_campo_desconocido():
    datos = datos_taller()
    datos["horra_inicio"] = "11:25"

    with pytest.raises(ValidationError):
        Taller(**datos)


def test_serializacion_json():
    taller = Taller(**datos_taller())
    resultado = taller.model_dump(mode="json")

    assert resultado["fecha"] == "2026-09-23"
    assert resultado["hora_inicio"] == "11:25:00"
