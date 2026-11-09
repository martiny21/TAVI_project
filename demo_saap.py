import json
import argparse
import os
from collections import defaultdict
import pandas as pd
from datetime import datetime, timedelta
from llama_cpp import Llama

PLANILLA = "EJEMPLO PLANILLA.xlsx"


def crear_llm():
    parser = argparse.ArgumentParser(description="Demo SAAP con un modelo GGUF local")
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL_PATH"),
        help="Ruta al archivo .gguf (también puede definirse con MODEL_PATH)",
    )
    parser.add_argument(
        "--n-gpu-layers",
        type=int,
        default=int(os.getenv("N_GPU_LAYERS", "-1")),
        help="-1 usa todas las capas disponibles en GPU; 0 usa solo CPU",
    )
    args = parser.parse_args()

    if not args.model:
        raise SystemExit(
            "Falta la ruta del modelo GGUF. Usa --model /ruta/modelo.gguf "
            "o define MODEL_PATH."
        )
    if not os.path.isfile(args.model):
        raise SystemExit(f"No existe el archivo del modelo: {args.model}")

    return Llama(
        model_path=args.model,
        n_ctx=8192,
        n_gpu_layers=args.n_gpu_layers,
        verbose=False,
    )


llm = crear_llm()


def completar_json(instrucciones, payload):
    respuesta = llm.create_chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "Responde únicamente con un objeto JSON válido. "
                    "No uses Markdown ni bloques de código."
                ),
            },
            {
                "role": "user",
                "content": instrucciones.format(payload=payload),
            },
        ],
        temperature=0,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    uso = respuesta.get("usage", {}) or {}
    print(
        "USO DE TOKENS (LLM)\n"
        f"Entrada: {uso.get('prompt_tokens', 'N/D')} | "
        f"Salida: {uso.get('completion_tokens', 'N/D')} | "
        f"Total: {uso.get('total_tokens', 'N/D')}"
    )
    contenido = respuesta["choices"][0]["message"]["content"]
    try:
        return json.loads(contenido)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"El modelo no devolvió JSON válido: {contenido[:300]!r}"
        ) from error

# INGESTA - Excel real -> JSON canónico (M1/M2)
def excel_serial_a_fecha(valor):
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d")
    try:
        return (datetime(1899, 12, 30) + timedelta(days=int(float(valor)))).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(valor)

# columna planilla real
MAPEO = { 
    "Área": "area",
    "Nombre taller": "nombre",
    "Nombre del tutor/a o mentor/a": "encargado",
    "Facultad/Carrera/Transversal": "facultad",
    "Descripción taller": "descripcion",
    "Semana": "semana",
    "Fecha": "fecha",
    "Día": "dia",
    "Horario": "horario",
    "Observaciones": "observaciones",
    "Número de sala (EDITADO SOLO POR SARA G.)": "sala",
    "Estado taller (EDITADO POR SARA G.)": "estado",
}

def cargar_planilla(ruta):
    df = pd.read_excel(ruta, sheet_name=0)
    df = df.astype(object).where(pd.notna(df), "")
    # elimina filas duplicadas del encabezado (peculiaridad real de la planilla)
    df = df.loc[:, ~df.columns.duplicated()]
    df = df[df["Nombre taller"] != "Nombre taller"]
    # renombra a campos canónicos y convertir fecha serial
    df = df.rename(columns=MAPEO)
    df["fecha"] = df["fecha"].apply(excel_serial_a_fecha)
    return df[["area","nombre","encargado","facultad","descripcion","semana",
               "fecha","dia","horario","observaciones","sala","estado"]].to_dict("records")

talleres = cargar_planilla(PLANILLA)
payload = json.dumps(talleres, ensure_ascii=False, indent=2)
print("=== INGESTA - Excel real -> JSON canónico ===")
print(payload)

# Los choques son reglas exactas y se calculan fuera del LLM.
def clave_normalizada(valor):
    return str(valor).strip().casefold()


def detectar_conflictos(talleres):
    por_sala = defaultdict(list)
    por_docente = defaultdict(list)
    for taller in talleres:
        momento = (
            clave_normalizada(taller["fecha"]),
            clave_normalizada(taller["dia"]),
            clave_normalizada(taller["horario"]),
        )
        sala = clave_normalizada(taller["sala"])
        encargado = clave_normalizada(taller["encargado"])
        if sala and sala != "virtual":
            por_sala[(*momento, sala)].append(taller)
        if encargado:
            por_docente[(*momento, encargado)].append(taller)

    choques_sala = [
        {
            "sala": grupo[0]["sala"],
            "dia": grupo[0]["dia"],
            "horario": grupo[0]["horario"],
            "talleres": [t["nombre"] for t in grupo],
        }
        for grupo in por_sala.values()
        if len(grupo) > 1
    ]
    docentes_duplicados = [
        {
            "encargado": grupo[0]["encargado"],
            "dia": grupo[0]["dia"],
            "horario": grupo[0]["horario"],
            "talleres": [t["nombre"] for t in grupo],
        }
        for grupo in por_docente.values()
        if len(grupo) > 1
    ]
    return choques_sala, docentes_duplicados


