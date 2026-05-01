# Building H Alien Evacuation Planner — Project Report

**Course:** CSC474 — Artificial Intelligence
**University:** Holy Spirit University of Kaslik (USEK)
**Semester:** Spring 2026
**Team:** [your name], [partner name]

---

## 1. Problem formulation

USEK's Building H has been compromised. An unidentified hostile presence has
emerged in the underground levels (UB1, UB2) and is spreading through the
stairwells and elevator shafts. Static "follow the green sign" evacuation
arrows do not adapt to which corridors are now infested or which areas are
emitting bio-radiation. Our planner solves the dynamic problem: given the
current state of the building, find the safest route from any room in the
five-floor structure to one of the two ground-level exits.

We model the building as a weighted undirected graph $G = (N, E)$:

- **State space:** the set of rooms $N$ across five floors (F3, F2, F1, UB1,
  UB2). A state is the current location of the person being evacuated.
- **Initial state:** the user-chosen start node $s_0$.
- **Actions:** at any node $n$, the available actions are "move along an
  unblocked edge to an adjacent node $n'$". Edges include corridors (within a
  floor), stairs, and elevators (between floors).
- **Transition model:** $T(n, \text{move to } n') = n'$, defined only when the
  edge $(n, n')$ exists and is not blocked.
- **Goal test:** $n \in \text{Exits}$, where $\text{Exits} = \{\text{EXIT NORTH},
  \text{EXIT SOUTH}\}$ (both on F1).
- **Path cost:** for an edge $e = (u, v)$ we define
  $$
  c(e) = w_d \cdot \text{dist}(e) + w_i \cdot \overline{\text{inf}}(e) \cdot \text{dist}(e)
                                  + w_r \cdot \overline{\text{rad}}(e) \cdot \text{dist}(e)
  $$
  where $\overline{\text{inf}}$ and $\overline{\text{rad}}$ are the averages of
  the two endpoints' infestation and radiation values, and $w_d, w_i, w_r$ are
  user-controlled weights.

The planner must return an action sequence (path) from $s_0$ to any exit that
minimizes the total cost. The user can manipulate the environment in real time
- toggling infestation on individual rooms or barricading edges - so the
planner has to be re-runnable on the fly.

## 2. AI technique and justification

We implement four classical search algorithms from the course (BFS, UCS,
Greedy Best-First, A\*) and use **A\*** as the deployed solver.

A\* is appropriate here for four reasons:

1. The problem is naturally a **graph search with a real-valued cost
   function**, so uninformed BFS is inadequate (it would minimize the number
   of doorways crossed, not safety).
2. We have a natural **admissible heuristic**: the straight-line (Euclidean)
   distance from a room to the nearest exit, scaled by the distance weight
   $w_d$, is always less than or equal to the actual cost-to-go. The
   infestation and radiation contributions are non-negative, so adding them
   only increases the true cost - the heuristic remains a lower bound. With
   an admissible $h$, A\* is **complete and optimal**.
3. Compared to UCS, which produces the same optimal path, A\* directs the
   search toward the goal and prunes irrelevant subtrees - an advantage that
   grows on larger maps and is the practical reason we picked it.
4. We deliberately do **not** use simple supervised machine learning: the
   project description excludes it, and the cost function is well-defined
   and inspectable. A search-based solution is also more transparent during
   the demo - the GUI can show the order of node expansion and the user can
   reason about why a particular path was chosen.

Greedy Best-First is implemented for comparison: it shows how ignoring
accumulated cost can route someone through the hive simply because the hive
happens to be geometrically close to an exit.

## 3. System architecture

```
+------------------+         +-----------------+         +------------------+
|  pygame GUI      |  uses   |  search module  |  reads  |  city_map module |
|  (gui.py)        | ------> |  (search.py)    | ------> |  (city_map.py)   |
|                  |         |                 |         |                  |
| - draw 5 floors  |         | - bfs           |         | - Node / Edge    |
| - terminal HUD   |         | - ucs           |         | - CityMap graph  |
| - particle FX    |         | - greedy        |         | - cost function  |
| - input handling |         | - astar         |         | - Building H scn.|
| - animation      |         | - SearchResult  |         |                  |
+------------------+         +-----------------+         +------------------+
        |
        v
+------------------+
|  audio module    |
|  (audio.py)      |
|                  |
| - synthesizes 8  |
|   creepy sounds  |
|   at startup     |
| - ambient loop   |
+------------------+
```

The four modules are deliberately decoupled:

- `city_map.py` knows nothing about searching or rendering - it just stores
  the graph and computes the cost of an edge given a weight dictionary.
- `search.py` is pure - it takes a `CityMap`, a start node, and weights, and
  returns a `SearchResult` object containing the path, the total cost, the
  ordered list of expanded nodes, and timing information. No pygame imports
  anywhere.
- `audio.py` synthesizes all sounds procedurally with numpy at startup - no
  audio files ship with the project. The module degrades gracefully to a
  no-op if the SDL audio driver fails to initialize.
- `gui.py` is the only place that depends on pygame. It calls `search.run()`
  and animates the result, calling `audio.play(...)` on each event.

This separation is what made it straightforward to write
`tests/test_search.py` - the algorithm tests run in plain Python without ever
opening a window or initializing audio.

## 4. Complexity analysis

Let $b$ be the average branching factor (degree of a node) and $d$ the depth
at which the nearest goal lies.

| Algorithm | Time                                                    | Space          | Optimal under our cost? |
|-----------|---------------------------------------------------------|----------------|---------|
| BFS       | $O(b^d)$                                                | $O(b^d)$       | No (only optimal for hop count) |
| UCS       | $O(b^{1 + \lfloor C^* / \varepsilon \rfloor})$          | same           | Yes |
| Greedy    | $O(b^m)$ worst case                                     | $O(b^m)$       | No |
| A\*       | $O(b^d)$ worst case, but driven by heuristic accuracy   | $O(b^d)$       | Yes (with admissible $h$) |

With the heuristic $h(n) = w_d \cdot \min_{e \in \text{Exits}} \|n - e\|_2$
the heuristic is admissible because the actual cost to reach an exit is at
least $w_d \cdot \text{euclidean distance}$ (the infestation and radiation
contributions are $\geq 0$).

For our specific scenario - 19 rooms, 27 edges, two exits - the absolute
numbers are small. What matters for the demo is the qualitative comparison:
informed search (A\*) reaches the goal with fewer expansions than uninformed
search (UCS) on average, while still guaranteeing the optimal path.

## 5. Experimental observations

We measured all four algorithms on three representative starting positions
with weights $(w_d, w_i, w_r) = (1, 10, 30)$:

**Start = F3 Chapel (clean upper floor)**

| Algorithm | Hops | Cost   | Expanded | Time (ms) | Path           |
|-----------|------|--------|----------|-----------|----------------|
| BFS       | 3    | 695    | 5        | < 1       | F3->F2->F1->EXIT NORTH |
| UCS       | 3    | 695    | 4        | < 1       | same           |
| Greedy    | 3    | 695    | 4        | < 1       | same           |
| A\*       | 3    | 695    | 5        | < 1       | same           |

When the start is already close to an exit and there's no danger in the way,
all algorithms agree.

**Start = UB2 Server Room (deep underground)**

| Algorithm | Hops | Cost   | Expanded | Path                                 |
|-----------|------|--------|----------|--------------------------------------|
| BFS       | 3    | 5119   | 9        | UB2->UB1->F1->EXIT NORTH (west stairs) |
| UCS       | 3    | 5119   | 4        | same                                 |
| Greedy    | 3    | 5119   | 4        | same                                 |
| A\*       | 3    | 5119   | 4        | same                                 |

Same path here too - on this small map, the west-stairwell route is
unambiguously the safest from UB2.

**Where the algorithms diverge:** when we manually toggle one of the upper
rooms to high infestation (e.g. right-click F1 Reception), BFS and Greedy
still pick the short path through it, while UCS and A\* re-route through the
auditorium and EXIT SOUTH. This is the qualitative result we demonstrate at
the demo - the cost-aware algorithms trade hops for safety, whereas the
uninformed/greedy ones do not.

## 6. Limitations and future work

- **Static during a search.** Infestation and radiation values are read once
  when a search starts. A real "spreading invasion" would update them over
  time. The architecture supports re-invocation (just call `search.run` again
  with the updated map), and we let the user simulate spread manually by
  toggling rooms, but we don't have a built-in spread model.
- **Single agent.** We plan for one person at a time. With many students
  evacuating, the optimal route for each individual depends on what others
  are doing - this would require a multi-agent or flow-based formulation.
- **Hand-built map.** Building H is modeled with 19 rooms - a very rough
  approximation. A real deployment would import a floor plan from a BIM/IFC
  file.
- **Stairs and elevators are treated identically.** In a real emergency you
  cannot use the elevator at all, and stairs have an extra time cost. We
  could easily encode this with per-edge cost multipliers.
- **No vertical visibility constraint.** We assume the planner has perfect
  information about every room, which is not realistic - in a real evacuation
  the user only knows what they can see.
- **Heuristic could be smarter.** Our heuristic uses Euclidean distance.
  A heuristic that also penalizes proximity to known infested zones could
  prune the search more aggressively while staying admissible.

## 7. Conclusion

The project formulates dynamic evacuation as a weighted graph search problem
with a multi-objective cost function (distance + infestation + radiation),
and applies four classical search algorithms from the CSC474 syllabus to
solve it. We picked A\* as the deployed planner because it is provably
optimal under our admissible heuristic and produces fewer expansions than
UCS on average. The pygame interface lets the user manipulate the
environment in real time, watch the algorithm explore the building floor
by floor, and see the resulting evacuation path - with procedurally
generated audio that gives the search a creepy alien-invasion atmosphere
appropriate to the scenario.
