# Building H - Alien Evacuation Planner

CSC474 - Artificial Intelligence
Holy Spirit University of Kaslik (USEK)
Spring 2026

## The scenario

It's 02:13 AM. Something has come up from the sub-levels of Building H. The
seismic sensors caught it first - then the lights in UB2 cut out and the
biology lab cameras went dark. Whatever it is, it's spreading. The university
security system has gone into emergency mode. **Static evacuation signs are
useless** - they don't know that the central elevator is blocked at UB1, that
the corridor between F1 Reception and the Atrium is crawling with something,
or that radiation from the hive on UB2 is leaking up through the stairwells.

This is the **Building H Evac Protocol**: an AI-driven evacuation planner
that, given the current state of the building, computes the safest route out
for whoever is left inside. The user picks where they're stuck, sets how
much they care about distance / infestation / radiation, and the planner
finds them a way out. Or tells them there isn't one.

## What it does

- Models all 5 floors of Building H (F3, F2, F1, UB1, UB2) as a connected graph
- Lets the user click any room to designate it as their current position
- Right-click any room to toggle its infestation level (simulating spread)
- Click any corridor / stairwell / elevator to barricade or clear it
- Runs one of four classical search algorithms (BFS, UCS, Greedy, A\*) and
  animates the search step by step
- Plays procedurally-generated alien audio (ambient hum, click blips when nodes
  are expanded, alarm sounds on failure)
- Has a "Compare All" mode that benchmarks all four algorithms on the same
  scenario and shows the trade-offs in a side-by-side table

## How to run

You need Python 3.10+ with pygame-ce and numpy installed.

```bash
pip install -r requirements.txt
python main.py
```

> **Note on `pygame-ce` vs `pygame`:** we use `pygame-ce` (the
> Community Edition fork) because it ships pre-built Windows wheels for
> Python 3.13 and 3.14, while the original `pygame` package fails to
> install on those versions. The two are drop-in compatible - the
> `import pygame` statements in our code work unchanged with either one.
> If you happen to already have plain `pygame` installed, the project
> will work with that too, just don't try to install both at the same
> time in the same environment.

If you don't have audio output (e.g. you're on a server or the SDL audio
driver fails to initialize), the program falls back to a silent mode and
keeps working.

To run the algorithm tests:

```bash
python tests/test_search.py
```

## Project structure

```
evacuation_planner/
├── main.py               # entry point
├── requirements.txt      # pygame + numpy
├── README.md
├── docs/
│   └── report.md         # the project report (problem formulation, AI justification, etc.)
├── src/
│   ├── city_map.py       # Building H graph + the alien-themed scenario
│   ├── search.py         # BFS, UCS, Greedy, A*
│   ├── audio.py          # procedural sound synthesis (no audio files needed)
│   └── gui.py            # pygame interface
└── tests/
    └── test_search.py    # unit tests for the algorithms
```

## How to play

1. Launch with `python main.py`. A 1280x720 window opens with the cross-section
   of Building H. The five floors are stacked vertically: F3 at the top, then
   F2, F1, ground level marker, UB1, UB2.

2. **The infested rooms glow red.** The deeper you go underground, the worse it
   gets. UB2 is the hive itself.

3. **Pick where you're trapped.** Click any non-exit room. A cyan reticle marks
   your start position.

4. **Tune the cost weights** on the right panel:
   - `Distance` weight: how much you care about a short walk
   - `Infestation` weight: how much you avoid alien-occupied rooms
   - `Radiation` weight: how much you avoid bio-radiation hotspots
   Use `+` and `-` to change the radiation weight on the fly. Setting it
   to 0 turns the AI into a pure-distance planner; setting it high makes
   the AI take huge detours to avoid the hive.

5. **Choose your algorithm** with keys `1` (BFS), `2` (UCS), `3` (Greedy), `4` (A\*).

6. **Press SPACE** to compute the route. You'll see nodes light up in the
   order the algorithm explored them (with a creepy blip per expansion -
   underground floors blip lower, upper floors blip higher), then the final
   evacuation path is drawn in cyan with a glow.

7. **Press C** to run all four algorithms on the same map and see the
   comparison.

8. **Simulate the invasion spreading**: right-click any uninfested room - it
   turns red. Run the search again and watch A\* take a different route. Block
   a corridor by clicking it - if you block all paths the system goes into
   alarm mode with a "NO ROUTE" warning.

### Cheat sheet

| Key      | Action                          |
|----------|---------------------------------|
| SPACE    | Run search                      |
| C        | Compare all 4 algorithms        |
| R        | Reset the map                   |
| 1/2/3/4  | Pick BFS / UCS / Greedy / A\*   |
| +/-      | Adjust radiation cost weight    |
| ESC      | Quit                            |
| Left-click node  | Set start position      |
| Right-click node | Toggle infestation     |
| Click an edge    | Block / clear corridor |

## The procedural audio

We don't ship any audio files with the project. All sounds are synthesized at
startup using numpy + pygame. There are 8 procedurally generated sounds:

- **ambient hum** - a slow detuned drone with subtle noise, looped throughout
- **blip** (high / mid / low) - alien click sounds for node expansion, pitched
  by floor so you can hear when the search is exploring underground vs upstairs
- **found** - two-tone minor-mode chime when a path is found
- **failed** - descending growl when no path exists
- **block** - metallic thud when toggling a barricade
- **alarm** - oscillating siren that plays when no route is available

If your environment has no audio output the module silently falls back to a
no-op and the rest of the app keeps working.

## Algorithms - quick recap

| Algorithm | Optimal under our cost? | Uses heuristic? | Notes |
|-----------|-------------------------|-----------------|-------|
| BFS       | Only by hop count       | No              | Baseline. Ignores danger. |
| UCS       | Yes                     | No              | Always finds the safest path, expands more nodes. |
| Greedy    | No                      | Yes             | Goes for the closest exit by straight line. Often unsafe. |
| A\*       | Yes (admissible h)      | Yes             | Same answer as UCS, usually with fewer expansions. |

The full justification for picking A\* is in `docs/report.md`.

## Limitations (also discussed in the report)

- Building H is hand-modeled. Real deployment would need a floor-plan importer.
- Aliens don't actually move during a search - infestation values are static
  while the algorithm runs. (You can simulate spread by right-clicking rooms
  between runs.)
- Single agent only - we don't model multiple students fleeing simultaneously
  and competing for the same staircase.
- The three "verticals" (west stairs / central elevator / east stairs) are all
  edges in the graph but treated identically apart from rendering color.

## Team

[your name here], [partner name here] - CSC474 Spring 2026
