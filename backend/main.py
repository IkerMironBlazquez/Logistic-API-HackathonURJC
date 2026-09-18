import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routing import search, pl, ml

load_dotenv()  # Carga variables desde .env

_ENV = os.getenv("ENV", "development")
_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
_ALLOWED_ORIGINS = [o.strip() for o in _ORIGINS_RAW.split(",")] if _ORIGINS_RAW != "*" else ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("Starting up the backend server...")
    search.load_kdt()  # (scipy.spatial) para búsqueda de nodos
    yield
    # --- Shutdown ---
    print("No more backend server...")


backend = FastAPI(
    title="Sustainability Optimization API",
    description="API para optimización logística: routing, programación lineal y predicción de demanda por zonas densas",
    version="1.0.1",
    docs_url="/docs" if _ENV != "production" else None,
    redoc_url="/redoc" if _ENV != "production" else None,
    lifespan=lifespan,
)

# CORS — En despliegue -> ALLOWED_ORIGINS en .env con el dominio real
backend.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
backend.include_router(search.router1, prefix="/search", tags=["Routing de alta escala - A* Bidirectional"])
backend.include_router(pl.router2, prefix="/pl", tags=["Optimización mediante PL - Multi-Depot VRP"])
backend.include_router(ml.router3, prefix="/ml", tags=["Predicción de pedidos por zona mediante ML - LightGBM en series temporales"])


@backend.get("/health", tags=["Health"])
def health_check():
    """Sonda de salud para Microsoft Azure."""
    return {"status": "ok", "version": "1.0.1"}
