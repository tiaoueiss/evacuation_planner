# Building H — Alien Evacuation Planner: Full Code Documentation

**Course:** CSC474 — Artificial Intelligence  
**University:** Holy Spirit University of Kaslik (USEK)  
**Semester:** Spring 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Structure](#2-project-structure)
3. [Module: `city_map.py`](#3-module-city_mappy)
4. [Module: `search.py`](#4-module-searchpy)
5. [Module: `audio.py`](#5-module-audiopy)
6. [Module: `gui.py`](#6-module-guipy)
7. [Entry Point: `main.py`](#7-entry-point-mainpy)
8. [Tests: `test_search.py`](#8-tests-test_searchpy)
9. [Data Flow Diagram](#9-data-flow-diagram)
10. [Bug Fixes & Changes Made](#10-bug-fixes--changes-made)
11. [How to Run](#11-how-to-run)

---

## 1. Project Overview

This is a **pygame-based AI evacuation planner** that simulates an alien invasion inside USEK's Building H. The building has 5 floors modeled as a weighted graph. Users can:

- Pick which room they're trapped in
- Toggle alien infestation or barricade corridors
- Choose from 4 search algorithms (BFS, UCS, Greedy, A*)
- Watch the algorithm animate its search step-by-step
- See the final escape route drawn in cyan

The project demonstrates the differences between uninformed and informed search algorithms on a real multi-objective cost function (distance + infestation + radiation).

---

## 2. Project Structure

```
evacuation_planner/
├── main.py                    # entry point — imports gui.main()
├── requirements.txt           # pygame-ce + numpy
├── README.md                  # user-facing instructions
├── src/
│   ├── city_map.py            # Building H graph model (nodes, edges, cost)
│   ├── search.py              # BFS, UCS, Greedy, A* algorithms
│   ├── audio.py               # procedural sound synthesis (no audio files)
│   └── gui.py                 # pygame window, rendering, user input
├── tests/
│   └── test_search.py         # algorithm correctness tests (no pygame needed)
└── docs/
    ├── report.md              # AI justification + problem formulation
    └── code_documentation.md  # this file
```

**Dependency chain** (what imports what):

```
main.py
  └── gui.py
        ├── city_map.py   (graph model)
        ├── search.py     (algorithms)
        └── audio.py      (sounds)
```

`search.py` and `city_map.py` have **no pygame dependency**, so tests run without a display.

---

## 3. Module: `city_map.py`

### Purpose
Defines the graph data model for Building H. Knows nothing about rendering or searching — it is a pure data layer.

### Classes

#### `Node`
Represents one room in the building.

| Attribute     | Type   | Description                                        |
|---------------|--------|----------------------------------------------------|
| `id`          | int    | Unique integer identifier                          |
| `x`, `y`      | float  | Screen pixel coordinates for rendering             |
| `floor`       | str    | Which floor: `"F3"`, `"F2"`, `"F1"`, `"UB1"`, `"UB2"` |
| `infestation` | float  | 0.0 (clean) → 1.0 (hive). Affects edge cost.      |
| `radiation`   | float  | 0.0 → 1.0 bio-hazard level. Affects edge cost.    |
| `is_exit`     | bool   | True for the two ground-floor exit nodes           |
| `label`       | str    | Human-readable name like `"F2 Lab 201"`            |

#### `Edge`
Represents a connection between two rooms.

| Attribute  | Type   | Description                                              |
|------------|--------|----------------------------------------------------------|
| `u`, `v`   | int    | The two endpoint node IDs (undirected)                   |
| `distance` | float  | Pixel distance between the rooms (default = Euclidean)   |
| `blocked`  | bool   | True if barricaded; blocked edges are skipped by search  |
| `kind`     | str    | `"corridor"`, `"stairs"`, or `"elevator"`                |

#### `CityMap`
The main graph container.

| Key method / attribute | Description |
|------------------------|-------------|
| `nodes`                | `dict[int, Node]` — all rooms indexed by ID |
| `edges`                | `list[Edge]` — all connections |
| `adjacency`            | `dict[int, list[(neighbor_id, Edge)]]` — fast neighbor lookup |
| `add_node(...)`        | Creates and registers a node |
| `add_edge(u, v, ...)`  | Creates an undirected edge (adds to `adjacency[u]` and `adjacency[v]`) |
| `neighbors(node_id)`   | Generator yielding `(neighbor_id, edge)` for all **unblocked** edges |
| `exits()`              | Returns `list[int]` of exit node IDs |
| `heuristic(u, v)`      | Euclidean pixel distance between two nodes (used by A* and Greedy) |
| `edge_cost(edge, weights)` | Weighted cost formula (see below) |
| `set_blocked(u, v, b)` | Toggle a barricade on an edge at runtime |
| `save(path)` / `load(path)` | JSON serialization |

### Edge Cost Formula

```
cost(edge) = w_d * dist
           + w_i * avg_infestation * dist
           + w_r * avg_radiation   * dist
```

Where:
- `dist` = the edge's Euclidean pixel distance
- `avg_infestation` = `(u.infestation + v.infestation) / 2`
- `avg_radiation` = `(u.radiation + v.radiation) / 2`
- `w_d`, `w_i`, `w_r` = user-controlled weights passed as a `dict`

This means a corridor through a heavily infested room is penalized proportionally to both the amount of infestation and the length of the corridor.

### Building H Layout (`build_building_h()`)

The factory function creates 19 nodes across 5 floors and 27 edges:

| Floor | Node IDs | Rooms                                        | Threat level |
|-------|----------|----------------------------------------------|--------------|
| F3    | 30–33    | Chapel, Lecture Hall, Faculty Office, Library | Clean        |
| F2    | 20–23    | Lab 201, Hallway, Lab 205, Lounge             | Low          |
| F1    | 10–13, 98, 99 | Reception, Atrium, Cafeteria, Auditorium + 2 exits | Medium |
| UB1   | 40–43    | Parking A, Bio Lab, Storage, Parking B        | Heavy        |
| UB2   | 50–52    | Server Room, HIVE, Deep Storage               | Extreme      |

Vertical connections (between floors):
- **West stairwell**: 30↔20↔10↔40↔50
- **Central elevator**: 31↔21↔11↔41↔51 (41↔51 starts **blocked** by default)
- **East stairwell**: 32↔22↔12↔42↔52
- **Far-east stairs**: 33↔23↔13 (no underground access)

---

## 4. Module: `search.py`

### Purpose
Contains the four search algorithms and a shared result container. **No pygame, no audio** — pure Python. This is what `test_search.py` tests directly.

### `SearchResult`

Returned by every algorithm. Stores everything the GUI needs to animate and display.

| Attribute          | Type       | Description |
|--------------------|------------|-------------|
| `algorithm`        | str        | `"BFS"`, `"UCS"`, `"Greedy"`, or `"A*"` |
| `path`             | list[int]  | Sequence of node IDs from start to goal |
| `total_cost`       | float      | Sum of edge costs along the path |
| `expanded_order`   | list[int]  | Nodes in the order they were popped from the frontier |
| `frontier_history` | list[list] | Snapshot of the frontier before each expansion (for replay) |
| `runtime_ms`       | float      | Wall-clock time in milliseconds |
| `found`            | bool       | Whether a path was found |
| `goal_id`          | int or None | Which exit was reached |

### Helper: `_reconstruct(came_from, goal)`
Traces back the `came_from` dict from goal to start, then reverses to get the path `[start, ..., goal]`.

### Helper: `_path_cost(city, path, weights)`
Recomputes the total weighted cost of a path by walking the adjacency list. Used by BFS and Greedy (which don't track cost during search).

### Algorithm: BFS

```python
def bfs(city, start, weights=None)
```

- **Data structure:** `deque` (FIFO queue)
- **Cost function:** treats all edges as cost 1 (minimizes hops, not safety)
- **Goal test:** when a node is **popped**
- **Optimal?** Only for hop count, not for the weighted cost function
- **When to use it:** as a baseline to show that shortest path ≠ safest path

BFS ignores `weights` during traversal. The `weights` parameter is only used to compute the reported `total_cost` via `_path_cost` after the path is found.

### Algorithm: UCS

```python
def ucs(city, start, weights)
```

- **Data structure:** min-heap sorted by accumulated cost `g(n)`
- **Uses lazy deletion:** if a cheaper path to a node is found later, the stale heap entry is skipped when popped via `if cost > g_cost.get(node, inf): continue`
- **Optimal?** Yes — always finds the minimum cost path
- **Heuristic?** No — blind to direction; explores in concentric cost rings

UCS uses a `counter` from `itertools.count()` as a tiebreaker to keep the heap stable when two entries have the same cost. Without it, Python would try to compare `Node` objects as a tiebreaker, which would raise an error.

### Algorithm: Greedy Best-First

```python
def greedy(city, start, weights)
```

- **Data structure:** min-heap sorted by `h(n) = min(euclidean to each exit)`
- **Heuristic:** pure straight-line distance to nearest exit (no cost accumulated)
- **Optimal?** No — can route through the hive because the hive is geometrically close to an exit
- **Visited set:** uses a simple `visited` set (no re-expansion)

Greedy demonstrates why heuristic alone is not enough: it can pick a path that is short in Euclidean terms but extremely costly in infestation/radiation.

### Algorithm: A*

```python
def astar(city, start, weights)
```

- **Data structure:** min-heap sorted by `f(n) = g(n) + h(n)`
- **Heuristic:** `h(n) = w_d * min(euclidean(n, exit) for each exit)`
  - Scaled by `w_d` (distance weight) to remain admissible
  - Always ≤ true cost since infestation/radiation contributions are ≥ 0
- **Goal test:** when a node is **popped** (ensures optimality)
- **Stale-entry check:** `if f > g_cost[node] + h(node) + 1e-9: continue`
- **Optimal?** Yes — with this admissible heuristic, A* is complete and optimal

**Why A* is chosen as the deployed algorithm:**
1. Same optimal result as UCS but with fewer node expansions (guided by `h`)
2. Heuristic is admissible (euclidean is a lower bound on true cost)
3. The GUI can meaningfully show the heuristic value per node (educational)

### `run(algorithm_name, city, start, weights)`
Dispatcher that looks up the algorithm by name in `ALGORITHMS` dict and calls it. Called by the GUI and by tests.

---

## 5. Module: `audio.py`

### Purpose
Synthesizes all game sounds procedurally at startup using `numpy`. No `.wav` or `.mp3` files are shipped.

### Initialization

```python
audio.init()        # called once at startup; generates all sounds
audio.start_ambient()  # begins the looping drone on a dedicated channel
audio.shutdown()    # called on exit; stops mixer cleanly
```

If `numpy` is not installed or the SDL audio driver fails, all functions become silent no-ops — the rest of the app keeps working.

### Sound Catalog

| Name        | Generator function   | Description |
|-------------|----------------------|-------------|
| `ambient`   | `_gen_ambient_hum`   | Slow pulsing drone with detuned sines; loops continuously |
| `blip`      | `_gen_blip(440)`     | Short descending click; played on node expansion (F1) |
| `blip_lo`   | `_gen_blip(300)`     | Lower blip for underground floors (UB1, UB2) |
| `blip_hi`   | `_gen_blip(600)`     | Higher blip for upper floors (F2, F3) |
| `found`     | `_gen_found`         | Two-tone minor chime when a path is found |
| `failed`    | `_gen_failed`        | Descending growl when no path exists |
| `block`     | `_gen_block`         | Metallic thud when barricading/clearing a corridor |
| `alarm`     | `_gen_alarm`         | Oscillating siren; played on search failure |

### Key Implementation Detail: `_to_sound(samples_mono)`

Converts a NumPy float32 array (values in `[-1, 1]`) into a `pygame.mixer.Sound`:
1. Clips to `[-1, 1]`
2. Applies a 10 ms fade-in/fade-out ramp to avoid audio clicks
3. Scales to `int16` range (`× 32767`)
4. Duplicates mono → stereo with `np.column_stack`
5. Returns a `pygame.mixer.Sound` via `pygame.sndarray.make_sound`

### `play_blip_for_floor(floor)`
Called during node-expansion animation. Picks blip pitch based on floor:
- UB1/UB2 → `blip_lo` (ominous low tone)
- F2/F3 → `blip_hi` (safer-sounding high tone)
- F1 → `blip` (neutral)

---

## 6. Module: `gui.py`

### Purpose
The entire pygame interface. Handles the window, all rendering, user input, and animation. This is the largest and most complex module.

### Constants

| Constant      | Value      | Meaning |
|---------------|------------|---------|
| `WIDTH`       | 1280       | Window width in pixels |
| `HEIGHT`      | 720        | Window height in pixels |
| `MAP_WIDTH`   | 960        | Width of the map area (left portion) |
| `PANEL_X`     | 960        | X coordinate where the right panel starts |
| `PANEL_W`     | 320        | Width of the right control panel |
| `NODE_RADIUS` | 20         | Radius of each room circle |

Colors follow a green terminal / alien aesthetic (`GREEN`, `AMBER`, `RED`, `PATH_COLOR`, etc.).

### Helper Functions (module-level)

| Function | Description |
|----------|-------------|
| `rtext(surf, text, x, y, font, color, glow)` | Renders text with optional glow effect (draws twice in dim color offset) |
| `scanlines(surf, alpha)` | Draws horizontal lines every 3px to simulate a CRT scanline effect |
| `build_vignette()` | Pre-builds a semi-transparent dark border overlay for cinematic look |
| `pt_seg_dist(px, py, x1, y1, x2, y2)` | Point-to-segment distance; used to detect clicks near edges |
| `dashed_line(surf, color, start, end, ...)` | Draws a dashed line for blocked corridors |

### Class: `SporeParticle`
Floating alien spore particles emitted by heavily infested rooms.

| Attribute | Description |
|-----------|-------------|
| `x`, `y`  | Current position |
| `vx`, `vy`| Velocity (slow upward drift) |
| `life`    | Remaining lifetime (counts down each frame) |
| `size`    | Particle radius |

`update()` moves the particle and returns `False` when it dies. Particles are filtered each frame with a list comprehension:
```python
self.particles = [p for p in self.particles if p.update()]
```

### Class: `EvacuationApp`

#### State Variables (set in `__init__`)

| Variable | Description |
|----------|-------------|
| `city` | The `CityMap` instance (Building H) |
| `start_node` | Currently selected start room ID (default = 30, F3 Chapel) |
| `algorithm` | Currently selected algorithm name (default = `"A*"`) |
| `weights` | Dict of cost weights: `{"distance": 1.0, "infestation": 10.0, "radiation": 30.0}` |
| `expansion_anim` | Queue of node IDs to reveal during expansion animation |
| `path_anim` | The `SearchResult` being animated, or `None` |
| `anim_frame` | Frame counter used to pace animation speed |
| `expanded_visible` | Set of node IDs that have been revealed by animation so far |
| `path_progress` | How many path edges have been drawn so far |
| `particles` | List of `SporeParticle` objects currently alive |
| `status_lines` | 1–2 strings shown in the status bar at the bottom |
| `last_result` | Most recent `SearchResult`, shown in the LAST RESULT panel section |
| `popup` | `(lines, ttl)` tuple for the compare popup, or `None` |
| `mouse_pos` | Current mouse position, updated every `MOUSEMOTION` event |
| `show_labels` | Boolean — whether to show edge costs and heuristic values on the map |
| `vignette` | Pre-built vignette `Surface` (expensive, built once) |

#### Button Rects (set in `_init_buttons`)

| Attribute | Description |
|-----------|-------------|
| `algo_rects` | Dict `{"BFS": Rect, "UCS": Rect, "Greedy": Rect, "A*": Rect}` |
| `run_rect` | The large `[>] RUN SEARCH` button |
| `compare_rect` | `[=] COMPARE ALL` button |
| `reset_rect` | `[R] RESET MAP` button |
| `wt_rects` | Dict of `+`/`-` buttons for each weight, e.g. `"distance+"`, `"radiation-"` |
| `labels_rect` | `[L] SHOW LABELS: ON/OFF` toggle button |

#### Input Handling

**`handle_left_click(pos)`**
- If click is in the panel (`mx >= PANEL_X`): delegates to `_panel_click`
- If click is on a node: sets `start_node` (rejects exit nodes)
- If click is near an edge: toggles `edge.blocked`

**`handle_right_click(pos)`**
- If click is on a non-exit node: toggles `node.infestation` between 0 and 0.95

**`_panel_click(pos)`**
- Checks all button rects in order: algo buttons → run → compare → reset → weight +/- → labels toggle
- Each match plays a sound and returns early

**Keyboard shortcuts (in `run()` event loop):**

| Key     | Action |
|---------|--------|
| SPACE   | Run search |
| C       | Compare all algorithms |
| R       | Reset map |
| 1/2/3/4 | Select BFS/UCS/Greedy/A* |
| L       | Toggle SHOW LABELS |
| +/=     | Increase radiation weight |
| -       | Decrease radiation weight |
| ESC     | Quit |

#### Search Execution: `run_search()`
1. Clears any existing animation state
2. Calls `search.run(algorithm, city, start_node, weights)`
3. If no path found: plays `failed` + `alarm` sounds, updates status
4. If path found: populates `expansion_anim` from `result.expanded_order`, plays `blip_hi`

The expansion animation reveals nodes one at a time every 5 frames. After all nodes are revealed, the path draws one edge every 8 frames.

#### Update Loop: `update()`
Called every frame before `draw()`:
1. **Expansion phase:** if `expansion_anim` is non-empty, pop one node every 5 frames into `expanded_visible`, play a floor-pitched blip. When done, play `found` sound.
2. **Path phase:** after expansion, advance `path_progress` every 8 frames.
3. **Particles:** spawn new particles near infested rooms, remove dead ones.
4. **Popup:** count down the popup timer.

#### Rendering Pipeline: `draw()`
Draws layers in order (later layers appear on top):

```
1. _draw_grid()         background grid lines
2. _draw_floor_labels() floor bands + labels + ground-level marker
3. _draw_edges()        corridors, stairs, elevators + cost labels if show_labels
4. _draw_path()         cyan glowing evacuation path with arrowheads
5. _draw_nodes()        room circles, infestation glow, labels, h values if show_labels
6. particles            spore particles on top of nodes
7. _draw_panel()        right panel (all controls and info)
8. _draw_status()       status bar on the bottom of the map
9. scanlines()          CRT scanline overlay
10. vignette            dark border vignette
11. _draw_popup()       algorithm comparison popup (if active)
12. _draw_hud()         blinking "!! NO ROUTE !!" in top-left (if no path)
```

#### Edge Cost Labels (`_draw_edges` with `show_labels=True`)
For each unblocked edge:
1. Compute `cost = city.edge_cost(edge, weights)` with current weights
2. Find the midpoint of the edge
3. Offset the label perpendicular to the edge direction by 10px so it doesn't overlap the line
4. Render the cost in amber text on a dark semi-transparent background

The perpendicular offset vector for edge direction `(dx, dy)` is `(-dy/d, dx/d) * 10`.

#### Heuristic Labels (`_draw_nodes` with `show_labels=True` and Greedy/A*)
For each non-exit node:
1. Compute `raw_h = min(city.heuristic(node.id, e) for e in exits_list)`
   - This is the Euclidean distance to the nearest exit
2. Scale by `w_d` if the algorithm is A* (matching the actual heuristic used)
   - Greedy uses `h(n) = raw_h` (unscaled)
   - A* uses `h(n) = w_d * raw_h`
3. Render `"h=<value>"` in cyan above the node circle

Heuristic labels are only shown for Greedy and A* (BFS and UCS don't use a heuristic).

#### Intro Screen: `_show_intro()`
A 9-second fullscreen cinematic shown at startup with:
- Pulsing "BUILDING H" header in red
- Flashing `[!!] ALIEN INVASION DETECTED [!!]`
- Typewriter-effect warning messages
- Loading progress bar
- Building floor overview with color-coded threat levels
- Looping alarm sound
- Auto-advances after 9s or any keypress/click

#### Intro Screen: `compare_all()`
Runs all 4 algorithms on the current map state, formats a comparison table, and displays it as a timed popup (500 frames ≈ 8 seconds at 60 fps). User can also dismiss it with any key or click.

---

## 7. Entry Point: `main.py`

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from gui import main
if __name__ == "__main__":
    main()
```

Adds `src/` to `sys.path` so all four source modules are importable, then calls `EvacuationApp().run()` via `gui.main()`.

---

## 8. Tests: `test_search.py`

Run with: `python tests/test_search.py` (no pygame required).

The file adds `src/` to `sys.path` at the top, so it runs from any working directory.

### Test Functions

#### `test_all_algos_find_an_exit()`
Verifies that all 4 algorithms find a path from 4 different start nodes (including the deepest UB2 nodes). Checks:
- `result.found == True`
- `result.path[0] == start`
- `result.path[-1] in city.exits()`

#### `test_ucs_optimal_vs_others()`
Verifies UCS cost ≤ all other algorithms' costs from 4 different starts. Since UCS and A* are both optimal, they should produce equal costs. BFS and Greedy may produce higher costs.

#### `test_astar_avoids_hive()`
Sets radiation weight to 100 and starts A* from UB2 Server Room. Prints the path — with high radiation penalty, A* should route west via stairs rather than through the hive.

#### `test_blocking_path_reroutes()`
Runs A* from F3 Chapel, records the path, blocks the first edge, then runs again. Verifies the second search still finds a (different, longer) path.

#### `test_compare_table()`
Prints a formatted comparison table for all 4 algorithms starting from UB2 Server Room — same data as the in-app COMPARE ALL popup.

### Test Results (all pass)

```
start=UB2 server room       all 4 algorithms found an exit
start=F3 library            all 4 algorithms found an exit
start=F1 atrium             all 4 algorithms found an exit
start=UB2 HIVE itself       all 4 algorithms found an exit

UCS is optimal (no other algo finds a cheaper path)

A* from UB2 Server Room: [50, 40, 10, 99]
cost=11017.4, expanded=4

before blocking:  [30, 20, 10, 99]  cost=695.0
after blocking:   [30, 31, 32, 33, 23, 13, 98]  cost=1510.0

Algo         cost   expanded   hops  exit
-------- --------  ---------  -----  ---------------
BFS        5119.2          9      3  EXIT NORTH
UCS        5119.2          4      3  EXIT NORTH
Greedy     5119.2          4      3  EXIT NORTH
A*         5119.2          4      3  EXIT NORTH
```

---

## 9. Data Flow Diagram

```
User Input (click/key)
        │
        ▼
EvacuationApp.handle_*_click / keyboard event
        │
        ├── changes city state (block edge, set infestation, set start)
        │
        └── run_search()
                │
                ▼
           search.run(algorithm, city, start, weights)
                │
                ▼
           SearchResult
           ├── path          → drawn as cyan overlay in _draw_path()
           ├── expanded_order → animated one-by-one in update() → _draw_nodes()
           ├── total_cost    → shown in LAST RESULT panel
           └── runtime_ms   → shown in LAST RESULT panel

city_map.edge_cost(edge, weights)
   = w_d*dist + w_i*avg_inf*dist + w_r*avg_rad*dist
        │
        └── used by UCS and A* during search
            and by _draw_edges() for cost labels (when show_labels=True)

city_map.heuristic(n, exit)
   = Euclidean distance(n, exit)
        │
        └── used by Greedy: h(n) = min(heuristic(n,e) for e in exits)
            used by A*:     h(n) = w_d * min(heuristic(n,e) for e in exits)
            shown as "h=X" above nodes in _draw_nodes() (when show_labels=True)
```

---

## 10. Bug Fixes & Changes Made

This section documents every change made during debugging and feature development.

### Feature: SHOW LABELS toggle (edge costs + heuristic values)

**Problem:** The edge cost formula and heuristic values were invisible — users had to trust the algorithm's output without being able to inspect the values driving the search.

**Changes made to `gui.py`:**

1. **`__init__`** — Added `self.show_labels = False` state variable.

2. **`_init_buttons`** — Added `self.labels_rect = pygame.Rect(px, 444, bw, 24)` for the toggle button in the panel.

3. **`_panel_click`** — Added a check for `self.labels_rect.collidepoint(pos)` that flips `self.show_labels` and plays a blip sound.

4. **Event loop in `run()`** — Added `pygame.K_l` key handler to toggle `show_labels` via keyboard.

5. **`_draw_edges`** — When `show_labels` is True, renders the weighted edge cost at each edge's midpoint (amber text on dark background, offset perpendicular to the edge).

6. **`_draw_nodes`** — Precomputes `exits_list` and `h_scale` once per frame, then renders `"h=<value>"` (cyan text) above each non-exit node when `show_labels` is True and the selected algorithm uses a heuristic (Greedy or A*). A* scales the displayed value by `w_d`.

7. **`_draw_panel`** — Added the `[L] SHOW LABELS: ON/OFF` button between the COST WEIGHTS and LAST RESULT sections. Shifted the LAST RESULT section from `y=446` to `y=476` (+30px) and the TIPS section from `y=598` to `y=628` (+30px) to make room. Updated the last tip line to include `L labels`.

8. **`_init_buttons`** — Added separator line at `y=472` to visually separate the new button.

**Result:** Pressing `L` or clicking the panel button toggles visibility of:
- **Amber numbers on edges** = the full weighted cost `w_d·dist + w_i·inf·dist + w_r·rad·dist`
- **Cyan "h=X" above rooms** = the heuristic value used by the active algorithm (only shown for Greedy and A*)

### Verification

All tests in `tests/test_search.py` pass without modification. The changes are GUI-only and do not affect any algorithm logic.

---

## 11. How to Run

### Prerequisites

- Python 3.10 or newer
- `pygame-ce >= 2.5.0`
- `numpy >= 1.24.0`

### Install dependencies

```bash
pip install -r requirements.txt
```

> If you already have plain `pygame` installed, it is compatible. Do not install both `pygame` and `pygame-ce` in the same environment.

### Run the application

```bash
python main.py
```

### Run the tests (no display needed)

```bash
python tests/test_search.py
```

### Keyboard Reference

| Key      | Action |
|----------|--------|
| SPACE    | Run search with selected algorithm |
| C        | Compare all 4 algorithms side by side |
| R        | Reset map to default state |
| 1        | Select BFS |
| 2        | Select UCS |
| 3        | Select Greedy |
| 4        | Select A* |
| L        | Toggle edge cost / heuristic labels |
| + / =    | Increase radiation weight |
| -        | Decrease radiation weight |
| ESC      | Quit |

### Mouse Reference

| Action | Effect |
|--------|--------|
| Left-click a room | Set as survivor start position |
| Right-click a room | Toggle alien infestation (0% ↔ 95%) |
| Left-click a corridor | Block or unblock it |
| Left-click panel buttons | Algorithm select, run, compare, reset, weight adjust, labels toggle |
