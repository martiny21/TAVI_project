from pathlib import Path
from typing import TypedDict

COLUMNAS = {
    "Área": "area",
    "Nombre taller": "nombre",
    "Nombre del tutor/a o mentor/a": "tutor",
    "Facultad/Carrera/Transversal": "destinatarios",
    "Descripción taller": "descripcion",
    "Semana": "semana",
    "Fecha": "fecha",
    "Día": "dia",
    "Horario": "horario",
    "Observaciones": "observaciones",
    "Número de sala (EDITADO SOLO POR SARA G.)": "sala",
    "Estado taller (EDITADO POR SARA G.)": "estado",
    "Total participantes (EDITADO POR SARA G.)": "total_participantes",
    "Ingresado en Permanencia (EDITADO POR SARA G.)": "ingresado_permanencia",
    "Revisión Linktree  (EDITADO POR SARA G.)": "revision_linktree",
}

class FilaExcel(TypedDict):
    fila: int
    datos: dict[str, object]


def normalizar_encabezado(texto: str) -> str:
    return " ".join(texto.split()).casefold()


def es_celda_vacia(valor: object) -> bool:
    return valor is None or (
        isinstance(valor, str) and not valor.strip()
    )

def extraer_filas(filas: list[list[object]]) -> list[FilaExcel]:

    if not filas:
        raise ValueError("La hoja está vacía")

    esperadas = {
        normalizar_encabezado(nombre): campo
        for nombre, campo in COLUMNAS.items()
    }

    indices: dict[str, int] = {}

    # Identificar los encabezados y sus posiciones
    for indice, encabezado in enumerate(filas[0]):

        if es_celda_vacia(encabezado):
            continue

        clave = normalizar_encabezado(str(encabezado))

        if clave not in esperadas:
            raise ValueError(
                f"Columna desconocida: {encabezado}"
                )

        campo = esperadas[clave]

        if campo in indices:
            raise ValueError(
                f"Columna duplicada: {encabezado}"
            )

        indices[campo] = indice

    # Comprobar que existen todas las columnas necesarias

    faltantes = set(COLUMNAS.values()) - set(indices)

    if faltantes:
        raise ValueError(
            f"Columnas faltantes: {', '.join(sorted(faltantes))}"
        )

    registros: list[FilaExcel] = []
    indices_validos = set(indices.values())

    # Recorrer las filas que contienen los talleres

    for numero, fila in enumerate(filas[1:], start=2):

        if all(es_celda_vacia(valor) for valor in fila):
            continue

        # Evitar que se pierdan datos de columnas sin encabezado

        for indice, valor in enumerate(fila):
            if indice not in indices_validos and not es_celda_vacia(valor):
                raise ValueError(
                    f"Fila {numero}: dato en columna sin encabezado"
                )

        datos = {
            campo: fila[indice] if indice < len(fila) else None
            for campo, indice in indices.items()
        }

        registros.append({
            "fila": numero,
            "datos": datos
        })
    return registros

def leer_excel(ruta: str | path, nombre_hoja: str) -> List [FilaExcel]:
    ruta = Path(ruta)

    if not ruta.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo: {ruta}"
        )

    from python_calamine import CalamineWorkbook

    with CalamineWorkbook.from_path(str(ruta)) as libro:

        if nombre_hoja not in libro.sheet_names:
            raise ValueError(
                f"Hoja no encontrada: {nombre_hoja}"
            )

        hoja = libro.get_sheet_by_name(nombre_hoja)
        filas = hoja.to_python(skip_empty_area=False)

    return extraer_filas(filas)