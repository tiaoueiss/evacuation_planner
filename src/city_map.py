"""
city_map.py
-----------
Models USEK Building H during the alien invasion.

Building H has 5 floors:
    F3   - top floor (classrooms, chapel access)
    F2   - middle floor
    F1   - ground floor (main entrance, two exits)
    UB1  - underground level 1 (parking, labs)
    UB2  - underground level 2 (server rooms, deep storage) <- alien hive

Each room (node) has:
    - (x, y) screen coordinates and a `floor` attribute
    - `infestation` value [0..1]   -> how many aliens are in the area
    - `radiation` value   [0..1]   -> alien bio-radiation / hazard
    - is_exit flag                  -> safe ground-floor exits
    - label (e.g. "F2 Lab" or "UB2 Server Room")

Edges:
    - corridors connect rooms on the same floor
    - stairs / elevators connect adjacent floors
    - any edge can be `blocked` (a barricade, collapse, or sealed door)

The cost function combines three real-world factors (we do NOT use simple
distance-only routing - that would be just A* on a grid):
    cost(edge) = w_d * dist + w_i * avg_infestation * dist
                            + w_r * avg_radiation   * dist
"""

import math
import json


# floor heights for drawing (y offset per floor, plus per-floor labels)
FLOOR_Y = {
    "F3":   65,
    "F2":  185,
    "F1":  305,
    "UB1": 470,
    "UB2": 590,
}

FLOOR_ORDER = ["F3", "F2", "F1", "UB1", "UB2"]


class Node:
    def __init__(self, node_id, x, y, floor,
                 infestation=0.0, radiation=0.0, is_exit=False, label=None):
        self.id = node_id
        self.x = x
        self.y = y
        self.floor = floor
        self.infestation = infestation
        self.radiation = radiation
        self.is_exit = is_exit
        self.label = label if label else str(node_id)

    def __repr__(self):
        return f"Node({self.id}, {self.floor}, exit={self.is_exit})"


class Edge:
    def __init__(self, u, v, distance, blocked=False, kind="corridor"):
        self.u = u
        self.v = v
        self.distance = distance
        self.blocked = blocked
        self.kind = kind  # "corridor" | "stairs" | "elevator"


class CityMap:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adjacency = {}

    # ---------- building ----------

    def add_node(self, node_id, x, y, floor,
                 infestation=0.0, radiation=0.0, is_exit=False, label=None):
        node = Node(node_id, x, y, floor, infestation, radiation, is_exit, label)
        self.nodes[node_id] = node
        self.adjacency[node_id] = []
        return node

    def add_edge(self, u, v, distance=None, blocked=False, kind="corridor"):
        if u not in self.nodes or v not in self.nodes:
            raise ValueError(f"node {u} or {v} doesn't exist")
        if distance is None:
            distance = self._euclid(u, v)
        edge = Edge(u, v, distance, blocked, kind)
        self.edges.append(edge)
        self.adjacency[u].append((v, edge))
        self.adjacency[v].append((u, edge))
        return edge

    def _euclid(self, u, v):
        a = self.nodes[u]
        b = self.nodes[v]
        return math.hypot(a.x - b.x, a.y - b.y)

    # ---------- runtime modifications ----------

    def set_blocked(self, u, v, blocked=True):
        for e in self.edges:
            if (e.u == u and e.v == v) or (e.u == v and e.v == u):
                e.blocked = blocked
                return True
        return False

    def toggle_blocked(self, u, v):
        for e in self.edges:
            if (e.u == u and e.v == v) or (e.u == v and e.v == u):
                e.blocked = not e.blocked
                return e.blocked
        return None

    def set_infestation(self, node_id, value):
        if node_id in self.nodes:
            self.nodes[node_id].infestation = max(0.0, min(1.0, value))

    def set_radiation(self, node_id, value):
        if node_id in self.nodes:
            self.nodes[node_id].radiation = max(0.0, min(1.0, value))

    # ---------- search queries ----------

    def neighbors(self, node_id):
        for nb, edge in self.adjacency[node_id]:
            if not edge.blocked:
                yield nb, edge

    def exits(self):
        return [n.id for n in self.nodes.values() if n.is_exit]

    def heuristic(self, node_id, goal_id):
        """Straight-line distance, admissible for A*."""
        return self._euclid(node_id, goal_id)

    def edge_cost(self, edge, weights):
        u = self.nodes[edge.u]
        v = self.nodes[edge.v]
        avg_inf = (u.infestation + v.infestation) / 2.0
        avg_rad = (u.radiation   + v.radiation)   / 2.0
        return (
            weights.get("distance", 1.0)    * edge.distance
            + weights.get("infestation", 0.0) * avg_inf * edge.distance
            + weights.get("radiation", 0.0)   * avg_rad * edge.distance
        )

    # ---------- save / load ----------

    def to_dict(self):
        return {
            "nodes": [
                {"id": n.id, "x": n.x, "y": n.y, "floor": n.floor,
                 "infestation": n.infestation, "radiation": n.radiation,
                 "is_exit": n.is_exit, "label": n.label}
                for n in self.nodes.values()
            ],
            "edges": [
                {"u": e.u, "v": e.v, "distance": e.distance,
                 "blocked": e.blocked, "kind": e.kind}
                for e in self.edges
            ]
        }

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        m = cls()
        for n in data["nodes"]:
            m.add_node(n["id"], n["x"], n["y"], n["floor"],
                       n["infestation"], n["radiation"],
                       n["is_exit"], n.get("label"))
        for e in data["edges"]:
            m.add_edge(e["u"], e["v"], e["distance"],
                       e.get("blocked", False), e.get("kind", "corridor"))
        return m


