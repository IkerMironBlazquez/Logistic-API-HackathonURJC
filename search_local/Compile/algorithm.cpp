#include "algorithm.hpp"
#include "open.hpp"
#include "closed.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>

// Implementación de A*
Algorithm::Result Algorithm::AStar(const Graph& graph, int source, int target, HeuristicType heuristic) {
    Result result;
    int n = graph.size();
    result.dist.assign(n + 1, INF);      // Inicializar a infinito
    result.prev.assign(n + 1, -1);       // Inicializar predecesores a -1
    result.nodes_expanded = 0;           // Contador de nodos expandidos
    OpenList open;                       // Lista de nodos por explorar
    ClosedList closed(n);                // Lista de nodos ya visitados
    result.dist[source] = 0;
    double h = CalculateHeuristic(graph, source, target, heuristic);
    open.push(static_cast<int>(h), source);
    // Mientras haya nodos por explorar
    while (!open.empty()) {
        // Extraer nodo con menor f(n)
        auto [f, u] = open.ExportMinimum();
        // Si el nodo ya ha sido visitado, omitir
        if (closed.contains(u)) {
            continue;
        }
        closed.insert(u);
        result.nodes_expanded++;
        // Objetivo
        if (target != -1 && u == target) {
            break;
        }
        // Explorar todos los vecinos para el nodo actual
        for (const auto& [v, w] : graph.neighbors(u)) {
            if (closed.contains(v)) {    // Omitir vecinos ya visitados
                continue;
            }
            // Calcular nuevo coste
            long long new_distance = static_cast<long long>(result.dist[u]) + w;
            // Si encontramos un camino mejor
            if (new_distance < result.dist[v]) {
                result.dist[v] = static_cast<int>(new_distance);  // Actualizar g(v)
                result.prev[v] = u;                               // Actualizar predecesor
                // Calcular f(v) = g(v) + h(v)
                double h_value = CalculateHeuristic(graph, v, target, heuristic);
                int f_value = static_cast<int>(new_distance + h_value);
                open.push(f_value, v);   // Añadir vecino a la lista abierta
            }
        }
    }
    return result;
}

// Algoritmo de Dijkstra: A* sin heurística (h(n) = 0)
Algorithm::Result Algorithm::Dijkstra(const Graph& graph, int source, int target) {
    return AStar(graph, source, target, HeuristicType::NONE);
}

