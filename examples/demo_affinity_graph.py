import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from examples.affinity_scenario import build_demo_scenario
from src.math_engine.graph import traverse_affinity_graph
from src.utils.graph_animator import create_bfs_animation


def main():
    graph, jobs = build_demo_scenario()
    print("Acyclic affinity graph: illustrative edge shifts, not measured traffic.")
    shifts = traverse_affinity_graph(graph, jobs)
    print("Calculated global offsets (reference j1 = 0 ms):")
    for jid, shift in shifts.items():
        print(f"  {jid}: {shift:g} ms")
    output = os.path.join(PROJECT_ROOT, "visualizations", "affinity_bfs_animation.gif")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    create_bfs_animation(output)


if __name__ == "__main__":
    main()
