"""
build_problem.py
================
Pipeline de pre-procesamiento: convierte un archivo JSON de entrada
(depósitos + flota + clientes, todos con coordenadas) en el dict
``data`` que ``solver_ortools.solve_mdvrp()`` espera.

Flujo
-----
1. El usuario entrega un JSON con depots, flt2. ``build_data_from_file(path)`` o ``build_data(raw_dict)`` lee/valida.
3. Se calcula la matriz de distancias internamente:
     - Haversine (lat/lng en grados) → km
     - Factor de desvío (road_factor) para aproximar distancia real por carretera
4. Devuelve el dict listo para ``solve_mdvrp(data)``.

Formato de entrada esperado (JSON)
----------------------------------
{
  "depots": [
    {"id": "D1", "lat": 40.4168, "lng": -3.7038},
    ...
  ],
  "flota": {
    "D1": {"VAN": 6, "TRUCK": 5},
    ...
  },
  "clients": [
    {"id": "C1", "lat": 40.420, "lng": -3.710, "nS": 5, "nM": 2, "nL": 0},
    ...
  ],
  "time_limit": 60,
  "road_factor": 1.3
}

Campos opcionales:
  - time_limit  : int (segundos, default 60)
  - road_factor : float (multiplicador sobre Haversine, default 1.3)
                  Valores típicos: 1.2-1.4 zona urbana, 1.1 autovía
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Tuple


# ─────────────────────── constantes ──────────────────────────────────
_EARTH_RADIUS_KM = 6_371.0   # radio medio terrestre


# CÁLCULO DE DISTANCIAS

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia en km entre dos puntos (lat, lng) en grados decimales."""
    rlat1, rlng1 = math.radians(lat1), math.radians(lng1)
    rlat2, rlng2 = math.radians(lat2), math.radians(lng2)

    dlat = rlat2 - rlat1
    dlng = rlng2 - rlng1

    a = (math.sin(dlat / 2) ** 2
         + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return _EARTH_RADIUS_KM * c


def build_distance_matrix(
    nodes: List[Dict[str, Any]],
    road_factor: float = 1.3,
) -> Dict[Tuple[str, str], float]:
    """
    Construye la matriz de distancias completa entre todos los nodos.

    Parameters
    ----------
    nodes : lista de dicts con al menos {"id", "lat", "lng"}
    road_factor : multiplicador para aproximar distancia real a una red vial...

    Returns
    -------
    dict  {(id_a, id_b): distancia_km, ...}  (simétrico, sin diagonales)
    """
    n = len(nodes)
    dist_matrix: Dict[Tuple[str, str], float] = {}

    for i in range(n):
        for j in range(i + 1, n):
            a, b = nodes[i], nodes[j]
            d = haversine(a["lat"], a["lng"], b["lat"], b["lng"])
            d_road = round(d * road_factor, 2)
            dist_matrix[(a["id"], b["id"])] = d_road
            dist_matrix[(b["id"], a["id"])] = d_road

    return dist_matrix


# VALIDACIÓN FICHERO DE ENTRADA (JSON)

def _validate_raw(raw: dict) -> None:
    """Valida la estructura en el JSON de entrada."""
    # Claves obligatorias
    for key in ("depots", "flota", "clients"):
        if key not in raw:
            raise ValueError(f"Falta la clave obligatoria '{key}' en el JSON.")

    # Depósitos
    if not raw["depots"]:
        raise ValueError("Se necesita al menos un depósito.")
    for i, d in enumerate(raw["depots"]):
        for field in ("id", "lat", "lng"):
            if field not in d:
                raise ValueError(f"Depósito {i}: falta el campo '{field}'.")

    # Flota
    depot_ids = {d["id"] for d in raw["depots"]}
    for did in raw["flota"]:
        if did not in depot_ids:
            raise ValueError(
                f"Flota contiene depósito '{did}' que no existe en depots."
            )
    for did in depot_ids:
        if did not in raw["flota"]:
            raise ValueError(
                f"Depósito '{did}' no tiene flota definida en flota."
            )

    # Clientes
    if not raw["clients"]:
        raise ValueError("Se necesita al menos un cliente.")
    for i, c in enumerate(raw["clients"]):
        for field in ("id", "lat", "lng", "nS", "nM", "nL"):
            if field not in c:
                raise ValueError(f"Cliente {i}: falta el campo '{field}'.")

    # IDs únicos
    all_ids = [d["id"] for d in raw["depots"]] + [c["id"] for c in raw["clients"]]
    seen = set()
    for aid in all_ids:
        if aid in seen:
            raise ValueError(f"ID duplicado: '{aid}'.")
        seen.add(aid)


# DICT PARA EL SOLVER

def build_data(raw: dict) -> dict:
    """
    Transforma el JSON de entrada por el usuario en el dict ``data`` que
    ``solve_mdvrp()`` necesita.

    Parameters
    ----------
    raw : dict con la estructura documentada arriba (depots, flota, clients,
          opcionalmente time_limit y road_factor).

    Returns
    -------
    dict listo para ``solve_mdvrp(data)``
    """
    _validate_raw(raw)

    road_factor = raw.get("road_factor", 1.3)
    time_limit = raw.get("time_limit", 60)

    # ── nodos = depots + clients (todos con lat/lng) ──
    nodes: List[Dict[str, Any]] = []
    for d in raw["depots"]:
        nodes.append({"id": d["id"], "lat": d["lat"], "lng": d["lng"]})
    for c in raw["clients"]:
        nodes.append({"id": c["id"], "lat": c["lat"], "lng": c["lng"]})

    # ── distancia ──
    dist_matrix = build_distance_matrix(nodes, road_factor)

    # ── depots limpios
    depots = [{"id": d["id"]} for d in raw["depots"]]

    clients = [
        {"id": c["id"], "nS": c["nS"], "nM": c["nM"], "nL": c["nL"]}
        for c in raw["clients"]
    ]

    print(f"  [build_problem] {len(raw['depots'])} depósitos, "
          f"{len(raw['clients'])} clientes, "
          f"{len(dist_matrix)} pares de distancias, "
          f"road_factor={road_factor}")

    return {
        "depots": depots,
        "clients": clients,
        "flota": raw["flota"],
        "dist_matrix": dist_matrix,
        "time_limit": time_limit,
    }


def build_data_from_file(path: str) -> dict:
    """
    Archivo JSON y devuelve el dict listo para ``solve_mdvrp()``.

    Parameters
    ----------
    path : ruta al archivo JSON de entrada.

    Returns
    -------
    dict listo para ``solve_mdvrp(data)``
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return build_data(raw)