// A* (Bidirectional) (sin hilos) con garantía de optimalidad
Algorithm::BidirectionalResult Algorithm::BidirectionalAStar(const Graph& graph, int source, int target, HeuristicType heuristic) {
    BidirectionalResult result;
    int n = graph.size();
    
    // Estructuras para búsqueda original
    std::vector<int> dist_forward(n + 1, INF);
    std::vector<int> prev_forward(n + 1, -1);
    OpenList open_forward;
    ClosedList closed_forward(n);
    
    // Estructuras para búsqueda backward
    std::vector<int> dist_backward(n + 1, INF);
    std::vector<int> prev_backward(n + 1, -1);
    OpenList open_backward;
    ClosedList closed_backward(n);
    
    // Inicializar
    dist_forward[source] = 0;
    dist_backward[target] = 0;
    
    // Para A* (Bidirectional)  (Balance de heurísticas)
    // garantiza que h_f(n) + h_b(n) <= h*(s,t)
    double h_forward = CalculateHeuristic(graph, source, target, heuristic) / 2.0;
    double h_backward = CalculateHeuristic(graph, target, source, heuristic) / 2.0;
    
    open_forward.push(static_cast<int>(h_forward), source);
    open_backward.push(static_cast<int>(h_backward), target);
    
    int best_path_cost = INF;
    int best_met_node = -1;
    
    // Búsqueda alternada
    while (!open_forward.empty() && !open_backward.empty()) {
        // Verificar criterio de terminación de Pohl (Optimalidad)
        // El camino es óptimo cuando mu_f + mu_b >= best_path_cost
        if (best_path_cost < INF) {
            int mu_f = static_cast<int>(open_forward.top().first);
            int mu_b = static_cast<int>(open_backward.top().first); 
            if (mu_f + mu_b >= best_path_cost) {
                break;  // Garantía de optimalidad
            }
        }
        // Expandir desde la primera búsqueda
        if (!open_forward.empty()) {
            auto [f, u] = open_forward.ExportMinimum();
            if (!closed_forward.contains(u)) {
                closed_forward.insert(u);
                result.nodes_expanded_forward++;
                // Verificar si backward ya visitó este nodo
                if (closed_backward.contains(u)) {
                    int candidate_cost = dist_forward[u] + dist_backward[u];
                    if (candidate_cost < best_path_cost) {
                        best_path_cost = candidate_cost;
                        best_met_node = u;
                    }
                }
                
                // Expandir vecinos
                for (const auto& [v, w] : graph.neighbors(u)) {
                    if (closed_forward.contains(v)) continue;
                    long long new_distance = static_cast<long long>(dist_forward[u]) + w;
                    if (new_distance < dist_forward[v]) {
                        dist_forward[v] = static_cast<int>(new_distance);
                        prev_forward[v] = u;
                        
                        double h_value = CalculateHeuristic(graph, v, target, heuristic) / 2.0;
                        int f_value = static_cast<int>(new_distance + h_value);
                        open_forward.push(f_value, v);
                        
                    }
                }
            }
        }
        // Verificar de nuevo antes de expandir backward
        if (best_path_cost < INF && !open_forward.empty() && !open_backward.empty()) {
            int mu_f = static_cast<int>(open_forward.top().first);
            int mu_b = static_cast<int>(open_backward.top().first);
            
            if (mu_f + mu_b >= best_path_cost) {
                break;
            }
        }
        // Expandir desde backward
        if (!open_backward.empty()) {
            auto [f, u] = open_backward.ExportMinimum();
            if (!closed_backward.contains(u)) {
                closed_backward.insert(u);
                result.nodes_expanded_backward++;
                // Verificar si la primera búsqueda ya visitó este nodo
                if (closed_forward.contains(u)) {
                    int candidate_cost = dist_forward[u] + dist_backward[u];
                    if (candidate_cost < best_path_cost) {
                        best_path_cost = candidate_cost;
                        best_met_node = u;
                    }
                }
                // Expandir vecinos en el grafo inverso
                for (const auto& [v, w] : graph.neighbors_reverse(u)) {
                    if (closed_backward.contains(v)) continue;
                    long long new_distance = static_cast<long long>(dist_backward[u]) + w;
                    if (new_distance < dist_backward[v]) {
                        dist_backward[v] = static_cast<int>(new_distance);
                        prev_backward[v] = u;

                        double h_value = CalculateHeuristic(graph, v, source, heuristic) / 2.0;
                        int f_value = static_cast<int>(new_distance + h_value);
                        open_backward.push(f_value, v);
                        
                    }
                }
            }
        }
    }
    // Verificar si hay camino
    if (best_met_node == -1 || best_path_cost == INF) {
        result.found = false;
        return result;
    }
    // Después de terminar, verificar todos los nodos alcanzados por ambas búsquedas
    for (int v = 1; v <= n; v++) {
        if (dist_forward[v] != INF && dist_backward[v] != INF) {
            int candidate_cost = dist_forward[v] + dist_backward[v];
            if (candidate_cost < best_path_cost) {
                best_path_cost = candidate_cost;
                best_met_node = v;
            }
        }
    }
    // Reconstruir camino
    result.found = true;
    result.cost = best_path_cost;
    result.met_node = best_met_node;
    // Camino desde source hasta el nodo (forward)
    std::vector<int> path_forward;
    int current = best_met_node;
    while (current != -1) {
        path_forward.push_back(current);
        current = prev_forward[current];
    }
    std::reverse(path_forward.begin(), path_forward.end());
    // Camino desde el nodo hasta target (backward, necesita invertirse)
    std::vector<int> path_backward;
    current = prev_backward[best_met_node];
    while (current != -1) {
        path_backward.push_back(current);
        current = prev_backward[current];
    }
    // Combinar caminos
    result.path = path_forward;
    result.path.insert(result.path.end(), path_backward.begin(), path_backward.end());
    
    return result;
}

