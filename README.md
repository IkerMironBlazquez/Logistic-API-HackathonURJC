# Idea Hackathon_URJC Fase 1

Documentación inicial

## Reto: Logística por DHL

Optimizar la cadena de suministro en base a la sostenibilidad, generando oportunidades:

Se plantea un backend con FastAPI, Uvicorn y Pydantic en Microsoft Azure que tenga 3 servicios principales:

    - Búsqueda optimizada mediante Bidirectional A* (Road) para importaciones y exportaciones en USA (Ejemplo DIMAC), entre un punto determinado de exportación o importación por mar o aire y un punto determinado que se ajustará a los disponibles en el mapa para hacer los cambios.
    Oportunidad: Coste de sostenibilidad (Energía) en las redes viales que son las rutas menos optimizadas a diferencia de las marítimas y aéreas

    - Programación lineal útil para cualquier trabajador de sucursal o directivo sin conocimientos en el ámbito, que dado determinados datos, optimice el número de trayectos que se deben hacer.
    Oportunidad: Optimiza el número de trayectos a realizar, es decir los paquetes entregados y su eficacia a través de datos relevantes.
    Extra: Optimización entre sucursales por transporte aéreo/marítimo, no solo de envíos directos (Orientado a directivos...)

    - Aprendizaje automático para determinar zonas con mayor densidad de recibos de paquetes día a día y así optimizar los envíos en cualquier plazo, ya sea para una organización directa o para elegir ubicaciones para nuevas sucursales/almacenes de la empresa.
    Predecir: nº pedidos en celda H3 en día t+1
    Oportunidad: Last mile, puedes obtener la densidad de paquetes en cada zona para el día siguiente o incluso el mes siguiente...

El frontend se planea hacer de forma completa en Hostinger, pero por si acaso, se creará otro estático para Microsoft Azure/Netlify.

### Servicio 1

    Implementación de algoritmos de búsqueda para encontrar caminos óptimos en redes viales reales utilizando grafos DIMAC de los Estados Unidos.

**Algoritmos implementados:**

Dijkstra (Fuerza Bruta)

- Sin heurística (h(n) = 0)
- Expande nodos uniformemente
- Usado como referencia para comparaciones

Astar

- Función de evaluación: f(n) = g(n) + h(n)
- Búsqueda dirigida hacia el objetivo
- Garantía de optimalidad con heurísticas admisibles

Astar (Bidirectional)

- Búsqueda simultánea desde origen y destino
- Criterio de parada de Ira Pohl
- Nodos expandidos mínimos...
- Balance de heurísticas (división por 2) para garantizar optimalidad

**Heurísticas implementadas:**

- Distancia Geodésica (Haversine): Considera la curvatura terrestre
- Distancia Euclídea: Por plano

**Resultados experimentales:**

Nodos expandidos respecto a Dijkstra:

- A*: 10-12% de reducción promedio
- A* Bidireccional: 35-50% de reducción promedio, hasta 85% en casos óptimos

Tiempo de ejecución:

- A* Bidireccional Euclídeo: factor de aceleración 1.15x promedio, hasta 5.6x en casos óptimos
- Instancia máxima: USA completo con 23.9M nodos, 58.3M aristas

Para la medición de tiempos es necesario estandarizar el equipo a utilizar...

**Estructuras de datos:**

- Grafo con listas de adyacencia: O(|V| + |E|)
- Cola de prioridad (min-heap) para lista abierta
- Vector T/F para nodos expandidos
- Vectores auxiliares para distancias, además de predecesores

**Pruebas automatizadas:**

Se recomienda descargar todos los mapas:

    ```bash
    python test.py        # Pruebas en todas las instancias disponibles
    python MAX10.py       # Pruebas en instancia USA completa
    ```

