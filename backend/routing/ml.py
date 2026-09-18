"""Router para el servicio de Machine Learning basado en historial de pedidos y posición GPS."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import List
import os
import numpy as np
import pandas as pd
import joblib
import h3


router3 = APIRouter()

# Carga del modelo (Dentro de backend/ML/)
_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "ML")
_model    = joblib.load(os.path.join(_BASE_DIR, "modelo_demanda.joblib"))
_features = joblib.load(os.path.join(_BASE_DIR, "features.joblib"))


# Clase base compartida con validaciones de historial y day semana
class HistorialDayWk(BaseModel):
    historial: List[int]
    day_semana: int  # 0 = lunes ... 6 = domingo

    @field_validator("historial")
    @classmethod
    def historial_minimo(cls, v: List[int]) -> List[int]:
        if len(v) < 7:
            raise ValueError("El historial debe contener al menos 7 dias.")
        return v

    @field_validator("day_semana")
    @classmethod
    def dia_valido(cls, v: int) -> int:
        if not (0 <= v <= 6):
            raise ValueError("day_semana debe estar entre 0 (lunes) y 6 (domingo).")
        return v


# Hereda de HistorialDayWeek
class PredecirZonaRequest(HistorialDayWk):
    pass


class PredecirZonaResponse(BaseModel):
    pedidos_esperados: float
    dia: str


# Lógica de prediccion 
_DIAS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]


def _predecir_zona(historial: List[int], day_semana: int) -> float:
    entrada = pd.DataFrame([{
        "lag_1":      historial[-1],
        "lag_2":      historial[-2],
        "lag_3":      historial[-3],
        "lag_7":      historial[-7],
        "average_wk": np.mean(historial[-7:]),
        "day_of_wk":  day_semana,
    }])
    return float(_model.predict(entrada[_features])[0])


# Endpoint para la prediccion de zona a partir del historial y dia de la semana
@router3.post(
    "/predecir-zona",
    response_model=PredecirZonaResponse,
    summary="Predice la demanda de pedidos para una zona H3",
    description=(
        "Recibe el historial de pedidos de los ultimos 7 dias (o mas) "
        "y el dia de la semana a predecir, y devuelve el numero "
        "estimado de pedidos para ese dia."
    ),
)
def predecir_zona(body: PredecirZonaRequest) -> PredecirZonaResponse:
    try:
        pedidos = _predecir_zona(body.historial, body.day_semana)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return PredecirZonaResponse(
        pedidos_esperados=round(pedidos, 1),
        dia=_DIAS[body.day_semana],
    )


# Hereda de HistorialDayWeek y le suma latitud y longitud sumando GPS
class PredictGpsRequest(HistorialDayWk):
    lat: float
    lng: float

    @field_validator("lat")
    @classmethod
    def lat_valida(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError("lat debe estar entre -90 y 90.")
        return v

    @field_validator("lng")
    @classmethod
    def lng_valida(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError("lng debe estar entre -180 y 180.")
        return v


class PredictGpsResponse(BaseModel):
    h3_cell: str
    lat: float
    lng: float
    dia: str
    pedidos_esperados: float


# Endpoint para la prediccion de zona a partir del GPS, historial y dia de la semana
@router3.post(
    "/predict-gps",
    response_model=PredictGpsResponse,
    summary="Predice la demanda a partir de una posicion GPS",
    description=(
        "Dado un punto GPS (lat, lng), obtiene su celda H3 (resolucion 8) "
        "y predice los pedidos esperados para el dia indicado."
    ),
)
def predict_from_gps_position(body: PredictGpsRequest) -> PredictGpsResponse:
    try:
        celda = h3.latlng_to_cell(body.lat, body.lng, 8)
        pedidos = _predecir_zona(body.historial, body.day_semana)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return PredictGpsResponse(
        h3_cell=celda,
        lat=body.lat,
        lng=body.lng,
        dia=_DIAS[body.day_semana],
        pedidos_esperados=round(pedidos, 1),
    )