# =====================================================================
# THE SCENARIO: Building H during the invasion
# =====================================================================
# x positions: rooms are arranged in 4 columns roughly 160 px apart.
# infestation is HIGH on the underground floors (UB1 ~0.4-0.7, UB2 ~0.8-1.0)
# and LOW on F2/F3. Aliens are climbing up the central stairs.
#
# Two exits: EXIT_NORTH (parking-side door) and EXIT_SOUTH (street door),
# both on F1 (ground floor).
# =====================================================================

def build_building_h():
    m = CityMap()

    # ---------- F3 (top floor - relatively safe) ----------
    m.add_node(30, 200, FLOOR_Y["F3"], "F3", infestation=0.0, label="F3 Chapel")
    m.add_node(31, 380, FLOOR_Y["F3"], "F3", infestation=0.05, label="F3 Lecture Hall")
    m.add_node(32, 560, FLOOR_Y["F3"], "F3", infestation=0.1, label="F3 Faculty Office")
    m.add_node(33, 740, FLOOR_Y["F3"], "F3", infestation=0.0, label="F3 Library")

    # ---------- F2 (middle - some leakage) ----------
    m.add_node(20, 200, FLOOR_Y["F2"], "F2", infestation=0.1, label="F2 Lab 201")
    m.add_node(21, 380, FLOOR_Y["F2"], "F2", infestation=0.25, radiation=0.1, label="F2 Hallway")
    m.add_node(22, 560, FLOOR_Y["F2"], "F2", infestation=0.15, label="F2 Lab 205")
    m.add_node(23, 740, FLOOR_Y["F2"], "F2", infestation=0.05, label="F2 Lounge")

    # ---------- F1 (ground - the goal floor) ----------
    m.add_node(10, 200, FLOOR_Y["F1"], "F1", infestation=0.15, label="F1 Reception")
    m.add_node(11, 380, FLOOR_Y["F1"], "F1", infestation=0.4, radiation=0.2, label="F1 Atrium")
    m.add_node(12, 560, FLOOR_Y["F1"], "F1", infestation=0.3, label="F1 Cafeteria")
    m.add_node(13, 740, FLOOR_Y["F1"], "F1", infestation=0.2, label="F1 Auditorium")

    # the two exits, slightly outside the building
    m.add_node(99, 60,  FLOOR_Y["F1"], "F1", is_exit=True, label="EXIT NORTH")
    m.add_node(98, 880, FLOOR_Y["F1"], "F1", is_exit=True, label="EXIT SOUTH")

    # ---------- UB1 (parking + labs - heavily infested) ----------
    m.add_node(40, 200, FLOOR_Y["UB1"], "UB1", infestation=0.55, radiation=0.3, label="UB1 Parking A")
    m.add_node(41, 380, FLOOR_Y["UB1"], "UB1", infestation=0.7,  radiation=0.5, label="UB1 Bio Lab")
    m.add_node(42, 560, FLOOR_Y["UB1"], "UB1", infestation=0.6,  radiation=0.4, label="UB1 Storage")
    m.add_node(43, 740, FLOOR_Y["UB1"], "UB1", infestation=0.5,  radiation=0.3, label="UB1 Parking B")

    # ---------- UB2 (the hive itself) ----------
    m.add_node(50, 280, FLOOR_Y["UB2"], "UB2", infestation=0.95, radiation=0.7, label="UB2 Server Room")
    m.add_node(51, 460, FLOOR_Y["UB2"], "UB2", infestation=1.0,  radiation=0.9, label="UB2 HIVE")
    m.add_node(52, 640, FLOOR_Y["UB2"], "UB2", infestation=0.9,  radiation=0.8, label="UB2 Deep Storage")

    # ---------- horizontal corridors ----------
    # F3
    m.add_edge(30, 31); m.add_edge(31, 32); m.add_edge(32, 33)
    # F2
    m.add_edge(20, 21); m.add_edge(21, 22); m.add_edge(22, 23)
    # F1 (with exits on both ends)
    m.add_edge(99, 10); m.add_edge(10, 11); m.add_edge(11, 12); m.add_edge(12, 13); m.add_edge(13, 98)
    # UB1
    m.add_edge(40, 41); m.add_edge(41, 42); m.add_edge(42, 43)
    # UB2
    m.add_edge(50, 51); m.add_edge(51, 52)

    # ---------- vertical stairs (kind="stairs") ----------
    # west stairwell connects 30-20-10-40-50
    m.add_edge(30, 20, kind="stairs")
    m.add_edge(20, 10, kind="stairs")
    m.add_edge(10, 40, kind="stairs")
    m.add_edge(40, 50, kind="stairs")
    # central elevator 31-21-11-41-51
    m.add_edge(31, 21, kind="elevator")
    m.add_edge(21, 11, kind="elevator")
    m.add_edge(11, 41, kind="elevator")
    m.add_edge(41, 51, kind="elevator")
    # east stairwell 32-22-12-42-52
    m.add_edge(32, 22, kind="stairs")
    m.add_edge(22, 12, kind="stairs")
    m.add_edge(12, 42, kind="stairs")
    m.add_edge(42, 52, kind="stairs")
    # far-east stairs (no underground access)
    m.add_edge(33, 23, kind="stairs")
    m.add_edge(23, 13, kind="stairs")

    # default: alien hive has barricaded the central elevator at UB2-UB1
    # (so the player can't trivially walk up the middle from the hive)
    m.set_blocked(51, 41, True)

    return m
