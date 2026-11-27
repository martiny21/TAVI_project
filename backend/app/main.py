from fastapi import FastAPI

app = FastAPI(
    title="SAAP API",
    description="Backend del Sistema Automático de Actualización de Página",
    version="0.1.0"
)

@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API de SAAP"
    }

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "SAAP Backend"
    }