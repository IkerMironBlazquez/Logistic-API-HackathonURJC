"""
Router para el servicio de programación lineal — Multi-Depot VRP con flota heterogénea.

Pipeline:
  1. Usuario envía JSON con depots (id, lat, lng), flota (VAN/TRUCK por depósito)
     y clientes (id, lat, lng, nS, nM, nL).
  2. Se calcula la matriz de distancias Haversine con factor de desvío vial.
  3. Se resuelve el MDVRP (CVRP por depósito, 2 fases).
  Se devuelve las rutas, ocupación, km totales y tiempo de resolución.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

router2 = APIRouter()


# CONSTANTES

_EARTH_RADIUS_KM = 6_371.0

CAP: Dict[str, float] = {"VAN": 10.0, "TRUCK": 20.0}   # m³
VOL: Dict[str, float] = {"S": 0.04, "M": 0.20, "L": 0.60}  # m³ por paquete

_SCALE = 1000      # OR-Tools trabaja con enteros → multiplicamos km × _SCALE
_VOL_SCALE = 10000  # precisión para volúmenes S/M/L


# MODELOS PYDANTIC

class DepotIn(BaseModel):
    id: str
    lat: float
    lng: float
    desc: Optional[str] = None


class ClientIn(BaseModel):
    id: str
    lat: float
    lng: float
    nS: int = 0
    nM: int = 0
    nL: int = 0


class VRPRequest(BaseModel):
    depots: List[DepotIn]
    flota: Dict[str, Dict[str, int]]
    clients: List[ClientIn]
    time_limit: int = 60
    road_factor: float = 1.3


class VRPResponse(BaseModel):
    status: str
    objective_km: Optional[float]
    vehicles_used: List[str]
    routes: Dict[str, List[str]]
    occupancy: Dict[str, float]
    solver_time: float
    gap: Optional[float]
    detail: Optional[str] = None


# DISTANCIAS

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia en km entre dos puntos (lat, lng) en grados decimales."""
    rlat1, rlng1 = math.radians(lat1), math.radians(lng1)
    rlat2, rlng2 = math.radians(lat2), math.radians(lng2)
    dlat = rlat2 - rlat1
    dlng = rlng2 - rlng1
    a = (math.sin(dlat / 2) ** 2
         + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2)
    return _EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_distance_matrix(
    nodes: List[Dict[str, Any]],
    road_factor: float = 1.3,
) -> Dict[Tuple[str, str], float]:
    """Construye la matriz de distancias completa entre todos los nodos."""
    dist: Dict[Tuple[str, str], float] = {}
    n = len(nodes)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = nodes[i], nodes[j]
            d = round(_haversine(a["lat"], a["lng"], b["lat"], b["lng"]) * road_factor, 2)
            dist[(a["id"], b["id"])] = d
            dist[(b["id"], a["id"])] = d
    return dist


# VALIDACIÓN

def _validate_request(req: VRPRequest) -> None:
    if not req.depots:
        raise HTTPException(status_code=422, detail="Se necesita al menos un depósito.")
    if not req.clients:
        raise HTTPException(status_code=422, detail="Se necesita al menos un cliente.")

    depot_ids = {d.id for d in req.depots}

    for did in req.flota:
        if did not in depot_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Flota contiene depósito '{did}' que no existe en depots.",
            )
    for did in depot_ids:
        if did not in req.flota:
            raise HTTPException(
                status_code=422,
                detail=f"Depósito '{did}' no tiene flota definida en flota.",
            )
    for vtype_dict in req.flota.values():
        for vtype in vtype_dict:
            if vtype not in CAP:
                raise HTTPException(
                    status_code=422,
                    detail=f"Tipo de vehículo desconocido: '{vtype}'. Valores válidos: {list(CAP)}.",
                )

    checked: set = set()
    for nid in [d.id for d in req.depots] + [c.id for c in req.clients]:
        if nid in checked:
            raise HTTPException(status_code=422, detail=f"ID duplicado: '{nid}'.")
        checked.add(nid)


# SOLVER: utilidades internas

