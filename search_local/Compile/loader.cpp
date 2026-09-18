#include "loader.hpp"
#include <fstream>
#include <sstream>
#include <thread>
#include <execution>
#include <vector>
#include <iostream>
#include <tuple>
#include <algorithm>

// Carga un grafo desde archivos DIMACS (.gr y .co)
Loader::Stats Loader::DIMACS(const std::string& basename, Graph& G) {
    Stats stats{0, 0};
    std::string fileGR = basename + ".gr";  // Archivo de aristas
    std::string fileCO = basename + ".co";  // Archivo de posiciones (Latitud y longitud)
    // Archivo .co
    {
        std::ifstream fin(fileCO);
        if (!fin) {
            return stats;
        }
        // Primera pasada: encontrar el nodo máximo
        std::string line;
        int maxNode = 0;
        std::vector<std::tuple<int, double, double>> coords;
        while (std::getline(fin, line)) {
            if (line.size() > 0 && line[0] == 'v') {  // Líneas que empiezan con 'v'
                std::istringstream iss(line);
                char c;
                int id;
                double x, y;
                iss >> c >> id >> x >> y;
                // Convertir a grados
                x = x / 1000000.0;
                y = y / 1000000.0;
                coords.push_back({id, x, y});
                maxNode = std::max(maxNode, id);
            }
        }
        stats.vertices_processed = coords.size();
        G.resize(maxNode);
        for (auto& [id, x, y] : coords) {
            G.SetNewPoint(id, x, y);
        }
    }
    // Archivo .gr
    std::ifstream fin(fileGR);
    if (!fin) {
        return stats;
    }
    // Carga todas las líneas en memoria
    std::vector<std::string> lines;
    lines.reserve(5'000'000);
    {
        std::string line;
        while (std::getline(fin, line))
            lines.push_back(std::move(line));
    }
    // Procesamiento paralelo con hilos
    int H = std::thread::hardware_concurrency();  // Número de cores
    if (H == 0) H = 4;
    const int N = lines.size();
    int capacity = N / H;  // Líneas por thread
    std::vector<std::vector<std::tuple<int,int,int>>> local(H);  // Aristas locales por thread
    std::vector<std::thread> threads;
    threads.reserve(H);
    // Crea hilos para procesar las líneas en paralelo
    for (int i = 0; i < H; ++i) {
        int start = i * capacity;
        int end   = (i == H - 1 ? N : start + capacity);
        threads.emplace_back([&, i, start, end] {
            for (int j = start; j < end; j++) {
                const std::string& s = lines[j];
                if (s.size() > 0 && s[0] == 'a') {  // Líneas que empiezan con 'a' (aristas)
                    std::istringstream iss(s);
                    char c;
                    int u, v, w;  // u: origen, v: destino, w: peso
                    iss >> c >> u >> v >> w;
                    local[i].push_back({u, v, w});
                }
            }
        });
    }
    // Espera a que terminen todos los hilos
    for (auto& t : threads) {
        if (t.joinable()) t.join();
    }
    // Encuentra el nodo con mayor ID
    int maxNode = 0;
    for (auto& vec : local)
        for (auto& [u, v, w] : vec)
            maxNode = std::max({maxNode, u, v});
    // Redimensiona el grafo y añade todas las aristas
    G.resize(maxNode);
    for (auto& vec : local) {
        stats.edges_processed += vec.size();
        for (auto& [u, v, w] : vec)
            G.NewEdge(u, v, w);
    }
    return stats;
}
