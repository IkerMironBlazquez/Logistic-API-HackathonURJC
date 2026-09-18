"""Router para el servicio de búsqueda de caminos (A* Bidireccional)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import subprocess as ss
import re
import os
import numpy as np
from scipy.spatial import cKDTree as cKDTree22

router1 = APIRouter()

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GRAPH_SEARCH_BIN = os.path.join(_BACKEND_DIR, "graph_search")
CO_FILE = os.path.join(_BACKEND_DIR, "DIMAC", "USA-road-d.USA.co")
_USE_WSL = os.name == "nt"  # En Windows el binario es Linux → usar WSL

# El árbol de búsqueda (Global) — se construye una sola vez en el startup
_kdt: cKDTree22 | None = None
_node_ids: np.ndarray | None = None  # shape (N,)  dtype int32


class Position(BaseModel):
    lat: float
    lon: float


class SearchResponse(BaseModel):
    source_lat: float
    source_lon: float
    target_lat: float
    target_lon: float
    source_node: int
    target_node: int
    found: bool
    cost: int | None = None
    nodes_expanded: int | None = None
    execution_time_ms: int | None = None
    path: list[int] = []
    geometry: list[Position] = []


def _nearest_node(lat: float, lon: float) -> int:
    """Devuelve el ID del nodo del grafo más cercano a la posición dada."""
    if _kdt is None:
        raise HTTPException(status_code=503, detail="Árbol de búsqueda no inicializado. El servidor aún está cargando.")
    _, idx = _kdt.query([lat, lon])
    return int(_node_ids[idx])


def load_kdt():
    """Carga el KD-Tree con las posiciones respecto al grafo."""
    global _kdt, _node_ids
    print("Cargando (lat, lon) desde el archivo .co...")
    node_ids = []
    lats = []
    lons = []
    co_path = os.path.abspath(CO_FILE)
    with open(co_path, "r") as f:
        for line in f:
            if line.startswith('v '):
                parts = line.split()
                node_ids.append(int(parts[1]))
                lons.append(int(parts[2]) / 1_000_000)  # x → lon
                lats.append(int(parts[3]) / 1_000_000)  # y → lat
    _node_ids = np.array(node_ids, dtype=np.int32)
    positions = np.column_stack([lats, lons])  # shape (N, 2): [lat, lon]
    _kdt = cKDTree22(positions)
    print(f"KD-tree construido con {len(node_ids):,} nodos.")


@router1.get("", response_model=SearchResponse)
def search_path(source_lat: float, source_lon: float, target_lat: float, target_lon: float):
    """
    Encuentra el camino óptimo entre 2 puntos geográficos en el grafo USA-road DIMACS.
    Recibe posición (lat, lon) y resuelve internamente los nodos más cercanos...
    Usa A* Bidirectional con la distancia euclídea como heurística.
    
    Args:
        source_lat: Latitud del punto de origen
        source_lon: Longitud del punto de origen
        target_lat: Latitud del punto de destino
        target_lon: Longitud del punto de destino
    
    Returns:
        SearchResponse con el camino, coste, coordenadas y métricas
    """
    source = _nearest_node(source_lat, source_lon)
    target = _nearest_node(target_lat, target_lon)
    
    backend_dir = _BACKEND_DIR
    try:
        if _USE_WSL:
            # Convertir ruta Windows a ruta WSL (/mnt/c/...)
            wsl_dir = backend_dir.replace("\\", "/").replace("C:", "/mnt/c").replace("c:", "/mnt/c")
            cmd = ["wsl", "-e", "bash", "-c",
                f"cd '{wsl_dir}' && ./graph_search {source} {target}"]
        else:
            cmd = [GRAPH_SEARCH_BIN, str(source), str(target)]
        result = ss.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutos de timeout para búsquedas complejas
            cwd=backend_dir,
        )
    except ss.TimeoutExpired:
        raise HTTPException(status_code=504, detail="El algoritmo superó el tiempo límite.")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Ejecutable no encontrado: {GRAPH_SEARCH_BIN}")

    output = result.stdout

    if "No existe camino" in output:
        return SearchResponse(
            source_lat=source_lat, source_lon=source_lon,
            target_lat=target_lat, target_lon=target_lon,
            source_node=source, target_node=target,
            found=False
        )

    cost = None
    m = re.search(r"Coste total:\s*(\d+)", output)
    if m:
        cost = int(m.group(1))

    nodes_expanded = None
    m = re.search(r"Nodos expandidos:\s*(\d+)", output)
    if m:
        nodes_expanded = int(m.group(1))

    exec_time = None
    m = re.search(r"Tiempo de ejecución:\s*(\d+)\s*ms", output)
    if m:
        exec_time = int(m.group(1))

    path: list[int] = []
    m = re.search(r"Camino:\n(.+)", output)
    if m:
        # Quitar los costes de arista "(X)" para extraer solo los nodos (Revisar)
        clean = re.sub(r"\s*-\s*\(\d+\)\s*-\s*", " ", m.group(1))
        path = [int(x) for x in clean.split()]

    if cost is None:
        raise HTTPException(status_code=500, detail=f"No se pudo parsear la salida:\nSTDOUT: {output!r}\nSTDERR: {result.stderr!r}\nRETURNCODE: {result.returncode}")

    # Parsear posiciones en el output
    geometry = []
    m = re.search(r"Posiciones:\n(.+?)\n\n", output, re.DOTALL)
    if m:
        coord_text = m.group(1).strip()
        for line in coord_text.split('\n'):
            parts = line.strip().split()
            if len(parts) == 2:
                lat = float(parts[0])
                lon = float(parts[1])
                geometry.append(Position(lat=lat, lon=lon))

    return SearchResponse(
        source_lat=source_lat,
        source_lon=source_lon,
        target_lat=target_lat,
        target_lon=target_lon,
        source_node=source,
        target_node=target,
        found=True,
        cost=cost,
        nodes_expanded=nodes_expanded,
        execution_time_ms=exec_time,
        path=path,
        geometry=geometry,
    )
