"""
Busca en el grafo DIMAC los nodos más cercanos a los principales
puntos de importación/exportación de USA.
Archivo .co: v <id> <lon*1e6> <lat*1e6>
"""

import math

# Principales puertos, cruces fronterizos y aeropuertos de comercio
# (nombre, latitud, longitud)
POI = [
    # PUERTOS MARÍTIMOS
    ("Puerto de Los Ángeles/Long Beach",    33.7308,  -118.2642),
    ("Puerto de Nueva York/Nueva Jersey",   40.6840,   -74.0600),
    ("Puerto de Houston/Galveston",         29.7370,   -95.0780),
    ("Puerto de Savannah, GA",              32.0835,   -81.0998),
    ("Puerto de Charleston, SC",            32.7765,   -79.9311),
    ("Puerto de Seattle/Tacoma",            47.3400,  -122.3780),
    ("Puerto de Baltimore, MD",             39.2700,   -76.5800),
    ("Puerto de Nueva Orleans, LA",         29.9511,   -90.0715),
    ("Puerto de Miami, FL",                 25.7742,   -80.1789),
    ("Puerto de Norfolk/Virginia Beach",    36.8970,   -76.3000),
    ("Puerto de Jacksonville, FL",          30.3272,   -81.6557),
    ("Puerto de Oakland, CA",               37.7970,  -122.2780),
    ("Puerto de Filadelfia, PA",            39.9370,   -75.1440),
    # CRUCES FRONTERIZOS TERRESTRES
    ("Laredo, TX (frontera México)",        27.5036,   -99.5075),
    ("El Paso, TX / Ciudad Juárez",         31.7619,  -106.4850),
    ("Detroit-Windsor Crossing",            42.3223,   -83.0457),
    ("Buffalo-Niagara Falls, NY",           42.8864,   -78.8784),
    ("San Diego / Tijuana (Otay Mesa)",     32.5729,  -116.9730),
    ("Nogales, AZ",                         31.3404,  -110.9347),
    ("Douglas, AZ / Agua Prieta",           31.3447,  -109.5453),
    # AEROPUERTOS INTERNACIONALES PRINCIPALES
    ("Aeropuerto JFK, Nueva York",          40.6413,   -73.7781),
    ("Aeropuerto O'Hare, Chicago",          41.9742,   -87.9073),
    ("Aeropuerto LAX, Los Ángeles",         33.9425,  -118.4081),
    ("Aeropuerto de Anchorage, AK",         61.1744,  -149.9960),
    ("Aeropuerto de Miami, FL",             25.7959,   -80.2870),
    ("Aeropuerto de Louisville (UPS Hub)",  38.1740,   -85.7360),
    ("Aeropuerto de Memphis (FedEx Hub)",   35.0424,   -89.9767),
]

COORD_FILE = "DIMAC/USA-road-d.USA.co"

def haversine_approx(lat1, lon1, lat2, lon2):
    """Distancia aproximada en grados² (suficiente para comparar vecindad)."""
    dlat = lat2 - lat1
    dlon = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return dlat * dlat + dlon * dlon

OUTPUT_FILE = "POIs.txt"

def main():
    # Mejor nodo para cada POI: (dist², node_id, lon, lat)
    best = [(float('inf'), -1, 0.0, 0.0) for _ in POI]

    print(f"Leyendo {COORD_FILE} ...")
    with open(COORD_FILE, "r") as f:
        for line in f:
            if not line.startswith('v '):
                continue
            parts = line.split()
            node_id = int(parts[1])
            lon = int(parts[2]) / 1_000_000
            lat = int(parts[3]) / 1_000_000

            for i, (name, plat, plon) in enumerate(POI):
                d = haversine_approx(lat, lon, plat, plon)
                if d < best[i][0]:
                    best[i] = (d, node_id, lon, lat)

    results = []
    for i, (name, plat, plon) in enumerate(POI):
        d, node_id, lon, lat = best[i]
        dist_km = math.sqrt(d) * 111
        results.append((node_id, name, lat, lon, dist_km))

    sections = {
        "PUERTOS MARÍTIMOS": results[0:13],
        "CRUCES FRONTERIZOS TERRESTRES": results[13:20],
        "AEROPUERTOS INTERNACIONALES": results[20:],
    }

    lines = []
    lines.append("# Nodos DIMAC USA relacionados a puntos clave de importación/exportación")
    lines.append("# Formato: <nodo_id>  <nombre>  (<lat>, <lon>)  delta~<km>km")
    lines.append("")

    for section, items in sections.items():
        lines.append(f"## {section}")
        lines.append("-" * 70)
        for node_id, name, lat, lon, dist_km in items:
            lines.append(f"{node_id:>10}  {name:<45}  ({lat:.4f}, {lon:.4f})  Δ≈{dist_km:.2f}km")
        lines.append("")

    lines.append("# Lista Python:")
    lines.append("POI_NODES = [")
    for node_id, name, lat, lon, dist_km in results:
        lines.append(f'    ({node_id:>10}, "{name}"),  # ({lat:.4f}, {lon:.4f})  Δ≈{dist_km:.2f}km')
    lines.append("]")

    output = "\n".join(lines)
    print(output)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output + "\n")
    print(f"\n→ Guardado en {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
