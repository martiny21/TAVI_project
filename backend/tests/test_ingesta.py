
from datetime import date

import pytest

from app.services.ingesta import (
    COLUMNAS,
    extraer_filas,
    leer_excel
)


def planilla_ejemplo():
    return [
        list(COLUMNAS),
        [
            "AOS",
            "Taller A",
            "Tutor A",
            "Todas las Facultades",
            "Descripción",
            39,
            date(2026, 9, 23),
            "Miércoles",
            "11:25 a 12:45",
            "",
            "Sala 12",
            "Vigente",
            "-",
            "No",
            "Ok"
        ]
    ]


def test_extraer_fila():

    registros = extraer_filas(planilla_ejemplo())

    assert len(registros) == 1
    assert registros[0]["fila"] == 2

    datos = registros[0]["datos"]

    assert datos["nombre"] == "Taller A"
    assert datos["fecha"] == date(2026, 9, 23)
    assert datos["horario"] == "11:25 a 12:45"
    assert datos["total_participantes"] == "-"


def test_filas_vacias_e_incompletas():

    filas = planilla_ejemplo()

    filas.extend([
        [None, "  "],
        ["AOS", ""]
    ])

    registros = extraer_filas(filas)

    assert [r["fila"] for r in registros] == [2, 4]
    assert registros[1]["datos"]["nombre"] == ""
    assert registros[1]["datos"]["sala"] is None


def test_columna_faltante():

    filas = planilla_ejemplo()
    filas[0].pop()

    with pytest.raises(
        ValueError,
        match="Columnas faltantes"
    ):
        extraer_filas(filas)


def test_columna_duplicada():

    filas = planilla_ejemplo()
    filas[0].append("  ÁREA  ")

    with pytest.raises(
        ValueError,
        match="Columna duplicada"
    ):
        extraer_filas(filas)


def test_columnas_reordenadas():

    filas = planilla_ejemplo()

    for fila in filas:
        fila[0], fila[1] = fila[1], fila[0]

    registros = extraer_filas(filas)

    assert registros[0]["datos"]["nombre"] == "Taller A"


def test_archivo_inexistente(tmp_path):

    with pytest.raises(FileNotFoundError):
        leer_excel(
            tmp_path / "no_existe.xlsx",
            "Talleres"
        )
