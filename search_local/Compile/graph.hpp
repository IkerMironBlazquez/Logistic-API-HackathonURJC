#ifndef GRAPH_HPP
#define GRAPH_HPP

#include <vector>
#include <utility>
#include <string>

// Clase que representa un grafo dirigido
class Graph {
public:
    using Edge = std::pair<int, int>; // Par (destino, peso)
    
    // Constructores
    Graph();
    Graph(int n);

    // Redimensiona el grafo
    void resize(int n);
    
    // Añade una arista
    void NewEdge(int u, int v, int w);
    
    // Establece una posición
    void SetNewPoint(int u, double longitude, double latitude);

    // Construye el grafo inverso para búsqueda doble
    void BuildReverseGraph();

    // Size
    int size() const;
    
    // Retorna los vecinos (forward)
    const std::vector<Edge>& neighbors(int u) const;
    
    // Retorna los vecinos en el grafo inverso (backward)
    const std::vector<Edge>& neighbors_reverse(int u) const;
    
    // Obtiene latitud y longitud
    std::pair<double, double> getC(int u) const;

    // Serialización binaria
    void SaveBinary(const std::string& path) const;
    bool LoadBinary(const std::string& path);

private:
    int n_;                                            // Número de nodos
    std::vector<std::vector<Edge>> adj_;               // Lista de adyacencia
    std::vector<std::vector<Edge>> adj_reverse_;       // Lista de adyacencia inversa
    std::vector<std::pair<double, double>> points_;    // Posiciones para cada nodo
};

#endif