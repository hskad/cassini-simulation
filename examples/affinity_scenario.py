"""Shared, acyclic graph example with illustrative edge shifts in milliseconds."""
from src.core.models import Cluster, Job, Link, Phase
from src.math_engine.graph import build_affinity_graph


def build_demo_scenario():
    jobs = {f"j{i}": Job(f"j{i}", f"Example job {i}", [Phase("compute", 100, 0)])
            for i in range(1, 6)}
    cluster = Cluster([], [Link(f"l{i}", 50) for i in range(1, 4)], {
        "l1": [jobs["j1"], jobs["j2"], jobs["j3"]],
        "l2": [jobs["j2"], jobs["j4"]],
        "l3": [jobs["j3"], jobs["j5"]],
    })
    shifts = {
        "l1": {"j1": 0.0, "j2": 10.0, "j3": 20.0},
        "l2": {"j2": 0.0, "j4": 30.0},
        "l3": {"j3": 0.0, "j5": 40.0},
    }
    return build_affinity_graph(cluster, shifts), jobs
