"""Compare shift decisions on shared workloads and fixed routes."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.core.models import Cluster, Job, Link, Phase
from src.core.trace_loader import TraceLoader
from src.math_engine.optimizer import DEFAULT_SCORE_WINDOW_MS
from src.scheduler.evaluator import make_fixed_placement, verify_paired_placement
from src.scheduler.policies import SHIFT_POLICIES
from src.scheduler.simulator import Simulator

POLICIES = ("uncoordinated", *SHIFT_POLICIES)
LABELS = {"uncoordinated": "Uncoordinated", "compatibility": "Vanilla model",
          "score": "Score control", "cooldown": "Cooldown control", "benefit": "Benefit rule"}
COLORS = {"uncoordinated": "#ff007f", "compatibility": "#00ddbb",
          "score": "#cf99ff", "cooldown": "#ffbd59", "benefit": "#69aaff"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def source_metadata(extra_sources=()):
    """Record the code and inputs used by either policy experiment runner."""
    sources = ["src/scheduler/simulator.py", "src/scheduler/evaluator.py",
               "src/scheduler/shift_policy.py", "src/math_engine/optimizer.py",
               "src/math_engine/graph.py", "src/core/models.py", "src/core/trace_loader.py",
               "experiments/shift_policy_experiment.py", "data/models/real_models.json",
               "data/traces/philly_cluster_trace.json", "data/traces/philly_2000_jobs.json",
               "data/traces/philly_10000_jobs.json"]
    sources.extend(path.relative_to(ROOT).as_posix()
                   for path in sorted((ROOT / "src/scheduler/policies").glob("*.py")))
    sources.extend(extra_sources)
    source_commit = os.environ.get("CASSINI_SOURCE_COMMIT")
    if source_commit is None:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                  capture_output=True, text=True)
        source_commit = revision.stdout.strip() if revision.returncode == 0 else None
    status = subprocess.run(["git", "status", "--porcelain", "--", *sources],
                            cwd=ROOT, capture_output=True, text=True)
    return {
        "source_commit": source_commit,
        "source_tree_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
        "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
        "versions": {p: importlib.metadata.version(p) for p in ("numpy", "matplotlib", "pillow", "networkx")},
    }


def build_workload(name, seed, num_jobs=None):
    """Existing inputs retain their original phase and bandwidth settings."""
    rng = random.Random(seed)
    if name == "macro":
        jobs = []
        for i in range(num_jobs if num_jobs is not None else 50):
            compute = float(rng.choice([25, 35, 45, 55]))
            communication = float(rng.choice([15, 20, 25]))
            demand = float(rng.choice([40, 50]))
            arrival = float(rng.randint(0, 400))
            iterations = rng.randint(5, 25)
            jobs.append(Job(f"J{i}", f"Job_{i}", [
                Phase("compute", compute, 0), Phase("communicate", communication, demand)
            ], arrival_time=arrival, total_iterations=iterations))
        count, incremental = 16, False
    elif name == "short":
        # A separate synthetic short-job case, not a production trace.
        jobs, arrival = [], 0.0
        for i in range(num_jobs if num_jobs is not None else 200):
            arrival += rng.expovariate(1 / 8)
            jobs.append(Job(f"S{i}", "Short synthetic job", [
                Phase("compute", rng.choice([40, 60, 80]), 0),
                Phase("communicate", rng.choice([10, 20]), 50)
            ], arrival_time=arrival, total_iterations=rng.randint(1, 5)))
        count, incremental = 4, True
    else:
        defaults = {"sample": (60, 16, False, "philly_cluster_trace.json"),
                    "2000": (2000, 32, True, "philly_2000_jobs.json"),
                    "10000": (10000, 32, True, "philly_10000_jobs.json")}
        size, count, incremental, filename = defaults[name]
        jobs = TraceLoader().load_trace(
            str(ROOT / "data/traces" / filename),
            bandwidth_gbps=25 if name == "sample" else 50,
            max_jobs=num_jobs if num_jobs is not None else size)
    return jobs, Cluster([], [Link(f"L{i}", 50) for i in range(count)]), incremental


def run_case(name, seed, *, num_jobs=None, min_gain_ms=0, cooldown_ms=100,
             score_window_ms=DEFAULT_SCORE_WINDOW_MS, output_dir=None, policies=POLICIES,
             remaining_work_scale=1.0):
    jobs, cluster, incremental = build_workload(name, seed, num_jobs)
    placement = make_fixed_placement(jobs, cluster.links, seed)
    input_hash = digest([asdict(job) for job in jobs])
    results, completed = {}, {}
    for policy in policies:
        sim = Simulator(cluster, penalty_factor=1.5, use_cassini=policy != "uncoordinated",
                        incremental=incremental, fixed_placement=placement,
                        shift_policy=policy if policy != "uncoordinated" else "compatibility",
                        min_gain_ms=min_gain_ms, cooldown_ms=cooldown_ms,
                        score_window_ms=score_window_ms, remaining_work_scale=remaining_work_scale)
        for job in jobs:
            sim.add_job_arrival(copy.deepcopy(job))
        start = time.perf_counter()
        sim.run_simulation()
        duration = time.perf_counter() - start
        verify_paired_placement(sim.completed_jobs, sim.completed_jobs, placement)
        completed[policy] = sim.completed_jobs
        times = [row["turnaround_time"] for row in sim.completed_jobs]
        if not all(math.isfinite(t) and t > 0 for t in times):
            raise ValueError("Completion times must be finite and positive.")
        if not all(0 <= row["shift_wait_ms"] <= row["turnaround_time"] + 1e-5
                   for row in sim.completed_jobs):
            raise ValueError("Shift waiting time exceeds completion time.")
        results[policy] = {
            "workload": name, "seed": seed, "policy": policy, "jobs": len(times),
            "input_sha256": input_hash, "placement_sha256": digest(placement),
            "incremental": incremental, "penalty": 1.5, "score_window_ms": score_window_ms,
            "min_gain_ms": min_gain_ms, "cooldown_ms": cooldown_ms,
            "remaining_work_scale": remaining_work_scale,
            "mean_jct_ms": statistics.mean(times),
            "p50_jct_ms": float(np.percentile(times, 50)),
            "p95_jct_ms": float(np.percentile(times, 95)),
            "mean_wait_ms": statistics.mean(row["shift_wait_ms"] for row in sim.completed_jobs),
            "shift_changes": sum(row["shift_changes"] for row in sim.completed_jobs),
            "simulation_seconds": duration, "shift_stats": sim.shift_stats,
        }
        if output_dir is not None:
            path = Path(output_dir) / f"{name}-seed{seed}-{policy}.json"
            path.write_text(json.dumps({**results[policy], "completions": sim.completed_jobs},
                                       indent=2, allow_nan=False) + "\n", encoding="utf-8")
    reference = results["compatibility"]
    for policy in policies:
        verify_paired_placement(completed["compatibility"], completed[policy], placement)
        results[policy]["mean_jct_gain_percent"] = (
            100 * (reference["mean_jct_ms"] - results[policy]["mean_jct_ms"])
            / reference["mean_jct_ms"])
        results[policy]["p95_jct_gain_percent"] = (
            100 * (reference["p95_jct_ms"] - results[policy]["p95_jct_ms"])
            / reference["p95_jct_ms"])
    return results, completed


def aggregate(runs):
    summary = {}
    for name in dict.fromkeys(row["workload"] for row in runs):
        summary[name] = {}
        for policy in POLICIES:
            rows = [r for r in runs if r["workload"] == name and r["policy"] == policy]
            if not rows:
                continue
            gains = [r["mean_jct_gain_percent"] for r in rows]
            summary[name][policy] = {
                "seeds": len(rows), "mean_gain_percent": statistics.mean(gains),
                "min_gain_percent": min(gains), "max_gain_percent": max(gains),
                "mean_jct_ms": statistics.mean(r["mean_jct_ms"] for r in rows),
                "mean_p95_jct_ms": statistics.mean(r["p95_jct_ms"] for r in rows),
                "mean_wait_ms": statistics.mean(r["mean_wait_ms"] for r in rows),
                "mean_shift_changes": statistics.mean(r["shift_changes"] for r in rows),
                "mean_simulation_seconds": statistics.mean(r["simulation_seconds"] for r in rows),
            }
    return summary


def plot_results(summary, examples, plot_dir, cdf_seed):
    plt.style.use("dark_background")
    names = list(summary)
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(max(8, len(names) * 2), 5))
    compared = [p for p in ("score", "cooldown", "benefit") if p in summary[names[0]]]
    if not compared:
        compared = ["uncoordinated"]
    width = 0.75 / len(compared)
    for index, policy in enumerate(compared):
        offset = (index - (len(compared) - 1) / 2) * width
        rows = [summary[name][policy] for name in names]
        means = np.array([r["mean_gain_percent"] for r in rows])
        errors = np.array([[m - r["min_gain_percent"] for m, r in zip(means, rows)],
                           [r["max_gain_percent"] - m for m, r in zip(means, rows)]])
        bars = ax.bar(x + offset, means, width * 0.92, color=COLORS[policy], label=LABELS[policy],
                      yerr=errors, capsize=4, error_kw={"elinewidth": 1, "ecolor": "#dddddd"})
        for bar, value, row in zip(bars, means, rows):
            label_y = row["max_gain_percent"] if value >= 0 else row["min_gain_percent"]
            ax.annotate(f"{value:+.2f}%", (bar.get_x() + bar.get_width() / 2, label_y),
                        xytext=(0, 8 if value >= 0 else -14), textcoords="offset points",
                        ha="center", fontsize=8)
    ax.axhline(0, color="white", linewidth=0.8)
    ax.set_xticks(x, [f"{name}\n(n={summary[name][compared[0]]['seeds']})" for name in names])
    ax.set_ylabel("Mean JCT reduction vs vanilla model (%)")
    ax.set_title("Shift decisions on identical routes\nBars: mean paired gain; whiskers: range across seeds")
    ax.grid(axis="y", alpha=0.2)
    ax.margins(y=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    comparison = plot_dir / "shift_policy_comparison.png"
    fig.savefig(comparison, dpi=180)
    plt.close(fig)

    columns = 2
    rows = math.ceil(len(names) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(12, rows * 3.8), squeeze=False)
    for ax, name in zip(axes.flat, names):
        for policy in examples[name]:
            times = np.sort([r["turnaround_time"] for r in examples[name][policy]])
            ax.plot(times, np.arange(1, len(times) + 1) / len(times),
                    color=COLORS[policy], label=LABELS[policy], linewidth=1.5)
        ax.set_title(f"{name}, seed {cdf_seed}")
        ax.set_xlabel("Turnaround time (ms)")
        ax.set_ylabel("CDF")
        ax.grid(alpha=0.2)
    for ax in list(axes.flat)[len(names):]:
        ax.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(examples[names[0]]), fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.suptitle("Same arrivals, profiles, and routes; shift waits included", y=0.995)
    cdf = plot_dir / "shift_policy_cdf.png"
    fig.savefig(cdf, dpi=180)
    plt.close(fig)
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (comparison, cdf)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workloads", nargs="+", choices=("macro", "sample", "short", "2000", "10000"),
                        default=["macro", "sample", "short"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 19, 42])
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    parser.add_argument("--num-jobs", type=int, help="Limit each workload for a quick check")
    parser.add_argument("--min-gain-ms", type=float, default=0)
    parser.add_argument("--cooldown-ms", type=float, default=100)
    parser.add_argument("--score-window-ms", type=float, default=DEFAULT_SCORE_WINDOW_MS)
    parser.add_argument("--remaining-work-scale", type=float, default=1.0,
                        help="Multiply only the benefit rule's remaining-work estimate")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/shift-policy")
    parser.add_argument("--plot-dir", type=Path, default=ROOT / "visualizations")
    args = parser.parse_args(argv)
    if args.num_jobs is not None and args.num_jobs <= 0:
        parser.error("--num-jobs must be positive")
    if not math.isfinite(args.min_gain_ms) or args.min_gain_ms < 0:
        parser.error("--min-gain-ms must be finite and nonnegative")
    if not math.isfinite(args.cooldown_ms) or args.cooldown_ms < 0:
        parser.error("--cooldown-ms must be finite and nonnegative")
    if not math.isfinite(args.score_window_ms) or args.score_window_ms < 1:
        parser.error("--score-window-ms must be finite and at least 1 ms")
    if not math.isfinite(args.remaining_work_scale) or args.remaining_work_scale <= 0:
        parser.error("--remaining-work-scale must be finite and positive")
    if len(set(args.seeds)) != len(args.seeds) or len(set(args.workloads)) != len(args.workloads):
        parser.error("Seeds and workloads must not contain duplicates")
    if ("compatibility" not in args.policies or len(args.policies) < 2
            or len(set(args.policies)) != len(args.policies)):
        parser.error("Choose distinct policies including compatibility and at least one alternative")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.plot_dir.mkdir(parents=True, exist_ok=True)
    provenance = source_metadata()
    runs, examples = [], {}
    for name in args.workloads:
        for seed in args.seeds:
            print(f"Running {name}, seed {seed} ...", flush=True)
            results, completed = run_case(
                name, seed, num_jobs=args.num_jobs, min_gain_ms=args.min_gain_ms,
                cooldown_ms=args.cooldown_ms, score_window_ms=args.score_window_ms,
                output_dir=args.output_dir, policies=args.policies,
                remaining_work_scale=args.remaining_work_scale)
            runs.extend(results.values())
            if seed == args.seeds[0]:
                examples[name] = completed
            print("  " + ", ".join(f"{LABELS[p]}: {results[p]['mean_jct_gain_percent']:+.3f}%"
                                   for p in args.policies if p not in ("uncoordinated", "compatibility")), flush=True)
    summary = aggregate(runs)
    figures = plot_results(summary, examples, args.plot_dir, args.seeds[0])
    manifest = {
        **provenance,
        "workloads": args.workloads, "seeds": args.seeds, "policies": args.policies,
        "num_jobs": args.num_jobs,
        "min_gain_ms": args.min_gain_ms, "cooldown_ms": args.cooldown_ms,
        "remaining_work_scale": args.remaining_work_scale,
        "score_window_ms": args.score_window_ms, "shift_waits_charged": True,
        "placement": "shared seeded fixed routes; independently verified for every run",
        "remaining_work": "true remaining work times remaining_work_scale; decision input only; no future arrivals; frozen-score estimate",
        "aggregation": "mean of per-seed paired JCT reductions; range is not a confidence interval",
        "baseline": "current Cassini-based fast model; not full paper implementation",
        "cdf_seed": args.seeds[0], "runs": runs, "summary": summary, "figures": figures,
    }
    (args.plot_dir / "shift_policy_results.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("\nMean paired JCT reduction vs vanilla model (range across seeds):")
    for name in args.workloads:
        for policy in args.policies:
            if policy in ("uncoordinated", "compatibility"):
                continue
            row = summary[name][policy]
            print(f"  {name:>6} {LABELS[policy]:>17}: {row['mean_gain_percent']:+.3f}% "
                  f"[{row['min_gain_percent']:+.3f}, {row['max_gain_percent']:+.3f}]")
    print(f"Plots and manifest: {args.plot_dir}")
    return manifest


if __name__ == "__main__":
    main()
