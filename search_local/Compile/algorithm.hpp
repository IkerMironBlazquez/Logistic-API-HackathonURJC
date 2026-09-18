#ifndef ALGORITHM_HPP
#define ALGORITHM_HPP

#include "graph.hpp"
#include <vector>
#include <limits>

// Clase para los algoritmos de búsqueda (Distancia mínima)
class Algorithm {
public:
    // Tipos de heurísticas disponibles para A*
    enum class HeuristicType {
        NONE,        // Sin heurística (Dijkstra)
        GEODESIC,    // Distancia geodésica
        EUCLIDEAN    // Distancia euclídea
    };

    // Estructura para el resultado
    struct Result {
        std::vector<int> dist;       // Distancias
        std::vector<int> prev;       // Nodos previos en el camino óptimo
        int nodes_expanded;          // Número de nodos expandidos
        
        Result() : nodes_expanded(0) {}
        
        // Verifica si existe un camino hasta el nodo objetivo
        bool Existence(int target) const;
        
        // Retorna el coste hasta el nodo objetivo
        int FinalCost(int target) const;
        
        // Reconstruye el camino hasta el objetivo
        std::vector<int> Path(int target) const;
    };

    // Estructura para el resultado de A* (Bidirectional)
    struct BidirectionalResult {
        int cost;                       // Camino óptimo (Coste)
        std::vector<int> path;          // Camino completo
        int nodes_expanded_forward;     // Nodos expandidos en búsqueda original
        int nodes_expanded_backward;    // Nodos expandidos en búsqueda backward
        int met_node;                   // Nodo en el que se encuentran
        bool found;                     // Resultado (True/False)
        
        BidirectionalResult() : cost(INF), nodes_expanded_forward(0), 
                                nodes_expanded_backward(0), met_node(-1), found(false) {}
    };

    // Ejecuta el algoritmo A* con la heurística especificada
    static Result AStar(const Graph& graph, int source, int target, HeuristicType heuristic = HeuristicType::EUCLIDEAN);
    
    // Ejecuta el algoritmo A* (Bidirectional) (sin hilos)
    static BidirectionalResult BidirectionalAStar(const Graph& graph, int source, int target, HeuristicType heuristic = HeuristicType::EUCLIDEAN);
    
    // Ejecuta el algoritmo de Dijkstra (A* sin heurística) (Herencia)
    static Result Dijkstra(const Graph& graph, int source, int target = -1);

private:
    static constexpr int INF = std::numeric_limits<int>::max();  // Valor infinito
    
    // Calcula el valor heurístico entre dos nodos
    static double CalculateHeuristic(const Graph& graph, int from, int to, HeuristicType heuristic);
    
    // Calcula la distancia geodésica (Harversine) entre dos puntos (Plano esférico)
    static double Geodesic(double lat1, double lon1, double lat2, double lon2);
    
    // Calcula la distancia euclídea entre dos puntos
    static double Euclidean(double x1, double y1, double x2, double y2);
};

#endif
