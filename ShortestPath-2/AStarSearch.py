import heapq
import re

# -------------------- FILES --------------------
GRAPH_FILE = "weighted_adj_list.txt"
COORDS_FILE = "logged_coordinates.txt"

graph = {}    # global graph
coords = {}   # global coordinates


# -------------------- READ COORDINATES --------------------
def read_coordinates(filename):
    """
    Reads node coordinates from cords.txt
    Format:
    0 17.3970873 78.4897846 500.5
    1 17.3970752 78.4898995 501.32
    """
    c = {}
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Split on commas or whitespace. This handles lines like:
            # 0 17.3973265, 78.4900595, 494.18
            # or CSV: 0,17.3973265,78.4900595,494.18
            parts = [p for p in re.split(r"[,\s]+", line) if p]

            try:
                node = int(parts[0])
            except (ValueError, IndexError):
                # malformed line — skip
                continue

            # Parse lat, lon, alt with graceful degradation.
            try:
                # Accept lines with at least lat and lon. Alt is optional and defaults to 0.0
                lat = float(parts[1]) if len(parts) > 1 else None
                lon = float(parts[2]) if len(parts) > 2 else None
                alt = float(parts[3]) if len(parts) > 3 else 0.0
                c[node] = [lat, lon, alt]
            except ValueError:
                # Try sanitizing numeric strings (remove stray commas/characters)
                def clean_num(s):
                    s = s.strip().rstrip(',')
                    s = re.sub(r'[^0-9eE.+-]', '', s)
                    return float(s)

                try:
                    lat = clean_num(parts[1]) if len(parts) > 1 else None
                    lon = clean_num(parts[2]) if len(parts) > 2 else None
                    alt = clean_num(parts[3]) if len(parts) > 3 else 0.0
                    c[node] = [lat, lon, alt]
                except Exception:
                    # still malformed — skip
                    continue

    return c


# -------------------- READ GRAPH --------------------
def read_adjacency_list(filename):
    """
    Reads weighted adjacency list and ensures bidirectional edges.
    Format:
    0: 1 (12.85m), 2 (10.43m)
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

    # ✅ Ensure bidirectional edges
    for node, nbrs in list(g.items()):
        for nbr, dist in nbrs.items():
            if nbr not in g:
                g[nbr] = {}
            if node not in g[nbr]:
                g[nbr][node] = dist

    return g


# -------------------- HEURISTIC FUNCTION --------------------
def heuristic(a, b):
    """Dummy heuristic — acts like Dijkstra."""
    return 0


# -------------------- A* SEARCH FUNCTION --------------------
def a_star(start, goal):
    """
    A* Search Algorithm using global graph.
    Returns path as a list of dicts: [{'node': n, 'coords': [lat, lon, alt]}, ...]
    """
    coords = read_coordinates(COORDS_FILE)
    graph = read_adjacency_list(GRAPH_FILE)
    # print(f"Graph = {graph}")
    # print(f"Coords = {coords}")
    # print(f"Start = {start}")
    # print(f"End = {goal}")
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
            path_nodes = []
            while current in came_from:
                path_nodes.append(current)
                current = came_from[current]
            path_nodes.append(start)
            path_nodes.reverse()

            # ✅ Build path with lists instead of tuples
            path = [
                {"node": n, "coords": coords.get(n, [None, None, None])}
                for n in path_nodes
            ]
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
    # Load global data
    coords = read_coordinates(COORDS_FILE)
    graph = read_adjacency_list(GRAPH_FILE)

    print(f"✅ Graph loaded from '{GRAPH_FILE}' with {len(graph)} nodes.")
    print(f"✅ Coordinates loaded from '{COORDS_FILE}'.")
    print("Available nodes:", sorted(graph.keys()))

    try:
        start = int(input("Enter source node: "))
        goal = int(input("Enter destination node: "))

        if start not in graph or goal not in graph:
            print("❌ Invalid node numbers.")
        else:
            path, cost = a_star(start, goal)
            print(f"Path = {path}")
            if path:
                print("\n✅ Shortest Path:")
                for step in path:
                    node, coords_list = step["node"], step["coords"]
                    print(f"  Node {node}: {coords_list}")
                print(f"\n📏 Total Distance: {round(cost, 2)} meters")
            else:
                print("⚠️ No path found between the given nodes.")
    except ValueError:
        print("❌ Please enter valid integer node IDs.")
