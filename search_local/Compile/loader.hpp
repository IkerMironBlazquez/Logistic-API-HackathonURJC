#ifndef LOADER_HPP
#define LOADER_HPP

#include <string>
#include "graph.hpp"

// Carga un grafo desde un archivo
class Loader {
public:
    // Estructura para estadísticas de carga
    struct Stats {
        int vertices_processed;  // Vértices cargados del .co
        int edges_processed;     // Arcos cargados del .gr
    };
    
    // Carga un grafo en formato DIMACS (.gr y .co)
    static Stats DIMACS(const std::string& basename, Graph& G);
};

#endif