// Calcula el valor heurístico h(n) entre dos nodos
double Algorithm::CalculateHeuristic(const Graph& graph, int from, int to, HeuristicType heuristic) {
    // Sin heurística: Dijkstra
    if (heuristic == HeuristicType::NONE) {
        return 0.0;
    }
    // Obtener posición de los nodos
    auto [lon1, lat1] = graph.getC(from);
    auto [lon2, lat2] = graph.getC(to);
    if (heuristic == HeuristicType::GEODESIC) {
        return Geodesic(lat1, lon1, lat2, lon2);
    } else if (heuristic == HeuristicType::EUCLIDEAN) {
        return Euclidean(lat1, lon1, lat2, lon2);
    }
    
    return 0.0;
}

// Distancia geodésica
double Algorithm::Geodesic(double lat1, double lon1, double lat2, double lon2) {
    const double R = 6371000.0;
    const double PI = 3.14159265358979323846;
    // Convertir grados a radianes
    double lat1_rad = lat1 * PI / 180.0;
    double lat2_rad = lat2 * PI / 180.0;
    double dLat = (lat2 - lat1) * PI / 180.0;  // Diferencia de latitudes
    double dLon = (lon2 - lon1) * PI / 180.0;  // Diferencia de longitudes
    // Fórmula de Haversine
    // a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
    double a = std::sin(dLat / 2.0) * std::sin(dLat / 2.0) +
               std::cos(lat1_rad) * std::cos(lat2_rad) *
               std::sin(dLon / 2.0) * std::sin(dLon / 2.0);
    // c = 2 * atan2(√a, √(1-a))
    double c = 2.0 * std::atan2(std::sqrt(a), std::sqrt(1.0 - a));
    return R * c; // Distancia en metros
}

// Calcula la distancia euclídea (en línea recta) entre dos puntos en 2D
double Algorithm::Euclidean(double lat1, double lon1, double lat2, double lon2) {
    const double METERS_PER_DEGREE_LAT = 111320.0;
    double lat_avg = (lat1 + lat2) / 2.0;
    const double PI = 3.14159265358979323846;
    double lat_avg_rad = lat_avg * PI / 180.0;
    double meters_per_degree_lon = 111320.0 * std::cos(lat_avg_rad);
    double dx = (lon2 - lon1) * meters_per_degree_lon;  // Diferencia en x
    double dy = (lat2 - lat1) * METERS_PER_DEGREE_LAT;  // Diferencia en y
    return std::sqrt(dx * dx + dy * dy);  // d = √(dx² + dy²) en metros
}
// Verifica si existe un camino desde el origen hasta el nodo objetivo
bool Algorithm::Result::Existence(int target) const {
    return dist[target] != INF;  // Si la distancia no es infinita, hay camino
}
// Retorna el coste total
int Algorithm::Result::FinalCost(int target) const {
    if (!Existence(target)) {
        return -1;
    }
    return dist[target];
}
// Reconstruye el camino desde el origen hasta el objetivo
std::vector<int> Algorithm::Result::Path(int target) const {
    std::vector<int> path;
    if (!Existence(target)) {
        return path;
    }
    int actual = target;
    while (actual != -1) {
        path.push_back(actual);
        actual = prev[actual];
    }
    // Invertir el camino (Estaba de fin a inicio)
    std::reverse(path.begin(), path.end());
    return path;
}