def _client_volume(c: dict) -> float:
    return c.get("nS", 0) * VOL["S"] + c.get("nM", 0) * VOL["M"] + c.get("nL", 0) * VOL["L"]


def _build_vehicles(flota: Dict[str, Dict[str, int]]) -> List[Dict[str, str]]:
    vehicles: List[Dict[str, str]] = []
    for depot_id, types in flota.items():
        for vtype, count in types.items():
            for idx in range(count):
                vehicles.append({"id": f"{depot_id}_{vtype}_{idx}", "depot": depot_id, "type": vtype})
    return vehicles


def _clients_to_depots(
    depots: List[dict],
    clients: List[dict],
    flota: Dict[str, Dict[str, int]],
    dist_matrix: Dict[Tuple[str, str], float],
) -> Dict[str, List[dict]]:
    """Fase 1: asigna cada cliente al depósito más cercano con capacidad disponible."""
    depot_ids = [d["id"] for d in depots]
    depot_cap = {
        did: sum(CAP[vt] * cnt for vt, cnt in flota.get(did, {}).items())
        for did in depot_ids
    }
    depot_vol_used: Dict[str, float] = {did: 0.0 for did in depot_ids}
    asignaciones: Dict[str, List[dict]] = {did: [] for did in depot_ids}

    for client in clients:
        cid = client["id"]
        vol = _client_volume(client)
        dists = sorted(
            (dist_matrix.get((did, cid), dist_matrix.get((cid, did), float("inf"))), did)
            for did in depot_ids
        )

        assigned = False
        for threshold in (0.80, 0.95):
            for _, did in dists:
                if depot_vol_used[did] + vol <= depot_cap[did] * threshold:
                    asignaciones[did].append(client)
                    depot_vol_used[did] += vol
                    assigned = True
                    break
            if assigned:
                break

        if not assigned:
            asignaciones[dists[0][1]].append(client)

    return asignaciones


