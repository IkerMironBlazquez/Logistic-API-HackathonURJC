"""
solver.py
Multi-Depot VRP con flota heterogénea (VAN / TRUCK) usando Google OR-Tools.

Estrategia:
  - Misma descomposición en 2 fases que solver_mdvrp:
    1) Asignar cada cliente a su depósito más cercano
    2) Resolver un CVRP por depósito con OR-Tools Routing
  - OR-Tools usa metaheurísticas que dan soluciones prácticamente óptimas en segundos, incluso para cientos de clientes.

Stack: Google OR-Tools (ortools.constraint_solver.routing)

Interfaz idéntica a solver_mdvrp.py → solve_mdvrp(data) → dict
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ortools.constraint_solver import routing_enums_pb2, pywrapcp

# ─────────────────────────── constantes ──────────────────────────────
CAP = {"VAN": 10.0, "TRUCK": 20.0}          # m³
VOL = {"S": 0.04, "M": 0.20, "L": 0.60}    # m³ por paquete

# Factor de escala: OR-Tools trabaja con enteros, así que
# multiplicamos km por este factor para ajustar precisión
_SCALE = 1000  # 3 decimales de precisión


# Vehículos
def build_vehicles(flota: Dict[str, Dict[str, int]]) -> List[Dict[str, str]]:
    """
    Expande la flota en vehículos virtuales-individuales.
    Retorna: [{"id": "D1_VAN_0", "depot": "D1", "type": "VAN"}, ...]
    """
    vehicles: List[Dict[str, str]] = []
    for depot_id, types in flota.items():
        for vtype, count in types.items():
            if vtype not in CAP:
                raise ValueError(f"Tipo de vehículo desconocido: {vtype}")
            for idx in range(count):
                vid = f"{depot_id}_{vtype}_{idx}"
                vehicles.append({"id": vid, "depot": depot_id, "type": vtype})
    return vehicles


# VOLUMEN PARA CADA CLIENTE

def _client_volume(client: dict) -> float:
    nS = client.get("nS", 0)
    nM = client.get("nM", 0)
    nL = client.get("nL", 0)
    return nS * VOL["S"] + nM * VOL["M"] + nL * VOL["L"]


# VALIDACIÓN DE INPUT

def _validate_input(data: dict):
    required = {"depots", "clients", "fleet", "dist_matrix"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Faltan claves en data: {missing}")
    if not data["depots"]:
        raise ValueError("Se necesita al menos un depósito.")
    if not data["clients"]:
        raise ValueError("Se necesita al menos un cliente.")


# ASIGNACIÓN DE CLIENTES A DEPÓSITOS (Fase 1)

def clients_to_depots(
    depots: List[dict],
    clients: List[dict],
    flota: Dict[str, Dict[str, int]],
    dist_matrix: Dict[Tuple[str, str], float],
) -> Dict[str, List[dict]]:
    """
    Asigna cada cliente al depósito más cercano con capacidad suficiente.
    """
    depot_ids = [d["id"] for d in depots]

    # Capacidad total por depósito
    depot_cap = {}
    for did in depot_ids:
        types = flota.get(did, {})
        cap = sum(CAP[vt] * cnt for vt, cnt in types.items())
        depot_cap[did] = cap

    # Volumen asignado a cada depósito
    depot_vol_used: Dict[str, float] = {did: 0.0 for did in depot_ids}

    # Asignar por cercanía
    asignaciones: Dict[str, List[dict]] = {did: [] for did in depot_ids}

    for client in clients:
        cid = client["id"]
        vol = _client_volume(client)

        # Ordenar depósitos por distancia
        dists = []
        for did in depot_ids:
            key = (did, cid)
            alt_key = (cid, did)
            d = dist_matrix.get(key, dist_matrix.get(alt_key, float("inf")))
            dists.append((d, did))
        dists.sort()

        # Asignar al depot más cercano que tenga capacidad (80% max para dejar margen a bin-packing)
        assigned = False
        for _, did in dists:
            if depot_vol_used[did] + vol <= depot_cap[did] * 0.80:
                asignaciones[did].append(client)
                depot_vol_used[did] += vol
                assigned = True
                break

        if not assigned:
            # Segunda pasada: aceptar hasta 95% de capacidad
            for _, did in dists:
                if depot_vol_used[did] + vol <= depot_cap[did] * 0.95:
                    asignaciones[did].append(client)
                    depot_vol_used[did] += vol
                    assigned = True
                    break

        if not assigned:
            # Último recurso: asignar al más cercano
            asignaciones[dists[0][1]].append(client)

    return asignaciones



# RESOLVER

def _solve_sub_vrp(
    depot: dict,
    clients: List[dict],
    vehicles: List[Dict[str, str]],
    dist_matrix: Dict[Tuple[str, str], float],
    time_limit: int = 30,
) -> dict:
    """
    Resuelve un CVRP para un depósito usando OR-Tools Routing.

    Retorna dict con routes, occupancy, objective_km, status.
    """
    if not clients:
        return {
            "status": "optimal",
            "objective_km": 0.0,
            "routes": {},
            "occupancy": {},
        }

    did = depot["id"]
    n_vehicles = len(vehicles)
    n_clients = len(clients)

    # ── Mapeo de nodos: 0 = depósito, 1..N = clientes ──
    nodes = [did] + [c["id"] for c in clients]
    n_nodes = len(nodes)

    # ── Matriz de distancias (escalada a enteros) ──
    dist = [[0] * n_nodes for _ in range(n_nodes)]
    for i in range(n_nodes):
        for j in range(n_nodes):
            if i == j:
                continue
            key = (nodes[i], nodes[j])
            alt = (nodes[j], nodes[i])
            d = dist_matrix.get(key, dist_matrix.get(alt, 999999.0))
            dist[i][j] = int(round(d * _SCALE))

    # ── Demandas (volumen escalado a enteros, en cm³) ──
    # Capacidad en cm³ (litros * 1000)
    vol_scale = 10000  # para mantener precisión con volúmenes pequeños
    demands = [0]  # depot = 0
    for c in clients:
        demands.append(int(round(_client_volume(c) * vol_scale)))

    vehicle_caps = [int(round(CAP[v["type"]] * vol_scale)) for v in vehicles]

    # ── Crear modelo de routing ──
    manager = pywrapcp.RoutingIndexManager(n_nodes, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Callback de distancia
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return dist[from_node][to_node]

    transit_cb_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    # ── Restricción de capacidad ──
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx,
        0,            # sin holgura
        vehicle_caps,  # capacidad por vehículo
        True,         # empezar acumulado en 0
        "Capacity",
    )

    # ── Permitir que no todos los vehículos se usen ──
    for v_idx in range(n_vehicles):
        routing.SetFixedCostOfVehicle(0, v_idx)

    # ── Parámetros de búsqueda ──
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = max(1, time_limit)

    # ── Resolver ──
    solution = routing.SolveWithParameters(search_params)

    if not solution:
        return {
            "status": "infeasible",
            "objective_km": None,
            "routes": {},
            "occupancy": {},
        }

    # ── Extraer rutas ──
    routes: Dict[str, List[str]] = {}
    occupancy: Dict[str, float] = {}
    total_km = 0.0

    for v_idx in range(n_vehicles):
        index = routing.Start(v_idx)
        route_nodes: List[str] = []
        route_load = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route_nodes.append(nodes[node])
            route_load += demands[node]
            index = solution.Value(routing.NextVar(index))

        # Añadir nodo final (depósito)
        route_nodes.append(nodes[manager.IndexToNode(index)])

        # Solo incluir vehículos que visiten al menos un cliente
        n_stops = len([n for n in route_nodes if n != did])
        if n_stops > 0:
            vid = vehicles[v_idx]["id"]
            routes[vid] = route_nodes
            cap = CAP[vehicles[v_idx]["type"]]
            occ = (route_load / vol_scale) / cap
            occupancy[vid] = round(occ, 4)

    total_km = solution.ObjectiveValue() / _SCALE

    status = "optimal" if routing.status() == 1 else "feasible"

    return {
        "status": status,
        "objective_km": round(total_km, 4),
        "routes": routes,
        "occupancy": occupancy,
    }



# FUNCIÓN PRINCIPAL

def solve_mdvrp(data: dict) -> dict:
    """
    Punto de entrada principal — interfaz idéntica a solver_mdvrp.solve_mdvrp().

    Usa descomposición en 2 fases + OR-Tools Routing por depósito.

    Parámetros
    ----------
    data : dict con claves depots, clients, fleet, dist_matrix, k_nn, time_limit

    Retorna
    -------
    dict JSON-serializable con status, objective_km, vehicles_used, routes,
    occupancy, solver_time, gap.
    """
    t0 = time.perf_counter()

    _validate_input(data)

    depots      = data["depots"]
    clients     = data["clients"]
    flota       = data["fleet"]
    dist_matrix = data["dist_matrix"]
    time_limit  = data.get("time_limit", 30)

    # Normalizar claves de dist_matrix a tuplas
    norm_dist: Dict[Tuple[str, str], float] = {}
    for key, val in dist_matrix.items():
        if isinstance(key, tuple):
            norm_dist[key] = float(val)
        elif isinstance(key, str):
            norm_dist[tuple(key.split(","))] = float(val)
        else:
            norm_dist[tuple(key)] = float(val)
    dist_matrix = norm_dist

    # ══════════════════ FASE 1: ASIGNAR CLIENTES ══════════════════
    depot_clients = clients_to_depots(depots, clients, flota, dist_matrix)

    # ══════════════════ FASE 2: VRP POR DEPÓSITO ══════════════════
    all_routes: Dict[str, List[str]] = {}
    all_occupancy: Dict[str, float] = {}
    total_km = 0.0
    worst_status = "optimal"

    n_depots_with_clients = sum(1 for v in depot_clients.values() if v)
    time_per_depot = max(5, time_limit // max(n_depots_with_clients, 1))

    for depot in depots:
        did = depot["id"]
        sub_clients = depot_clients[did]

        if not sub_clients:
            continue

        # Vehículos de este depósito
        sub_fleet = {did: flota[did]}
        vehicles = build_vehicles(sub_fleet)

        # Resolver
        sub_result = _solve_sub_vrp(
            depot, sub_clients, vehicles, dist_matrix,
            time_limit=time_per_depot,
        )

        if sub_result["status"] == "infeasible":
            solver_time = round(time.perf_counter() - t0, 3)
            return {
                "status": "infeasible",
                "objective_km": None,
                "vehicles_used": [],
                "routes": {},
                "occupancy": {},
                "solver_time": solver_time,
                "gap": None,
                "detail": f"Sub-problema del depósito {did} es infeasible "
                          f"({len(sub_clients)} clientes, {len(vehicles)} vehículos)",
            }

        if sub_result["status"] == "feasible":
            worst_status = "feasible"

        all_routes.update(sub_result["routes"])
        all_occupancy.update(sub_result["occupancy"])
        total_km += sub_result["objective_km"]

    solver_time = round(time.perf_counter() - t0, 3)
    vehicles_used = sorted(all_routes.keys())

    return {
        "status": worst_status,
        "objective_km": round(total_km, 4),
        "vehicles_used": vehicles_used,
        "routes": all_routes,
        "occupancy": all_occupancy,
        "solver_time": solver_time,
        "gap": 0.0,  # No hay gap directo en el solver
    }
