#ifndef CLOSED_HPP
#define CLOSED_HPP

#include <vector>

// Lista de nodos visitados
class ClosedList {
public:
    ClosedList();
    ClosedList(int n);

    void init(int n);              // Inicializa con n nodos
    void insert(int u);            // Marca el nodo u como visitado
    bool contains(int u) const;    // Verifica si u ya ha sido visitado

private:
    std::vector<bool> closed_;     // Vector de nodos visitados
};

#endif