def _solve_sub_vrp(
    depot: dict,
    clients: List[dict],
    vehicles: List[Dict[str, str]],
    dist_matrix: Dict[Tuple[str, str], float],
    time_limit: int = 30,
) -> dict:
    """Fase 2: resuelve un CVRP para un depósito concreto usando OR-Tools Routing."""
    if not clients:
        return {"status": "optimal", "objective_km": 0.0, "routes": {}, "occupancy": {}}

    did = depot["id"]
    nodes = [did] + [c["id"] for c in clients]
    n_nodes = len(nodes)
    n_vehicles = len(vehicles)

    # Matriz de distancias (Enteros escalados)
    dist = [[0] * n_nodes for _ in range(n_nodes)]
    for i in range(n_nodes):
        for j in range(n_nodes):
            if i == j:
                continue
            key = (nodes[i], nodes[j])
            alt = (nodes[j], nodes[i])
            dist[i][j] = int(round(
                dist_matrix.get(key, dist_matrix.get(alt, 999_999.0)) * _SCALE
            ))

    # Demandas y capacidades (Volumen escalado)
    demands = [0] + [int(round(_client_volume(c) * _VOL_SCALE)) for c in clients]
    vehicle_caps = [int(round(CAP[v["type"]] * _VOL_SCALE)) for v in vehicles]

    manager = pywrapcp.RoutingIndexManager(n_nodes, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return dist[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_cb = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    def demand_callback(from_index):
        return demands[manager.IndexToNode(from_index)]

    demand_cb = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_cb, 0, vehicle_caps, True, "Capacity")

    for v_idx in range(n_vehicles):
        routing.SetFixedCostOfVehicle(0, v_idx)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = max(1, time_limit)

    solution = routing.SolveWithParameters(search_params)

    if not solution:
        return {"status": "infeasible", "objective_km": None, "routes": {}, "occupancy": {}}

    routes: Dict[str, List[str]] = {}
    occupancy: Dict[str, float] = {}

    for v_idx in range(n_vehicles):
        index = routing.Start(v_idx)
        route_nodes: List[str] = []
        route_load = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route_nodes.append(nodes[node])
            route_load += demands[node]
            index = solution.Value(routing.NextVar(index))
        route_nodes.append(nodes[manager.IndexToNode(index)])

        n_stops = sum(1 for n in route_nodes if n != did)
        if n_stops > 0:
            vid = vehicles[v_idx]["id"]
            routes[vid] = route_nodes
            cap = CAP[vehicles[v_idx]["type"]]
            occupancy[vid] = round((route_load / _VOL_SCALE) / cap, 4)

    return {
        "status": "optimal" if routing.status() == 1 else "feasible",
        "objective_km": round(solution.ObjectiveValue() / _SCALE, 4),
        "routes": routes,
        "occupancy": occupancy,
    }


def _solve_mdvrp(
    depots: List[dict],
    clients: List[dict],
    flota: Dict[str, Dict[str, int]],
    dist_matrix: Dict[Tuple[str, str], float],
    time_limit: int = 60,
) -> dict:
    """Resuelve el MDVRP completo con descomposición en 2 fases."""
    t0 = time.perf_counter()

    depot_clients = _clients_to_depots(depots, clients, flota, dist_matrix)

    all_routes: Dict[str, List[str]] = {}
    all_occupancy: Dict[str, float] = {}
    total_km = 0.0
    worst_status = "optimal"

    active_depots = sum(1 for v in depot_clients.values() if v)
    time_per_depot = max(5, time_limit // max(active_depots, 1))

    for depot in depots:
        did = depot["id"]
        sub_clients = depot_clients[did]
        if not sub_clients:
            continue

        vehicles = _build_vehicles({did: flota[did]})
        sub_result = _solve_sub_vrp(depot, sub_clients, vehicles, dist_matrix,
                                    time_limit=time_per_depot)

        if sub_result["status"] == "infeasible":
            return {
                "status": "infeasible",
                "objective_km": None,
                "vehicles_used": [],
                "routes": {},
                "occupancy": {},
                "solver_time": round(time.perf_counter() - t0, 3),
                "gap": None,
                "detail": (f"Sub-problema del depósito '{did}' es infeasible "
                           f"({len(sub_clients)} clientes, {len(vehicles)} vehículos)."),
            }

        if sub_result["status"] == "feasible":
            worst_status = "feasible"

        all_routes.update(sub_result["routes"])
        all_occupancy.update(sub_result["occupancy"])
        total_km += sub_result["objective_km"] or 0.0

    return {
        "status": worst_status,
        "objective_km": round(total_km, 4),
        "vehicles_used": sorted(all_routes.keys()),
        "routes": all_routes,
        "occupancy": all_occupancy,
        "solver_time": round(time.perf_counter() - t0, 3),
        "gap": 0.0,
    }


# ENDPOINT

@router2.post("/optimize", response_model=VRPResponse, summary="Optimizar rutas - VRP")
def optimize_routes(req: VRPRequest) -> VRPResponse:
    """
    Resuelve el problema de ruteo de vehículos multi-depósito (MDVRP) con flota heterogénea.

    **Flujo interno:**
    1. Valida el input.
    2. Calcula la matriz de distancias Haversine × road_factor entre todos los nodos.
    3. Asigna cada cliente al mejor depósito (Distancia) con capacidad disponible.
    4. Resuelve un CVRP independiente por depósito con OR-Tools (GLS metaheurístico).
    5. Devuelve rutas, ocupación por vehículo, km totales y tiempo de resolución.

    **Tipos de vehículo soportados:** `VAN` (10 m³), `TRUCK` (20 m³).

    **Tamaño de paquetes:** `S` = 0.04 m³ · `M` = 0.20 m³ · `L` = 0.60 m³.
    """
    _validate_request(req)

    # Construir lista de nodos con posiciones para la matriz de distancias
    nodes: List[Dict[str, Any]] = (
        [{"id": d.id, "lat": d.lat, "lng": d.lng} for d in req.depots]
        + [{"id": c.id, "lat": c.lat, "lng": c.lng} for c in req.clients]
    )
    dist_matrix = _build_distance_matrix(nodes, req.road_factor)

    depots_data = [{"id": d.id} for d in req.depots]
    clients_data = [{"id": c.id, "nS": c.nS, "nM": c.nM, "nL": c.nL} for c in req.clients]

    try:
        result = _solve_mdvrp(
            depots=depots_data,
            clients=clients_data,
            flota=req.flota,
            dist_matrix=dist_matrix,
            time_limit=req.time_limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Excepción con en el solver: {exc}") from exc

    return VRPResponse(**result)


# TRANSFER – Minimización de transporte en alta escala sobre sucursales (Aeropuertos) de vuelos por franja horaria

# ── Aeropuertos DHL europeos de referencia ──
_AIRPORTS: Dict[str, Tuple[str, float, float]] = {
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

_FRANJAS = ["manana", "tarde", "noche"]
_FUEL_KG_KM = 3.5           # kg de queroseno por km (B757F cargado, estimación)
_CORRIDOR_FACTOR = 1.05      # factor corredor aéreo vs línea recta

import random  # noqa: E402  (ya importado math arriba)


# ── Modelos Pydantic – Transfer ──

class FlightIn(BaseModel):
    id: str
    origen: str
    destino: str


class TransferRequest(BaseModel):
    vuelos: List[FlightIn]
    weather_seed: int = 42


class FranjaDetail(BaseModel):
    franja: str
    fuel_kg: float
    extra_kg: float
    pct_extra_total: float
    motivos: List[str]


class FlightResult(BaseModel):
    vuelo_id: str
    origen: str
    destino: str
    dist_km: float
    fuel_base_kg: float
    mejor_franja: str
    fuel_mejor_kg: float
    fuel_peor_kg: float
    ahorro_kg: float
    por_franja: List[FranjaDetail]


class TransferSummary(BaseModel):
    fuel_total_mejor_kg: float
    fuel_total_peor_kg: float
    ahorro_total_kg: float
    ahorro_total_pct: float


class TransferResponse(BaseModel):
    vuelos: List[FlightResult]
    meteo: Dict[str, Dict[str, Any]]
    resumen: TransferSummary


# ── Funciones auxiliares – Transfer ──

def _combustible_base(origen: str, destino: str) -> Tuple[float, float]:
    """Combustible base en kg y distancia en km entre dos aeropuertos."""
    _, lat1, lon1 = _AIRPORTS[origen]
    _, lat2, lon2 = _AIRPORTS[destino]
    dist_km = _haversine(lat1, lon1, lat2, lon2) * _CORRIDOR_FACTOR
    fuel_kg = dist_km * _FUEL_KG_KM
    return round(fuel_kg, 1), round(dist_km, 0)


def _gen_meteo(rng: random.Random, franja: str) -> Dict[str, Any]:
    """Genera condiciones meteo y su sobreconsumo de combustible (%)."""
    ajuste = {"manana": (1.0, 1.2), "tarde": (0.6, 0.8), "noche": (1.5, 0.7)}
    niebla_mult, viento_mult = ajuste[franja]

    viento_kt = max(0, round(rng.gauss(12, 6) * viento_mult))
    visibilidad_km = round(max(0.5, rng.gauss(15, 5) / niebla_mult), 1)
    lluvia = rng.random() < 0.25
    tormenta = rng.random() < 0.08
    niebla = visibilidad_km < 5

    pct_extra = 0.0
    motivos: List[str] = []
    if tormenta:
        pct_extra += 0.04
        motivos.append("TORMENTA +4%")
    if niebla:
        pct_extra += 0.03
        motivos.append(f"NIEBLA (vis {visibilidad_km}km) +3%")
    if lluvia:
        pct_extra += 0.01
        motivos.append("LLUVIA +1%")
    if viento_kt > 30:
        pct_extra += 0.02
        motivos.append(f"VIENTO FUERTE {viento_kt}kt +2%")
    elif viento_kt > 20:
        pct_extra += 0.01
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


def _generate_weather(seed: int = 42) -> Dict[str, Dict[str, Any]]:
    """Devuelve {aeropuerto: {franja: meteo}} para los aeropuertos de referencia."""
    rng = random.Random(seed)
    meteo: Dict[str, Dict[str, Any]] = {}
    for code in sorted(_AIRPORTS):
        meteo[code] = {}
        for franja in _FRANJAS:
            meteo[code][franja] = _gen_meteo(rng, franja)
    return meteo


def _build_transfer_data(vuelos: List[Dict[str, Any]], seed: int = 42) -> Dict[str, Any]:
    """Genera datos meteorológicos y combustible base para la lista de vuelos."""
    meteo = _generate_weather(seed)
    for v in vuelos:
        fuel, dist = _combustible_base(v["origen"], v["destino"])
        v["fuel_base_kg"] = fuel
        v["dist_km"] = dist
    return {"vuelos": vuelos, "meteo": meteo, "franjas": _FRANJAS}


def _fuel_franja(fuel_base: float, wx_origen: dict, wx_destino: dict) -> float:
    """Combustible total (kg) de un vuelo en una franja."""
    pct = 1.0 + wx_origen["pct_extra"] + wx_destino["pct_extra"]
    return round(fuel_base * pct, 1)


def _motivos_combinados(wx_origen: dict, wx_destino: dict) -> List[str]:
    partes: List[str] = []
    for m in wx_origen["motivos"]:
        partes.append(f"Orig: {m}")
    for m in wx_destino["motivos"]:
        partes.append(f"Dest: {m}")
    return partes if partes else ["Sin sobreconsumo"]


def _solve_flights(data: Dict[str, Any]) -> Dict[str, Any]:
    """Para cada vuelo elige la franja con menor consumo de combustible."""
    vuelos = data["vuelos"]
    meteo = data["meteo"]
    franjas = data["franjas"]

    resultados: List[Dict[str, Any]] = []
    total_optimo = 0.0
    total_peor = 0.0

    for v in vuelos:
        origen = v["origen"]
        destino = v["destino"]
        base = v["fuel_base_kg"]

        opciones: List[Dict[str, Any]] = []
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
        peor = max(opciones, key=lambda x: x["fuel_kg"])
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


# ── Endpoint – Transfer ──

@router2.post("/transfer", response_model=TransferResponse,
               summary="Optimizar transporte entre sucursales Aire/Mar – Minimizar combustible por franja horaria")
def optimize_transfer(req: TransferRequest) -> TransferResponse:
    """
    Minimiza el consumo de combustible de una flota de aviones eligiendo
    la mejor franja horaria (mañana / tarde / noche) para cada vuelo.

    **Flujo interno:**
    1. Genera condiciones meteorológicas (viento, visibilidad, lluvia, tormentas)
       para cada aeropuerto en cada franja según la seed proporcionada.
    2. Calcula el combustible base por vuelo (distancia Haversine × factor corredor × consumo/km).
    3. Aplica penalizaciones meteorológicas (% extra realista) en origen y destino.
    4. Elige la franja de menor consumo para cada vuelo.
    5. Devuelve el detalle por vuelo, la meteo utilizada y un resumen de ahorro total.

    **Aeropuertos soportados:** LEJ, CDG, FRA, MAD, BCN, BRU, EMA, LIS, MXP, VIE.
    """
    # Validar que los aeropuertos existen
    for v in req.vuelos:
        if v.origen not in _AIRPORTS:
            raise HTTPException(status_code=422,
                                detail=f"Aeropuerto de origen desconocido: '{v.origen}'. "
                                       f"Válidos: {sorted(_AIRPORTS.keys())}")
        if v.destino not in _AIRPORTS:
            raise HTTPException(status_code=422,
                                detail=f"Aeropuerto de destino desconocido: '{v.destino}'. "
                                       f"Válidos: {sorted(_AIRPORTS.keys())}")

    vuelos_raw = [{"id": v.id, "origen": v.origen, "destino": v.destino} for v in req.vuelos]

    try:
        data = _build_transfer_data(vuelos_raw, seed=req.weather_seed)
        result = _solve_flights(data)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Error en el solver de transferencia: {exc}") from exc

    return TransferResponse(**result)
