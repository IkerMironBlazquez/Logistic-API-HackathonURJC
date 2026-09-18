#include <iostream>
#include <string>
#include <chrono>
#include "Compile/graph.hpp"
#include "Compile/algorithm.hpp"

int main(int argc, char* argv[]) {
    auto start_time = std::chrono::high_resolution_clock::now();
    if (argc != 3) {
        std::cerr << "Uso: " << argv[0] << " <nodo_1> <nodo_2>\n";
        return 1;
    }
    // Parámetros fijos para el servicio
    int source = std::stoi(argv[1]);
    int target = std::stoi(argv[2]);
    const std::string bin_path = "DIMAC/USA-road-d.USA.bin";
    const Algorithm::HeuristicType heuristic = Algorithm::HeuristicType::EUCLIDEAN;
    // Cargar el grafo desde el binario precomputado
    std::cout << "Cargando grafo desde binario: " << bin_path << "\n";
    Graph graph;
    if (!graph.LoadBinary(bin_path)) {
        std::cerr << "Error: no se pudo abrir " << bin_path << "\n";
        std::cerr << "Ejecuta primero: graph_loader.exe DIMAC/USA-road-d.USA DIMAC/USA-road-d.USA.bin\n";
        return 1;
    }
    std::cout << "Grafo cargado con " << graph.size() << " nodos\n";
    // Ejecutar A* Bidireccional con heurística euclídea
    std::cout << "Ejecutando A* Bidirectional (heurística euclídea)\n";
    std::cout << "Desde nodo " << source << " hasta nodo " << target << "...\n";
    auto algorithm_start = std::chrono::high_resolution_clock::now();
    auto bi_result = Algorithm::BidirectionalAStar(graph, source, target, heuristic);
    auto algorithm_end = std::chrono::high_resolution_clock::now();
    if (!bi_result.found) {
        std::cout << "No existe camino\n";
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
        std::cout << "Tiempo total de ejecución: " << duration.count() << " ms\n";
        return 0;
    }
    std::cout << "Coste total: " << bi_result.cost << "\n";
    int total_expansions = bi_result.nodes_expanded_forward + bi_result.nodes_expanded_backward;
    std::cout << "Nodos expandidos: " << total_expansions << "\n";
    auto algorithm_duration = std::chrono::duration_cast<std::chrono::milliseconds>(algorithm_end - algorithm_start);
    std::cout << "Tiempo de ejecución: " << algorithm_duration.count() << " ms\n";
    if (algorithm_duration.count() > 0) {
        double expansions_per_sec = (total_expansions * 1000.0) / algorithm_duration.count();
        std::cout << "Expansiones: " << static_cast<int>(expansions_per_sec) << " nodos/s\n";
    }
    // Imprimir el camino con costes de arista
    std::cout << "\nCamino:\n";
    for (size_t i = 0; i < bi_result.path.size(); ++i) {
        std::cout << bi_result.path[i];
        if (i < bi_result.path.size() - 1) {
            int u = bi_result.path[i];
            int v = bi_result.path[i+1];
            int edge_cost = 0;
            for (const auto& [neighbor, weight] : graph.neighbors(u)) {
                if (neighbor == v) {
                    edge_cost = weight;
                    break;
                }
            }
            std::cout << " - (" << edge_cost << ") - ";
        }
    }
    std::cout << "\n";

    // Imprimir posiciones
    std::cout << "\nPosiciones:\n";
    for (size_t i = 0; i < bi_result.path.size(); ++i) {
        auto [lon, lat] = graph.getC(bi_result.path[i]);
        std::cout << lat << " " << lon;
        if (i < bi_result.path.size() - 1) {
            std::cout << "\n";
        }
    }
    std::cout << "\n";

    auto end_time = std::chrono::high_resolution_clock::now();
    auto total_duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    std::cout << "\nTiempo total de ejecución: " << total_duration.count() << " ms\n";
    return 0;
}