choques_sala, docentes_duplicados = detectar_conflictos(talleres)

# AGENTE VALIDADOR (M3) - interpreta solamente texto ambiguo
prompt_validador = """Eres el verificador de la cartelera semanal de talleres del PAIEP de la Universidad de Santiago de Chile.

Talleres (JSON):
{payload}

Analiza SOLO "observaciones" para detectar suspensiones mal registradas.
Marca un taller únicamente cuando "observaciones" contiene explícitamente
"suspendido", "suspensión", "cancelado", "cancelada" o "no se realiza", y
"estado" no es exactamente "Suspendido" ni "No Vigente".
Una observación normal o descriptiva no es una suspensión.
Si no hay coincidencias, devuelve una lista vacía.

Responde EXACTAMENTE con este objeto y ninguna otra clave:
{{
  "suspensiones_mal_registradas": [{{"taller": "...", "observacion": "...", "estado_actual": "..."}}],
  "resumen": "una frase"
}}"""

resultado_modelo = completar_json(prompt_validador, payload)
if not isinstance(resultado_modelo, dict):
    raise RuntimeError("El validador devolvió un JSON que no es un objeto.")
suspensiones = resultado_modelo.get("suspensiones_mal_registradas", [])
if not isinstance(suspensiones, list):
    raise RuntimeError(
        "El validador devolvió suspensiones_mal_registradas con formato inválido."
    )
for suspension in suspensiones:
    if not isinstance(suspension, dict) or not suspension.get("taller"):
        raise RuntimeError(
            "Cada suspensión debe ser un objeto con el campo 'taller'."
        )
alertas = {
    "suspensiones_mal_registradas": suspensiones,
    "choques_de_sala": choques_sala,
    "docente_duplicado": docentes_duplicados,
    "resumen": (
        "Se detectaron conflictos de sala o docente."
        if choques_sala or docentes_duplicados
        else resultado_modelo.get("resumen", "No se encontraron problemas.")
    ),
}
print("=== AGENTE VALIDADOR (LLM local + llama.cpp) ===")
print(json.dumps(alertas, ensure_ascii=False, indent=2))
print()

# Corrección determinista: se excluyen talleres con problemas
#    (quedan en manos de Sara - validación humana final)
en_alerta = {a["taller"] for a in alertas["suspensiones_mal_registradas"]}
for c in alertas["choques_de_sala"] + alertas["docente_duplicado"]:
    en_alerta.update(c["talleres"])
talleres_validos = [t for t in talleres if t["nombre"] not in en_alerta
                    and str(t["estado"]).strip() == "Vigente"]
print("=== CORRECCIÓN DETERMINISTA ===")
print(f"Se excluyen {len(en_alerta)} talleres con problemas.")
print()
print("=== TALLERES VALIDOS ===")
for t in talleres_validos:
    print(f"- {t['nombre']} ({t['encargado']})")

print()

# AGENTE GENERADOR (M4) - JSON validado -> tarjetas de cartelera
#    El LLM devuelve JSON estructurado; data.js se renderiza en Python
#    (determinismo total: nada de HTML/JS malformado por texto libre)
prompt_generador = """Eres el generador de datos para la cartelera web de talleres del PAIEP.
De la Universidad de Santiago de Chile. Recibes un JSON con los talleres validados y devuelves un JSON con tarjetas para la cartelera web.
No debes inventar nada: solo debes usar los datos que vienen en el JSON de entrada.
Si no hay datos para un campo, rellena con una cadena vacía "".
Si el taller es virtual, rellena el campo "sala" con la cadena "Virtual".

Talleres validados (JSON):
{payload}

Devuelve SOLO este JSON, una tarjeta por taller:
{{
  "tarjetas": [
    {{
      "titulo": "<nombre del taller>",
      "area": "<área>",
      "encargado": "<tutor/a>",
      "facultad": "<facultad>",
      "dia": "<día>",
      "fecha": "<fecha ISO>",
      "horario": "<horario>",
      "sala": "<sala o 'Virtual'>",
      "descripcion": "<descripción>"
    }}
  ]
}}"""

tarjetas = completar_json(
    prompt_generador,
    json.dumps(talleres_validos, ensure_ascii=False),
)["tarjetas"]

data_js = ("// Generado automáticamente por SAAP - pipeline n8n + LLM local\n"
           "const TALLERES = " + json.dumps(tarjetas, ensure_ascii=False, indent=2) + ";\n")
with open("data.js", "w", encoding="utf-8") as f:
    f.write(data_js)

print("\n=== data.js GENERADO (se publica junto al HTML de TIC PAIEP) ===")
print(data_js)
print(f"OK: {len(talleres)} leídos, {len(talleres_validos)} publicados, "
      f"{len(en_alerta)} con alerta.")
