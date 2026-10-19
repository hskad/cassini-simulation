"""Build the README figures from current simulator events and graph results."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import numpy as np
import PIL

from src.core.models import Cluster, Job, Link, Phase
from src.scheduler.simulator import Simulator
from src.utils.comparison_plots import plot_comparison
from src.utils.readme_animations import geometric_animation, affinity_animation
from src.utils.readme_workload import build_workload_figures

ROOT = Path(__file__).resolve().parents[2]


def _jobs(count=2, iterations=10):
    return [Job(chr(65+i), chr(65+i), [Phase("compute", 50, 0),
                Phase("communicate", 50, 50)], total_iterations=iterations)
            for i in range(count)]


def _simulate(jobs, cluster, jitter=0.0, include_static=False):
    policies = [("uncoordinated", False, None)]
    if include_static:
        policies.append(("static-shifts", True, None))
    policies.append(("cassini", True, 0.05))
    results = {}
    for name, enabled, threshold in policies:
        sim = Simulator(cluster, use_cassini=enabled, record_history=True,
                        solver="exact", compute_jitter=jitter, seed=42,
                        drift_threshold=threshold)
        for job in copy.deepcopy(jobs):
            sim.add_job_arrival(job)
        sim.run_simulation()
        results[name] = sim
    return results


def build_readme_visuals(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    jobs = _jobs()
    cluster = Cluster([], [Link("L1", 50)], {"L1": jobs})
    aligned = _simulate(jobs, cluster)
    noisy_jobs = _jobs(iterations=100)
    jitter = _simulate(noisy_jobs, Cluster([], [Link("L1", 50)], {"L1": noisy_jobs}),
                       jitter=0.04, include_static=True)
    # Only the selected figures enter Git. Temporary plots remain outside docs.
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        plot_comparison(aligned, scratch, window=600, max_jobs=2)
        (out / "bandwidth.png").write_bytes((scratch / "bandwidth.png").read_bytes())
        (out / "completion.png").unlink(missing_ok=True)
        plot_comparison(jitter, scratch, window=3000, max_jobs=2)
        (out / "drift.png").write_bytes((scratch / "drift.png").read_bytes())
    workload = build_workload_figures(out)
    print("Building circular alignment animation...", flush=True)
    geometric = geometric_animation(out / "geometric-alignment.gif")
    (out / "phase-alignment.gif").unlink(missing_ok=True)
    print("Building affinity graph animation...", flush=True)
    graph = affinity_animation(out / "affinity-traversal.gif")
    summaries = {}
    for scenario, simulations in [("aligned", aligned), ("jitter", jitter)]:
        summaries[scenario] = {name: {
            "mean_jct_ms": float(np.mean([r["turnaround_time"] for r in sim.completed_jobs])),
            "mean_wait_ms": float(np.mean([r["wait_time"] for r in sim.completed_jobs])),
            "adjustments": len(sim.adjustments),
        } for name, sim in simulations.items()}
    sources = ["src/scheduler/simulator.py", "src/math_engine/optimizer.py",
               "src/math_engine/graph.py", "src/scheduler/evaluator.py",
               "src/utils/comparison_plots.py", "src/utils/readme_visuals.py",
               "src/utils/plot_style.py", "src/utils/readme_animations.py",
               "src/utils/readme_workload.py", "data/models/real_models.json"]
    manifest = {
        "command": "python3 cassini.py docs", "source": "synthetic examples from the current simulator",
        "profile": {"compute_ms": 50, "communication_ms": 50, "demand_gbps": 50,
                    "link_capacity_gbps": 50, "solver": "exact", "resolution_ms": 1},
        "aligned": {"iterations": 10, "jitter_fraction": 0, "plot_window_ms": 600},
        "jitter": {"iterations": 100, "jitter_fraction": 0.04, "seed": 42,
                   "drift_threshold": 0.05, "plot_window_ms": 3000},
        "correction_action": "delay to the next nominal phase start; simulation assumption",
        "summaries": summaries, "affinity_graph": graph, "geometric": geometric, "workload_comparison": workload,
        "source_sha256": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
        "versions": {"matplotlib": matplotlib.__version__, "pillow": PIL.__version__},
    }
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print("README visuals:", out)
