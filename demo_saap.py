import json
import argparse
import os
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
    df = pd.read_excel(ruta, sheet_name=0).fillna("")
    # elimina filas duplicadas del encabezado (peculiaridad real de la planilla)
    primer_fila = df.columns.tolist()
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

# AGENTE VALIDADOR (M3) - detecta errores reales reportados por el cliente
prompt_validador = """Eres el verificador de la cartelera semanal de talleres del PAIEP (USACH).

Talleres (JSON):
{payload}

Detecta SOLO estos tres problemas, que son los errores reales que ocurren
en la operación de PAIEP:
1. suspensiones_mal_registradas: "observaciones" indica que el taller fue
   suspendido/cancelado, pero "estado" NO es "Suspendido" ni "No Vigente".
2. choques_de_sala: dos talleres en la misma sala, mismo día y mismo horario.
3. docente_duplicado: el mismo encargado con dos talleres el mismo día y
   mismo horario.

Responde SOLO con este JSON (sin texto adicional):
{{
  "suspensiones_mal_registradas": [{{"taller": "...", "observacion": "...", "estado_actual": "..."}}],
  "choques_de_sala": [{{"sala": "...", "dia": "...", "horario": "...", "talleres": ["...", "..."]}}],
  "docente_duplicado": [{{"encargado": "...", "dia": "...", "horario": "...", "talleres": ["...", "..."]}}],
  "resumen": "una frase"
}}"""

alertas = completar_json(prompt_validador, payload)
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
