"""build_problem.py – Genera meteorología + modelo de combustible para 10 aeropuertos en 3 franjas."""

import json
import math
import random

# ── 10 aeropuertos DHL europeos (código, nombre, lat, lon) Ejemplo ──
AIRPORTS = {
    "LEJ": ("Leipzig",        51.432, 12.242),
    "CDG": ("Paris-CDG",      49.010,  2.548),
    "FRA": ("Frankfurt",      50.033,  8.571),
    "MAD": ("Madrid",         40.472, -3.563),
    "BCN": ("Barcelona",      41.297,  2.079),
    "BRU": ("Bruselas",       50.901,  4.484),
    "EMA": ("East Midlands",  52.831, -1.328),
    "LIS": ("Lisboa",         38.781, -9.136),
    "MXP": ("Milan-Malpensa", 45.631,  8.728),
    "VIE": ("Viena",          48.110, 16.570),
}

FRANJAS = ["manana", "tarde", "noche"]

# ── Consumo medio de combustible ──
_FUEL_KG_KM = 3.5          # kg de queroseno por km (B757F cargado, estimación)
_CORRIDOR_FACTOR = 1.05    # Despliegue aéreo vs línea recta


def _haversine(lat1, lon1, lat2, lon2):
    """Distancia en km."""
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon/2)**2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def combustible_base(origen, destino):
    """Combustible base en kg (sin penalización meteo)."""
    _, lat1, lon1 = AIRPORTS[origen]
    _, lat2, lon2 = AIRPORTS[destino]
    dist_km = _haversine(lat1, lon1, lat2, lon2) * _CORRIDOR_FACTOR
    fuel_kg = dist_km * _FUEL_KG_KM
    return round(fuel_kg, 1), round(dist_km, 0)


def _gen_meteo(rng, franja):
    """Genera condiciones meteo y su sobreconsumo de combustible (% realista)."""
    ajuste = {"manana": (1.0, 1.2), "tarde": (0.6, 0.8), "noche": (1.5, 0.7)}
    niebla_mult, viento_mult = ajuste[franja]

    viento_kt = max(0, round(rng.gauss(12, 6) * viento_mult))
    visibilidad_km = round(max(0.5, rng.gauss(15, 5) / niebla_mult), 1)
    lluvia = rng.random() < 0.25
    tormenta = rng.random() < 0.08
    niebla = visibilidad_km < 5

    # ── Sobreconsumo de combustible (% realista sobre consumo base) ──
    # Basado en datos operacionales reales:
    #   - Desvío por tormenta: +3-5% (ruta más larga)
    #   - Holding por niebla: ~2-4% (circuitos de espera)
    #   - Lluvia: ~0.5-1% (frenada + reversa más larga, poco impacto en crucero)
    #   - Viento cruzado fuerte: ~1-2% (corrección de deriva)
    pct_extra = 0.0
    motivos = []
    if tormenta:
        pct_extra += 0.04          # desvío de ruta ~4%
        motivos.append("TORMENTA +4%")
    if niebla:
        pct_extra += 0.03          # holding / aproximación frustrada ~3%
        motivos.append(f"NIEBLA (vis {visibilidad_km}km) +3%")
    if lluvia:
        pct_extra += 0.01          # impacto menor ~1%
        motivos.append("LLUVIA +1%")
    if viento_kt > 30:
        pct_extra += 0.02          # viento cruzado fuerte ~2%
        motivos.append(f"VIENTO FUERTE {viento_kt}kt +2%")
    elif viento_kt > 20:
        pct_extra += 0.01          # viento moderado ~1%
        motivos.append(f"VIENTO {viento_kt}kt +1%")

    return {
        "viento_kt": viento_kt,
        "visibilidad_km": visibilidad_km,
        "lluvia": lluvia,
        "tormenta": tormenta,
        "niebla": niebla,
        "pct_extra": round(pct_extra, 3),
        "motivos": motivos,
    }


def generate_weather(seed=42):
    """Devuelve {aeropuerto: {franja: meteo}} para los 10 aeropuertos."""
    rng = random.Random(seed)
    meteo = {}
    for code in sorted(AIRPORTS):
        meteo[code] = {}
        for franja in FRANJAS:
            meteo[code][franja] = _gen_meteo(rng, franja)
    return meteo


def build_data(raw):
    """Lee el JSON de entrada y genera los datos con meteo + combustible base."""
    vuelos = raw["vuelos"]
    seed = raw.get("weather_seed", 42)
    meteo = generate_weather(seed)

    for v in vuelos:
        fuel, dist = combustible_base(v["origen"], v["destino"])
        v["fuel_base_kg"] = fuel
        v["dist_km"] = dist

    print(f"  [build_problem] {len(vuelos)} vuelos, {len(meteo)} aeropuertos, 3 franjas")
    return {"vuelos": vuelos, "meteo": meteo, "franjas": FRANJAS}


def build_data_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return build_data(raw)
