#ifndef OPEN_HPP
#define OPEN_HPP

#include <queue>
#include <vector>
#include <utility>
#include <functional>

// Cola de prioridad
class OpenList {
public:
    using Entry = std::pair<long long, int>;  // (distancia, nodo)
    OpenList();

    void push(long long distance, int node);  // Inserta un nodo
    Entry ExportMinimum();                    // Extrae el nodo con menor distancia
    Entry top() const;                        // Obtiene el nodo con menor distancia sin extraer

    bool empty() const;                       // Verifica si está vacía

private:
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> pq_;  // Min-heap
};

#endif