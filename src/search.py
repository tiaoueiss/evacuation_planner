from collections import deque
import heapq
import time
import itertools


class SearchResult:
    def __init__(self, algorithm, path, total_cost, expanded_order,
                 frontier_history, runtime_ms, found, goal_id=None):
        self.algorithm = algorithm
        self.path = path
        self.total_cost = total_cost
        self.expanded_order = expanded_order
        self.frontier_history = frontier_history
        self.runtime_ms = runtime_ms
        self.found = found
        self.goal_id = goal_id

    def summary(self):
        return {
            "algorithm": self.algorithm,
            "found": self.found,
            "goal": self.goal_id,
            "path_length": len(self.path) if self.path else 0,
            "total_cost": round(self.total_cost, 2) if self.total_cost else None,
            "nodes_expanded": len(self.expanded_order),
            "runtime_ms": round(self.runtime_ms, 3),
        }


def _reconstruct(came_from, goal):
    path = [goal]
    while came_from.get(path[-1]) is not None:
        path.append(came_from[path[-1]])
    path.reverse()
    return path


def _path_cost(city, path, weights):
    total = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        for nb, edge in city.adjacency[u]:
            if nb == v and not edge.blocked:
                total += city.edge_cost(edge, weights)
                break
    return total


def bfs(city, start, weights=None):
    t0 = time.perf_counter()
    weights = weights or {"distance": 1.0}

    frontier = deque([start])
    came_from = {start: None}
    visited = {start}
    expanded_order = []
    frontier_history = []
    found_goal = None
    exits = set(city.exits())

    while frontier:
        frontier_history.append(list(frontier))
        node = frontier.popleft()
        expanded_order.append(node)

        if node in exits:
            found_goal = node
            break

        for nb, _edge in city.neighbors(node):
            if nb not in visited:
                visited.add(nb)
                came_from[nb] = node
                frontier.append(nb)

    runtime = (time.perf_counter() - t0) * 1000
    if found_goal is None:
        return SearchResult("BFS", [], 0, expanded_order, frontier_history, runtime, False)

    path = _reconstruct(came_from, found_goal)
    total = _path_cost(city, path, weights)
    return SearchResult("BFS", path, total, expanded_order, frontier_history,
                        runtime, True, found_goal)


def ucs(city, start, weights):
    t0 = time.perf_counter()
    counter = itertools.count()

    frontier = [(0.0, next(counter), start)]
    came_from = {start: None}
    g_cost = {start: 0.0}
    expanded_order = []
    frontier_history = []
    found_goal = None
    exits = set(city.exits())

    while frontier:
        frontier_history.append([n for (_, _, n) in frontier])
        cost, _, node = heapq.heappop(frontier)

        if cost > g_cost.get(node, float("inf")):
            continue

        expanded_order.append(node)

        if node in exits:
            found_goal = node
            break

        for nb, edge in city.neighbors(node):
            new_cost = cost + city.edge_cost(edge, weights)
            if new_cost < g_cost.get(nb, float("inf")):
                g_cost[nb] = new_cost
                came_from[nb] = node
                heapq.heappush(frontier, (new_cost, next(counter), nb))

    runtime = (time.perf_counter() - t0) * 1000
    if found_goal is None:
        return SearchResult("UCS", [], 0, expanded_order, frontier_history, runtime, False)

    path = _reconstruct(came_from, found_goal)
    return SearchResult("UCS", path, g_cost[found_goal], expanded_order,
                        frontier_history, runtime, True, found_goal)


def greedy(city, start, weights):
    t0 = time.perf_counter()
    counter = itertools.count()
    exits = city.exits()

    def h(n):
        return min(city.heuristic(n, e) for e in exits) if exits else 0

    frontier = [(h(start), next(counter), start)]
    came_from = {start: None}
    visited = {start}
    expanded_order = []
    frontier_history = []
    found_goal = None
    exit_set = set(exits)

    while frontier:
        frontier_history.append([n for (_, _, n) in frontier])
        _, _, node = heapq.heappop(frontier)
        expanded_order.append(node)

        if node in exit_set:
            found_goal = node
            break

        for nb, _edge in city.neighbors(node):
            if nb not in visited:
                visited.add(nb)
                came_from[nb] = node
                heapq.heappush(frontier, (h(nb), next(counter), nb))

    runtime = (time.perf_counter() - t0) * 1000
    if found_goal is None:
        return SearchResult("Greedy", [], 0, expanded_order, frontier_history, runtime, False)

    path = _reconstruct(came_from, found_goal)
    total = _path_cost(city, path, weights)
    return SearchResult("Greedy", path, total, expanded_order,
                        frontier_history, runtime, True, found_goal)


def astar(city, start, weights):
    t0 = time.perf_counter()
    counter = itertools.count()
    exits = city.exits()

    def h(n):
        if not exits:
            return 0
        d_w = weights.get("distance", 1.0)
        return d_w * min(city.heuristic(n, e) for e in exits)

    frontier = [(h(start), next(counter), start)]
    came_from = {start: None}
    g_cost = {start: 0.0}
    expanded_order = []
    frontier_history = []
    found_goal = None
    exit_set = set(exits)

    while frontier:
        frontier_history.append([n for (_, _, n) in frontier])
        f, _, node = heapq.heappop(frontier)

        if node in exit_set:
            expanded_order.append(node)
            found_goal = node
            break

        if f > g_cost[node] + h(node) + 1e-9:
            continue

        expanded_order.append(node)

        for nb, edge in city.neighbors(node):
            tentative_g = g_cost[node] + city.edge_cost(edge, weights)
            if tentative_g < g_cost.get(nb, float("inf")):
                g_cost[nb] = tentative_g
                came_from[nb] = node
                heapq.heappush(frontier, (tentative_g + h(nb), next(counter), nb))

    runtime = (time.perf_counter() - t0) * 1000
    if found_goal is None:
        return SearchResult("A*", [], 0, expanded_order, frontier_history, runtime, False)

    path = _reconstruct(came_from, found_goal)
    return SearchResult("A*", path, g_cost[found_goal], expanded_order,
                        frontier_history, runtime, True, found_goal)


ALGORITHMS = {"BFS": bfs, "UCS": ucs, "Greedy": greedy, "A*": astar}


def run(algorithm_name, city, start, weights):
    if algorithm_name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm_name}")
    return ALGORITHMS[algorithm_name](city, start, weights)
