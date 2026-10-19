"""Build the README figures from current simulator events and graph results."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Patch, Rectangle
import numpy as np
import PIL

from src.core.models import Cluster, Job, Link, Phase
from src.math_engine.graph import build_affinity_graph, traverse_affinity_graph
from src.scheduler.evaluator import PlacementCandidate, score_candidate
from src.scheduler.simulator import Simulator
from src.utils.comparison_plots import COLORS, plot_comparison

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


def _phase_gif(simulations, filename):
    stop = 600.0
    fig, axes = plt.subplots(2, 1, figsize=(10, 4.8), sharex=True, layout="constrained")
    fig.suptitle("Phase alignment | executed compute, communication, and waits", fontsize=14)
    clock = fig.text(0.99, 0.99, "", ha="right", va="top", fontsize=10)
    patches, cursors = [], []
    for ax, (name, sim) in zip(axes, simulations.items()):
        for row in sim.phase_history:
            if row["start"] >= stop:
                continue
            rect = Rectangle((row["start"], ["A", "B"].index(row["job_id"])-0.3),
                             0, 0.6, facecolor=COLORS[row["type"]],
                             edgecolor="white", linewidth=0.5)
            ax.add_patch(rect)
            patches.append((rect, row["start"], min(stop, row["end"])))
        cursors.append(ax.axvline(0, color="#185944", linewidth=2))
        ax.set(xlim=(0, stop), ylim=(1.5, -0.5), yticks=[0, 1], yticklabels=["A", "B"])
        ax.set_title(name, loc="left", fontsize=12)
        ax.grid(axis="x", alpha=0.15)
    axes[-1].set_xlabel("Simulation time (ms)")
    fig.legend(handles=[Patch(color=color, label=name) for name, color in COLORS.items()],
               loc="outside lower center", ncol=3)
    frames = list(np.linspace(0, stop, 61)) + [stop]*18

    def update(time):
        for patch, left, right in patches:
            patch.set_width(max(0, min(time, right)-left))
        for cursor in cursors:
            cursor.set_xdata([time, time])
        clock.set_text(f"t = {time:.0f} ms")
        return [clock] + cursors + [p[0] for p in patches]

    clip = animation.FuncAnimation(fig, update, frames=frames, interval=1000/12, blit=False)
    clip.save(filename, writer=animation.PillowWriter(fps=12), dpi=105)
    plt.close(fig)


def _affinity_gif(filename):
    jobs = _jobs(3)
    cluster = Cluster([], [Link("L1", 50), Link("L2", 50)],
                      {"L1": jobs[:2], "L2": jobs[1:]})
    score, weights = score_candidate(PlacementCandidate("chain", cluster), solver="exact")
    graph = build_affinity_graph(cluster, weights)
    shifts = traverse_affinity_graph(graph, {j.job_id: j for j in jobs})
    fig, ax = plt.subplots(figsize=(9.5, 4.8), layout="constrained")
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    fig.suptitle("Affinity graph | one time-shift per job", fontsize=15)
    positions = {"A": (0.15, 0.8), "B": (0.15, 0.5), "C": (0.15, 0.2),
                 "L1": (0.52, 0.66), "L2": (0.52, 0.34)}
    ax.text(0.15, 0.95, "JOBS", ha="center", fontsize=11, color="#555555")
    ax.text(0.52, 0.95, "SHARED LINKS", ha="center", fontsize=11, color="#555555")
    ax.text(0.8, 0.95, "GLOBAL SHIFT", ha="center", fontsize=11, color="#555555")
    lines, nodes, labels = {}, {}, {}
    for jid in sorted(graph.U):
        for lid in graph.edges_U_to_V[jid]:
            x1, y1 = positions[jid]
            x2, y2 = positions[lid]
            lines[(jid, lid)], = ax.plot([x1, x2], [y1, y2], color="#B6B9BE", linewidth=3, zorder=1)
            ax.text((x1+x2)/2, (y1+y2)/2, f"{weights[lid][jid]:g} ms",
                    ha="center", va="center", fontsize=10,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 2}, zorder=3)
    for jid in sorted(graph.U):
        x, y = positions[jid]
        nodes[jid] = Circle((x, y), 0.055, facecolor="#DEE8F2", edgecolor="#3677B5", linewidth=2, zorder=4)
        ax.add_patch(nodes[jid])
        ax.text(x, y, jid, ha="center", va="center", fontsize=13, zorder=5)
        labels[jid] = ax.text(0.8, y, "", ha="center", va="center", fontsize=13)
    for lid in sorted(graph.V):
        x, y = positions[lid]
        ax.add_patch(Rectangle((x-0.055, y-0.05), 0.11, 0.1, facecolor="#F5E4D2",
                               edgecolor="#DD8841", linewidth=2, zorder=4))
        ax.text(x, y, lid, ha="center", va="center", fontsize=12, zorder=5)
    caption = ax.text(0.5, 0.04, "", ha="center", fontsize=11)
    b_formula = f"B = (0 - {weights['L1']['A']:g} + {weights['L1']['B']:g}) mod 100 = {shifts['B']:g} ms"
    c_formula = f"C = ({shifts['B']:g} - {weights['L2']['B']:g} + {weights['L2']['C']:g}) mod 100 = {shifts['C']:g} ms"
    stages = [
        ([], [], "Each edge stores a shift calculated for one link."),
        (["A"], [], f"A is the reference: {shifts['A']:g} ms."),
        (["A", "B"], [("A", "L1"), ("B", "L1")], b_formula),
        (["A", "B", "C"], [("B", "L2"), ("C", "L2")], c_formula),
        (["A", "B", "C"], list(lines), "A and C can communicate together. B uses the other half of the period."),
    ]

    def update(index):
        visited, active, text = stages[index]
        for jid in nodes:
            nodes[jid].set_facecolor("#9CC8AE" if jid in visited else "#DEE8F2")
            labels[jid].set_text(f"{shifts[jid]:g} ms" if jid in visited else "--")
        for edge, line in lines.items():
            line.set_color("#2F7956" if edge in active else "#B6B9BE")
        caption.set_text(text)

    frames = [stage for stage in range(len(stages)) for _ in range(10)] + [4]*15
    clip = animation.FuncAnimation(fig, update, frames=frames, interval=100, blit=False)
    clip.save(filename, writer=animation.PillowWriter(fps=10), dpi=105)
    plt.close(fig)
    return {"compatibility_score": score, "link_shifts_ms": weights, "global_shifts_ms": shifts}


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
        for source, target in [("bandwidth.png", "bandwidth.png"), ("jct.png", "completion.png")]:
            (out / target).write_bytes((scratch / source).read_bytes())
        plot_comparison(jitter, scratch, window=3000, max_jobs=2)
        (out / "drift.png").write_bytes((scratch / "drift.png").read_bytes())
    print("Building phase animation...", flush=True)
    _phase_gif(aligned, out / "phase-alignment.gif")
    print("Building affinity graph animation...", flush=True)
    graph = _affinity_gif(out / "affinity-traversal.gif")
    summaries = {}
    for scenario, simulations in [("aligned", aligned), ("jitter", jitter)]:
        summaries[scenario] = {name: {
            "mean_jct_ms": float(np.mean([r["turnaround_time"] for r in sim.completed_jobs])),
            "mean_wait_ms": float(np.mean([r["wait_time"] for r in sim.completed_jobs])),
            "adjustments": len(sim.adjustments),
        } for name, sim in simulations.items()}
    sources = ["src/scheduler/simulator.py", "src/math_engine/optimizer.py",
               "src/math_engine/graph.py", "src/scheduler/evaluator.py",
               "src/utils/comparison_plots.py", "src/utils/readme_visuals.py"]
    manifest = {
        "command": "python3 cassini.py docs", "source": "synthetic examples from the current simulator",
        "profile": {"compute_ms": 50, "communication_ms": 50, "demand_gbps": 50,
                    "link_capacity_gbps": 50, "solver": "exact", "resolution_ms": 1},
        "aligned": {"iterations": 10, "jitter_fraction": 0, "plot_window_ms": 600},
        "jitter": {"iterations": 100, "jitter_fraction": 0.04, "seed": 42,
                   "drift_threshold": 0.05, "plot_window_ms": 3000},
        "correction_action": "delay to the next nominal phase start; simulation assumption",
        "summaries": summaries, "affinity_graph": graph,
        "source_sha256": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
        "versions": {"matplotlib": matplotlib.__version__, "pillow": PIL.__version__},
    }
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print("README visuals:", out)
