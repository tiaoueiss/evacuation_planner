# Building H — Alien Evacuation Planner

**Course:** CSC474 — Artificial Intelligence  
**University:** Holy Spirit University of Kaslik (USEK)  
**Semester:** Spring 2026

---

## 1. Problem Formulation

USEK's Building H has five floors (F3, F2, F1, UB1, UB2). An alien presence has emerged in the underground levels and is spreading upward. Static evacuation signs are useless because they cannot adapt to blocked corridors, infested rooms, or radiation leaking from the hive. The goal of this planner is to compute, on demand, the safest route from any room to one of two ground-floor exits given the current state of the building.

We model the problem as a **weighted graph search**:

- **State space:** the set of rooms $N$ across the five floors. A state is the current location of the person being evacuated.
- **Initial state:** the user-selected start room $s_0$.
- **Actions:** move along any unblocked edge (corridor, stairwell, or elevator) to an adjacent room.
- **Transition model:** $T(n,\ \text{move to}\ n') = n'$, defined only when the edge $(n, n')$ is not blocked.
- **Goal test:** $n \in \{\text{EXIT NORTH},\ \text{EXIT SOUTH}\}$ (both on F1).
- **Path cost:** for an edge $e = (u, v)$ with Euclidean length $\text{dist}(e)$:

$$c(e)\ =\ w_d \cdot \text{dist}(e)\ +\ w_i \cdot \overline{\text{inf}}(e) \cdot \text{dist}(e)\ +\ w_r \cdot \overline{\text{rad}}(e) \cdot \text{dist}(e)$$

where $\overline{\text{inf}}$ and $\overline{\text{rad}}$ are the averages of the two endpoint values, and $w_d,\ w_i,\ w_r$ are user-controlled weights. Setting $w_i$ and $w_r$ to zero reduces the planner to pure shortest-path; raising them makes the AI trade extra distance for safety.

---

## 2. AI Technique Justification

We implement four classical search algorithms and deploy **A\*** as the primary solver.

**Why not BFS?** BFS minimises the number of doorways crossed, not the weighted cost. It will cheerfully route someone through a radiation-saturated corridor if it happens to be one hop shorter.

**Why not Greedy Best-First?** Greedy uses only the straight-line distance to the nearest exit as its priority. It can recommend walking through the alien hive simply because the hive is geometrically close to an exit — it never accounts for accumulated danger.

**Why not UCS alone?** Uniform Cost Search is optimal but blind to direction. It expands nodes in concentric cost rings around the start, wasting time exploring rooms that are clearly far from any exit.

**A\* combines the strengths of both:** $f(n) = g(n) + h(n)$, where $g(n)$ is the true accumulated cost and $h(n) = w_d \cdot \min_{e \in \text{Exits}} \|n - e\|_2$ is a weighted Euclidean heuristic. This heuristic is **admissible** because the actual cost-to-go is at least $w_d \cdot \text{(Euclidean distance to exit)}$ — infestation and radiation contributions are non-negative, so they can only increase the true cost. With an admissible heuristic, A\* is **complete** (always finds a solution if one exists) and **optimal** (finds the minimum-cost path). Compared to UCS it also expands fewer nodes because $h$ steers the search toward the exits.

The visual interface exposes all four algorithms side by side so students can see concretely why informed search outperforms uninformed search on this cost function.

---

## 3. System Architecture

The project is split into four deliberately decoupled modules:

```
main.py
  └── gui.py          ← only module that uses pygame
        ├── city_map.py   ← graph: nodes, edges, cost function
        ├── search.py     ← BFS / UCS / Greedy / A*  (pure Python, no GUI)
        └── audio.py      ← procedural sound synthesis via numpy
```

**`city_map.py`** stores the building as a weighted undirected graph (`CityMap`, `Node`, `Edge`). The cost function is computed here so the algorithms only call `city.edge_cost(edge, weights)` and `city.heuristic(u, v)`. No search or rendering logic lives in this module.

**`search.py`** contains the four algorithms. Each returns a `SearchResult` holding the path, total cost, expansion order, and timing — everything the GUI needs to animate the result. The module has no pygame import and is tested independently.

**`audio.py`** synthesises eight sounds (ambient drone, node-expansion blips, success chime, failure growl, alarm, block thud) at startup using numpy. Underground floors get lower-pitched blips; upper floors get higher-pitched ones, giving the user auditory feedback about where the search is exploring. The module degrades gracefully to a no-op if the SDL audio driver is unavailable.

**`gui.py`** is the only pygame-dependent module. It manages the game loop, renders the five-floor cross-section, handles all user input, and animates expansions and paths. The right panel exposes algorithm selection, weight sliders, a label-overlay toggle (edge costs and heuristic values), and a comparison mode that benchmarks all four algorithms on the same map.

---

## 4. Complexity Analysis

Let $b$ be the average branching factor and $d$ the depth of the nearest exit. Let $C^*$ be the optimal path cost and $\varepsilon$ the minimum edge cost.

| Algorithm | Time complexity | Space | Optimal? |
|-----------|-----------------|-------|----------|
| BFS | $O(b^d)$ | $O(b^d)$ | No — hop count only |
| UCS | $O\!\left(b^{1+\lfloor C^*/\varepsilon \rfloor}\right)$ | same | Yes |
| Greedy | $O(b^m)$ worst case | $O(b^m)$ | No |
| A\* | $O(b^d)$ worst case | $O(b^d)$ | Yes (admissible $h$) |

In practice the building has 19 rooms and 27 edges, so the absolute counts are small. What matters for the demo is the **qualitative difference**: on a clean map all four algorithms find the same 3-hop west-stairwell path. Once a room is toggled to high infestation, BFS and Greedy still route through it while UCS and A\* detour around it — illustrating that cost-aware search is not just faster but qualitatively different.

A\* expands 4 nodes from UB2 Server Room versus 9 for BFS on the default map — a 55 % reduction in expansions even on a graph this small, and the gap would widen on a larger floor plan.

---

## 5. Limitations & Improvements

**Static state during search.** Infestation and radiation values are read once when a search starts. A spreading invasion would require either replanning on every alien move (expensive) or an anytime algorithm that refines a partial solution as the map changes. The architecture already supports re-invocation, so periodic replanning is a straightforward extension.

**Single agent.** The planner computes the optimal route for one person at a time. If multiple students are evacuating simultaneously, the individually optimal route for each person depends on corridor congestion caused by others — this would require a multi-agent formulation or a flow-based model.

**Hand-built map.** Building H is approximated with 19 rooms. Real deployment would require importing a floor plan from a BIM/IFC file and automatically generating nodes and edges from room polygons and door positions.

**Stairs and elevators treated identically.** In a real emergency elevators are disabled. Per-edge type multipliers could encode this (e.g. multiply elevator edge costs by a large constant after an alarm is triggered).

**Heuristic could be stronger.** The current heuristic is pure Euclidean distance scaled by $w_d$. A pattern database or landmark-based heuristic that also estimates infestation exposure could remain admissible while pruning the search more aggressively on larger maps.

**Single exit bias.** Because the heuristic points to the geometrically nearest exit, both exits can receive paths but one tends to dominate. Randomising tiebreaking or running A\* twice (once per exit) and taking the cheaper result would produce more varied and realistic routing.