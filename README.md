# Demo SAAP - Módulo LLM local con llama.cpp

## Qué demuestra

Ejecución LOCAL de un LLM mediante `llama-cpp-python`, aplicado al caso real de PAIEP:
validación de la planilla de talleres y generación del `data.js` de la cartelera.

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
cd demo_saap
python demo_saap.py --model /ruta/al/modelo.gguf
```

También se puede definir la ruta una sola vez:

```bash
export MODEL_PATH="/ruta/al/modelo.gguf"
python demo_saap.py
```

`--n-gpu-layers -1` (valor predeterminado) intenta cargar todas las capas en la
GPU. Para ejecutarlo solo con CPU usa `--n-gpu-layers 0`.

### Usar modelos descargados con LM Studio

LM Studio normalmente descarga modelos cuantizados en formato `.gguf`. Elige
el archivo `.gguf` dentro de la carpeta de modelos de LM Studio y pásalo a
`--model`; no es necesario volver a descargarlo ni convertirlo. La ubicación
se puede consultar en **LM Studio > My Models** (opción para abrir la carpeta
del modelo). Ejemplos habituales en Linux son:

```bash
find ~/.cache/lm-studio/models -type f -name '*.gguf'
python demo_saap.py --model "/home/usuario/.cache/lm-studio/models/autor/modelo/modelo-Q4_K_M.gguf"
```

El modelo debe tener una plantilla de chat compatible (Qwen, Llama, Mistral,
etc. suelen funcionar automáticamente). Si LM Studio solo muestra un modelo
pero no hay ningún `.gguf`, se está usando una descarga o formato que
`llama.cpp` no puede abrir directamente; descarga la variante GGUF.

Como alternativa, LM Studio puede actuar como servidor OpenAI-compatible,
pero este demo usa el archivo local directamente con `llama-cpp-python`, por
lo que no necesita dejar LM Studio abierto.

## Contenido

- `demo_saap.py` : pipeline completo (ingesta -> validador LLM -> generador LLM -> data.js)
- `EJEMPLO PLANILLA.xlsx` : planilla con el FORMATO REAL de PAIEP (mismas columnas),
  con errores reales detectados en reunión: suspensión mal registrada
  en Observaciones, choque de sala/horario y docente duplicado.
  La ingesta maneja las peculiaridades reales: encabezado duplicado
  y Fecha como serial de Excel (46288 -> 2026-09-23).

## Relación con el proyecto

| Demo                           | Producción (diseño arquitectural)                            |
| ------------------------------ | ------------------------------------------------------------ |
| Script Python + LangChain      | Sub-workflows n8n con nodos AI Agent (LangChain)             |
| llama.cpp local (archivo GGUF) | Mismo motor en servidor USACH (Ubuntu 22, 8 GB RAM)          |
| Validador + Generador          | Agente Resolvedor de Conflictos (M3) + Agente Generador (M4) |
| data.js                        | Único archivo que se publica en TIC/Cloudflare (M7)          |

## Costo de la demo

$0 - modelo open-weight local, sin API keys, sin suscripciones.
