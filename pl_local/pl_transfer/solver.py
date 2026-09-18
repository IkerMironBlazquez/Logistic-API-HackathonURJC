"""solver.py – Minimiza el consumo de combustible eligiendo la mejor franja.

Modelo:
  fuel_vuelo(franja) = fuel_base × (1 + %extra_meteo_origen + %extra_meteo_destino)
  objetivo: min Σ fuel_vuelo(franja_elegida)
  ahorro = fuel_peor_franja − fuel_mejor_franja
"""


def _fuel_franja(fuel_base, wx_origen, wx_destino):
    """Combustible total (kg) de un vuelo en una franja."""
    pct = 1.0 + wx_origen["pct_extra"] + wx_destino["pct_extra"]
    return round(fuel_base * pct, 1)


def _motivos_combinados(wx_origen, wx_destino):
    partes = []
    for m in wx_origen["motivos"]:
        partes.append(f"Orig: {m}")
    for m in wx_destino["motivos"]:
        partes.append(f"Dest: {m}")
    return partes if partes else ["Sin sobreconsumo"]


def solve_flights(data):
    """Para cada vuelo elige la franja con menor consumo de combustible."""
    vuelos = data["vuelos"]
    meteo = data["meteo"]
    franjas = data["franjas"]

    resultados = []
    total_optimo = 0.0
    total_peor = 0.0

    for v in vuelos:
        origen = v["origen"]
        destino = v["destino"]
        base = v["fuel_base_kg"]

        opciones = []
        for fr in franjas:
            wx_o = meteo[origen][fr]
            wx_d = meteo[destino][fr]
            fuel = _fuel_franja(base, wx_o, wx_d)
            extra = round(fuel - base, 1)
            pct_total = round((wx_o["pct_extra"] + wx_d["pct_extra"]) * 100, 1)
            opciones.append({
                "franja": fr,
                "fuel_kg": fuel,
                "extra_kg": extra,
                "pct_extra_total": pct_total,
                "motivos": _motivos_combinados(wx_o, wx_d),
            })

        mejor = min(opciones, key=lambda x: x["fuel_kg"])
        peor  = max(opciones, key=lambda x: x["fuel_kg"])
        ahorro = round(peor["fuel_kg"] - mejor["fuel_kg"], 1)

        total_optimo += mejor["fuel_kg"]
        total_peor += peor["fuel_kg"]

        resultados.append({
            "vuelo_id": v["id"],
            "origen": origen,
            "destino": destino,
            "dist_km": v["dist_km"],
            "fuel_base_kg": base,
            "mejor_franja": mejor["franja"],
            "fuel_mejor_kg": mejor["fuel_kg"],
            "fuel_peor_kg": peor["fuel_kg"],
            "ahorro_kg": ahorro,
            "por_franja": opciones,
        })

    ahorro_total = round(total_peor - total_optimo, 1)

    return {
        "vuelos": resultados,
        "meteo": meteo,
        "resumen": {
            "fuel_total_mejor_kg": round(total_optimo, 1),
            "fuel_total_peor_kg": round(total_peor, 1),
            "ahorro_total_kg": ahorro_total,
            "ahorro_total_pct": round(ahorro_total / total_peor * 100, 2) if total_peor else 0,
        },
    }
