#include "closed.hpp"

// Constructor vacío
ClosedList::ClosedList() {}

// Constructor con int n
ClosedList::ClosedList(int n) {
    init(n);
}

// Inicializa el vector con n+1 elementos en false
void ClosedList::init(int n) {
    closed_.assign(n + 1, false);
}

// Marca el nodo u como visitado
void ClosedList::insert(int u) {
    closed_[u] = true;
}

// Retorna true si el nodo u ya ha sido visitado
bool ClosedList::contains(int u) const {
    return closed_[u];
}