import joblib
import pandas as pd
import numpy as np
import h3
from datetime import date, timedelta

model    = joblib.load("modelo_demanda.joblib")
features = joblib.load("features.joblib")

print("Modelo cargado")
print(f"Features esperadas: {features}\n")

def predecir_zona(historial: list[int], day_semana: int) -> float:
    """
    Predice el número de pedidos para mañana en una zona H3.

    Parámetros:
        historial   : lista con los pedidos de los últimos 7 días (Semana),
                      ordenados.
                      Ej: [30, 28, 30, 28, 30, 28, 30]
                                                    ^--- ayer
        day_semana  : día de la semana A PREDECIR (0=lun, 6=dom)

    Devuelve:
        número de pedidos esperados (float)
    """
    if len(historial) < 7:
        raise ValueError("El historial debe tener 7 días como mínimo.")

    entrada = pd.DataFrame([{
        "lag_1":       historial[-1],
        "lag_2":       historial[-2],
        "lag_3":       historial[-3],
        "lag_7":       historial[-7],
        "average_wk":  np.mean(historial[-7:]), # Promedio
        "day_of_wk":   day_semana,
    }])

    return model.predict(entrada[features])[0]

def predict_from_gps_position(lat: float, lng: float, historial: list[int], day_semana: int) -> dict:
    """
    Dado un punto GPS, obtiene su celda H3 y predice la demanda.

    Devuelve un dict con la celda H3, posición y predicción.
    """
    RESOLUTION = 8
    celda = h3.latlng_to_cell(lat, lng, RESOLUTION)
    pedidos = predecir_zona(historial, day_semana)

    return {
        "h3_cell":  celda,
        "lat":      lat,
        "lng":      lng,
        "day":      ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"][day_semana],
        "pedidos_esperados": round(pedidos, 1),
    }

# EJEMPLO

if __name__ == "__main__":

    # Ejemplo 1: predicción por historial directo ---
    print("=" * 50)
    print("EJEMPLO 1: Predicción por historial")
    print("=" * 50)

    historial_zona_A = [30, 25, 35, 40, 20, 40, 35]
    tomorrow = (date.today() + timedelta(days=1)).weekday()

    pred = predecir_zona(historial_zona_A, day_semana=tomorrow)
    print(f"Historial (7 días): {historial_zona_A}")
    print(f"Día a predecir:     {['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'][tomorrow]}")
    print(f"Pedidos esperados:  {pred:.1f}\n")


    # Ejemplo 2: predicción por posición GPS ---
    print("=" * 50)
    print("EJEMPLO 2: Predicción por posición GPS")
    print("=" * 50)

    resultado = predict_from_gps_position(
        lat=29.5637,
        lng=106.5504,
        historial=[20, 18, 25, 30, 15, 22, 24],
        day_semana=tomorrow,
    )

    for k, v in resultado.items():
        print(f"  {k}: {v}")


    # Ejemplo 3: predicción para múltiples zonas ---
    print("\n" + "=" * 50)
    print("EJEMPLO 3: Múltiples zonas a la vez")
    print("=" * 50)

    zonas = [
        {"nombre": "Zona Norte", "historial": [40, 42, 38, 42, 40, 38, 30], "dia": tomorrow},
        {"nombre": "Zona Centro","historial": [80, 75, 80, 90, 70, 90, 80], "dia": tomorrow},
        {"nombre": "Zona Sur",   "historial": [15, 10, 20, 18, 20, 10, 15], "dia": tomorrow},
    ]

    print(f"{'Zona':<15} {'Historial (media)':<25} {'Predicción':>12}")
    print("-" * 55)
    for z in zonas:
        pred = predecir_zona(z["historial"], z["dia"])
        media = np.mean(z["historial"])
        print(f"{z['nombre']:<15} {media:<25.1f} {pred:>12.1f}")