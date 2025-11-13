import math

# -------------------- HAVERSINE FUNCTION --------------------
def haversine_distance(coord1, coord2):
    """Calculate great-circle distance (in meters) between two coordinates."""
    R = 6371000  # Earth radius in meters

    lat1, lon1, _ = coord1
    lat2, lon2, _ = coord2

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# -------------------- READ INPUT FILES --------------------
def read_coordinates(filename="logged_coordinates.txt"):
    """Read coordinates from a file and return a dict mapping node->(lat, lon, alt).

    This parser is defensive and accepts either space-separated values like
    "0 17.3970873 78.4897846 500.5" or comma-separated values like
    "0 17.3973265, 78.4900595, 494.18". Malformed lines are skipped with a
    warning.
    """
    coords = {}
    with open(filename, 'r') as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue

            # Normalize separators: replace commas with spaces then split on whitespace
            parts = line.strip().replace(',', ' ').split()

            if len(parts) < 4:
                print(f"⚠️ Skipping malformed line {lineno} in {filename}: '{line.strip()}'")
                continue

            try:
                node = int(parts[0])
            except ValueError:
                print(f"⚠️ Invalid node id on line {lineno}: '{parts[0]}'. Skipping.")
                continue

            try:
                lat, lon, alt = map(float, parts[1:4])
            except ValueError:
                # Last-ditch attempt: strip any lingering punctuation and retry
                try:
                    cleaned = [p.strip().strip(',') for p in parts[1:4]]
                    lat, lon, alt = map(float, cleaned)
                except ValueError:
                    print(f"⚠️ Could not parse coordinates on line {lineno}: '{line.strip()}'. Skipping.")
                    continue

            coords[node] = (lat, lon, alt)
    return coords


def read_connections(filename="logged_coordinates.txt"):
    """Read adjacency list from list.txt and return a dict."""
    connections = {}
    with open(filename, 'r') as f:
        for line in f:
            if ':' not in line:
                continue
            node, neighbors = line.strip().split(':')
            node = int(node.strip())
            neighbors = [int(n.strip()) for n in neighbors.split(',') if n.strip()]
            connections[node] = neighbors
    return connections


# -------------------- BUILD GRAPH STRUCTURES --------------------
def create_adjacency_list(coords, connections):
    """Return weighted adjacency list using Haversine distance."""
    adj_list = {}
    for node, neighbors in connections.items():
        adj_list[node] = {}
        for neighbor in neighbors:
            if neighbor not in coords:
                print(f"⚠️ Warning: Neighbor {neighbor} not found in coordinates. Skipping.")
                continue
            dist = haversine_distance(coords[node], coords[neighbor])
            adj_list[node][neighbor] = round(dist, 2)
    return adj_list



# -------------------- SAVE OUTPUT FILES --------------------
def save_adjacency_list(filename, adj_list):
    with open(filename, 'w') as f:
        for node, neighbors in adj_list.items():
            line = f"{node}: " + ", ".join(f"{nbr} ({dist}m)" for nbr, dist in neighbors.items())
            f.write(line + "\n")


def save_adjacency_matrix(filename, matrix):
    with open(filename, 'w') as f:
        for row in matrix:
            f.write(" ".join(f"{val:.2f}" for val in row) + "\n")


# -------------------- MAIN --------------------
if __name__ == "__main__":
    coords = read_coordinates()
    # Try to read an explicit connections file. If it's missing, fall back
    # to a simple sequential chain graph based on the coordinate node ids.
    try:
        connections = read_connections("list.txt")
    except FileNotFoundError:
        print("⚠️ 'list.txt' not found. Falling back to sequential connections based on coordinates.")
        # Build a simple adjacency where each node connects to the next and previous node
        node_ids = sorted(coords.keys())
        connections = {}
        for i, node in enumerate(node_ids):
            neighbors = []
            if i > 0:
                neighbors.append(node_ids[i-1])
            if i < len(node_ids) - 1:
                neighbors.append(node_ids[i+1])
            connections[node] = neighbors

    adj_list = create_adjacency_list(coords, connections)

    save_adjacency_list("weighted_adj_list.txt", adj_list)

    print("✅ Weighted adjacency list saved to 'weighted_adj_list.txt'")

