import heapq
import re

# -------------------- GLOBAL GRAPH --------------------
GRAPH_FILE = "weighted_adj_list.txt"
graph = {}  # global graph loaded at startup


# -------------------- READ GRAPH --------------------
def read_adjacency_list(filename):
    """
    Reads weighted adjacency list from a file and ensures bidirectional edges.
    Expected format:
        0: 1 (12.85m), 2 (10.43m)
        1: 0 (12.85m), 2 (11.67m)
    """
    g = {}
    with open(filename, 'r') as f:
        for line in f:
            if ':' not in line:
                continue

            node, rest = line.strip().split(':')
            node = int(node.strip())

            neighbors = {}
            matches = re.findall(r'(\d+)\s*\(([\d.]+)m\)', rest)
            for nbr, dist in matches:
                neighbors[int(nbr)] = float(dist)

            g[node] = neighbors

    # ✅ Ensure bidirectional edges (undirected graph)
    for node, nbrs in list(g.items()):
        for nbr, dist in nbrs.items():
            if nbr not in g:
                g[nbr] = {}
            if node not in g[nbr]:
                g[nbr][node] = dist

    return g


# -------------------- HEURISTIC FUNCTION --------------------
def heuristic(a, b):
    """Dummy heuristic (acts like Dijkstra since we have no coordinates)."""
    return 0


# -------------------- A* SEARCH FUNCTION --------------------
def a_star(start, goal):
    """
    A* Search Algorithm using global graph.
    Finds the shortest path between start and goal.
    """
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {node: float('inf') for node in graph}
    g_score[start] = 0
    f_score = {node: float('inf') for node in graph}
    f_score[start] = heuristic(start, goal)

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            # Reconstruct path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path, g_score[goal]

        for neighbor, dist in graph[current].items():
            tentative_g = g_score[current] + dist
            if tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    return [], float('inf')


# -------------------- MAIN --------------------
if __name__ == "__main__":
    # Load the global graph once
    graph = read_adjacency_list(GRAPH_FILE)
    print(f"✅ Graph loaded from '{GRAPH_FILE}' with {len(graph)} nodes.")
    print("Available nodes:", sorted(graph.keys()))

    try:
        start = int(input("Enter source node: "))
        goal = int(input("Enter destination node: "))

        if start not in graph or goal not in graph:
            print("❌ Invalid node numbers.")
        else:
            path, cost = a_star(start, goal)
            if path:
                print(f"\n✅ Shortest Path: {' → '.join(map(str, path))}")
                print(f"📏 Total Distance: {round(cost, 2)} meters")
            else:
                print("⚠️ No path found between the given nodes.")
    except ValueError:
        print("❌ Please enter valid integer node IDs.")
