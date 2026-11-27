from fastapi import FastAPI

from app.api.routes import ejecuciones, snapshots, talleres


app = FastAPI(
    title="SAAP API",
    description="Backend del Sistema Automático de Actualización de Página",
    version="0.1.0"
)

# Rutas

app.include_router(talleres.router, prefix="/talleres")
app.include_router(snapshots.router, prefix="/snapshots")
app.include_router(ejecuciones.router, prefix="/ejecuciones")

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