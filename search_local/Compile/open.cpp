#include "open.hpp"

// Constructor vacío
OpenList::OpenList() {}

// Inserta un par (distancia, nodo) en la cola
void OpenList::push(long long distance, int node) {
    pq_.push({distance, node});
}

// Extrae y retorna el elemento con menor distancia
OpenList::Entry OpenList::ExportMinimum() {
    auto top = pq_.top();  // Obtiene el mínimo
    pq_.pop();             // Lo elimina
    return top;
}

// Obtiene el elemento con menor distancia sin extraer
OpenList::Entry OpenList::top() const {
    return pq_.top();
}

// Retorna true si la cola está vacía
bool OpenList::empty() const {
    return pq_.empty();
}