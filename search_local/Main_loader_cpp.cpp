#include <iostream>
#include <chrono>
#include <string>
#include "Compile/graph.hpp"
#include "Compile/loader.hpp"

// Uso: graph_loader.exe <basename_DIMACS> <archivo_salida.bin>
// Ejemplo: graph_loader.exe DIMAC/USA-road-d.USA DIMAC/USA-road-d.USA.bin
//
// Carga el grafo desde los archivos .gr y .co, construye el grafo inverso
// y serializa todo en un único binario para que graph_search lo lea en ms.

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Uso: " << argv[0] << " <basename_DIMACS> <archivo_salida.bin>\n";
        std::cerr << "Ejemplo: " << argv[0] << " DIMAC/USA-road-d.USA DIMAC/USA-road-d.USA.bin\n";
        return 1;
    }
    std::string basename   = argv[1];
    std::string output_bin = argv[2];

    auto t0 = std::chrono::high_resolution_clock::now();

    std::cout << "Cargando grafo DIMACS desde: " << basename << "\n";
    Graph graph;
    auto stats = Loader::DIMACS(basename, graph);
    std::cout << "  Nodos:  " << graph.size() << "\n";
    std::cout << "  Arcos:  " << stats.edges_processed << "\n";

    auto t1 = std::chrono::high_resolution_clock::now();
    std::cout << "Tiempo carga DIMACS: "
              << std::chrono::duration_cast<std::chrono::milliseconds>(t1 - t0).count()
              << " ms\n";

    std::cout << "Construyendo grafo inverso...\n";
    graph.BuildReverseGraph();

    auto t2 = std::chrono::high_resolution_clock::now();
    std::cout << "Tiempo construccion inverso: "
              << std::chrono::duration_cast<std::chrono::milliseconds>(t2 - t1).count()
              << " ms\n";

    std::cout << "Guardando binario en: " << output_bin << "\n";
    graph.SaveBinary(output_bin);

    auto t3 = std::chrono::high_resolution_clock::now();
    std::cout << "Tiempo escritura binario: "
              << std::chrono::duration_cast<std::chrono::milliseconds>(t3 - t2).count()
              << " ms\n";
    std::cout << "Tiempo total: "
              << std::chrono::duration_cast<std::chrono::milliseconds>(t3 - t0).count()
              << " ms\n";
    std::cout << "Listo. Ejecuta graph_search con los nodos deseados.\n";
    return 0;
}
