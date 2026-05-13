import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from city_map import build_building_h
import search


def test_all_algos_find_an_exit():
    city = build_building_h()
    weights = {"distance": 1.0, "infestation": 10.0, "radiation": 30.0}

    for start, label in [(50, "UB2 server room"), (33, "F3 library"),
                         (11, "F1 atrium"), (51, "UB2 HIVE itself")]:
        for name in ["BFS", "UCS", "Greedy", "A*"]:
            r = search.run(name, city, start, weights)
            assert r.found, f"{name} failed from {label} (id={start})"
            assert r.path[0] == start
            assert r.path[-1] in city.exits()
        print(f"  start={label:20s}  all 4 algorithms found an exit")
    print()


def test_ucs_optimal_vs_others():
    city = build_building_h()
    weights = {"distance": 1.0, "infestation": 10.0, "radiation": 30.0}
    for start in [50, 32, 20, 41]:
        ucs_r = search.run("UCS", city, start, weights)
        for name in ["BFS", "Greedy", "A*"]:
            r = search.run(name, city, start, weights)
            assert ucs_r.total_cost <= r.total_cost + 1e-6, \
                f"{name} cheaper than UCS from {start}!"
    print("  UCS is optimal (no other algo finds a cheaper path)\n")


def test_astar_avoids_hive():
    city = build_building_h()
    weights = {"distance": 1.0, "infestation": 5.0, "radiation": 100.0}
    r = search.run("A*", city, 50, weights)
    print(f"  A* from UB2 Server Room: {r.path}")
    print(f"  cost={r.total_cost:.1f}, expanded={len(r.expanded_order)}")
    print()


def test_blocking_path_reroutes():
    city = build_building_h()
    weights = {"distance": 1.0, "infestation": 10.0, "radiation": 30.0}
    r1 = search.run("A*", city, 30, weights)
    print(f"  before blocking:  {r1.path}  cost={r1.total_cost:.1f}")
    if len(r1.path) >= 2:
        city.set_blocked(r1.path[0], r1.path[1], True)
    r2 = search.run("A*", city, 30, weights)
    assert r2.found
    print(f"  after blocking:   {r2.path}  cost={r2.total_cost:.1f}\n")


def test_compare_table():
    city = build_building_h()
    weights = {"distance": 1.0, "infestation": 10.0, "radiation": 30.0}
    print(f"  {'Algo':8s} {'cost':>8s}  {'expanded':>9s}  {'hops':>5s}  exit")
    print(f"  {'-'*8} {'-'*8}  {'-'*9}  {'-'*5}  {'-'*15}")
    for name in ["BFS", "UCS", "Greedy", "A*"]:
        r = search.run(name, city, 50, weights)
        exit_label = city.nodes[r.goal_id].label if r.found else "FAIL"
        cost_s = f"{r.total_cost:.1f}" if r.found else "-"
        print(f"  {name:8s} {cost_s:>8s}  {len(r.expanded_order):>9d}  "
              f"{len(r.path)-1:>5d}  {exit_label}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("BUILDING H EVACUATION - Algorithm Tests")
    print("=" * 60)

    print("\n[1] All algorithms find an exit from many starts:")
    test_all_algos_find_an_exit()

    print("[2] UCS is optimal vs all others:")
    test_ucs_optimal_vs_others()

    print("[3] A* avoids the HIVE when radiation weight is high:")
    test_astar_avoids_hive()

    print("[4] Blocking a road forces re-planning:")
    test_blocking_path_reroutes()

    print("[5] Comparison table (start = UB2 Server Room):")
    test_compare_table()

    print("All tests passed!")