Instancias disponibles en [9th DIMAC Challenge](http://www.diag.uniroma1.it/challenge9/).

**Análisis y resultados de búsqueda:**

- A* (Bidirectional) con distancia euclídea es la configuración óptima (Haversine también disponible)
- Descenso consistente de 35-50% en nodos expandidos respecto a A*
- Escalabilidad comprobada hasta 23.9M de nodos
- Optimalidad garantizada mediante criterio de Ira Pohl y balance de heurísticas completo

### Servicio 2

**Funcionamiento del servicio**
El empresario introduce los siguientes datos mediante un archivo: lista de depósitos, flota de cada depósito y lista de clientes. Inclyendo en los datos las coordenadas de los clientes y de los depósitos.

Después internamente se calculan las distancias necesarias para construir la matriz de distancias (mediante build_problem), que lee el JSON del usuario, calcula la distancia Haversine entre todos los pares de nodos, multiplica por un factor para aproximar la distancia real por carretera y devuelve la matriz de distancias.

Posteriormente se le pasarían todos los datos al solver para aplicarlo a nuestro modelo de programacion lineal.

**COP Solver**
El modelo se descompone en 2 fases, asignación de clientes a depósitos y para cada depósito con clientes asignados se resuelve un CVRP.

-Fase 1: esta fase es una heuristica greedy que decide que depósito atenderá a cada cliente, esta fase solo se establece "este cliente es parte de este depósito", para ello se recorren todos los clientes uno por uno y asigna cada uno al deposito más cercano que aún tengo capacidad disponible. Se realiza de la siguiente manera:

    -Primero se calcula la capacidad total de cada deposito (según las VAN y TRUCKS) y el volumen del cliente (según sus paquetes).

    -Para cada cliente, ordena los depositos por distancias (de menor a mayor), usando la matriz de distancias precalculada.

    -Se intentan asignar en 3 pasadas(con umbrales de capacidad cada vez más permisivos):
        Volumen acumulado + volumen del cliente < 80% de la capacidad del depósito.
        Volumen acumulado + volumen del cliente < 95% de la capacidad del depósito.
        Sin restricciones de capacidad.

-Fase 2: esta fase se ejecuta una vez por cada deposito que tenga clientes asignados.
    -Preparacion del modelo: se crea un grafo donde Nodo 0(es el deposito) y luego Nodos1...N (son los clientes).
    -Se expande la flota del depósito, es decir se crean tantos vehículos como tenga el depósito.
    -Se construye la matriz de distancias, con las distancias entre todos los pares de nodos(cliente-cliente, cliente-deposito)

    **COP**
    Se trata de un CSP que ademas de asegurarte que la solución es factible tambien te asegura que sea óptima.

    FUNCIÓN OBJETIVO:
    Minimizar la distancia total recorrida por todos los vehículos, por lo tanto se busca minimizar la suma de la distancia de todos los arcos recorridos por todos los vehículos.
   
    RESTRICCIONES:
    R1: La capacidad de los vehículos no sea excedida.
    R2: No es obligatorio usar todos los vehículos, para reducir la penalización si no hacen falta todos los vehículos.
    R3: Cada cliente debe ser etendido exactamente una vez y no se debe dejar ningún cliente sin visitar.
    R4: Si un vehículo llega a un punto debe de salir de ese punto.
    R5: Todos los vehículos que salen de un deposito deben volver al mismo deposito.

**Datos necesarios**
-Lista de depósitos: tan solo se necesita el Id del depósito. (D1, D2, D3)

-Flota de cada depósito: "VAN": número de furgonetas, "TRUCK": número de camiones.

-Lista de clientes: con su Id, nS: paquetes pequeños, nM: paquetes medianos, nL: paquetes grandes.

-Matriz de distancias:
    Distancias depósitos a depósito: ("D1", "D2"): X ...
    Distancia entre depósito a cliente: ("C1", "D1"): X
    Distancias cliente a cliente: ("C1", "C2"): X

### Servicio 3

**Pipeline (Laboratorio):**

    - Datos brutos de pedidos (Posición y fecha de aceptación como mínimo)
    - Convertimos posición a zonas (celdas H3)
    - Agregamos por día
    - Creamos memoria temporal (lags)
    - Entrenamos LightGBM
    - Validamos respecto a tiempo
    - Ajuste de hiperparámetros
    - Obtenemos el modelo final

**Resultados de entrenamiento**
    1.75 MAE, es decir, se equivoca en promedio menos de 2 pedidos por zona - 460 m^2 (H3)

**Qué ofrece el modelo:**

    - Asignar repartidores con antelación a las zonas con más carga
    - Planificar rutas antes de tener los pedidos reales
    - Redistribuir recursos entre zonas según la demanda esperada (Last mile...)

**Funcionalidad:**

    El modelo aprende un patrón temporal universal: "si ayer hubo X pedidos, mañana habrá Y". La zona queda implícita en el historial que se le pasa. (Modelo: Hangzhou)
  