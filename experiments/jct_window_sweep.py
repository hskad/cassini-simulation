"""
End-to-End Cluster JCT Sweep Across Scoring Windows.
Evaluates how the scoring window bound (150ms to 2400ms) affects actual
Job Completion Time (JCT), P95 tail latency, and simulator runtime.
"""

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.core.models import Link, Cluster, Job
from src.core.trace_loader import TraceLoader
from src.scheduler.simulator import Simulator
from src.scheduler.evaluator import make_fixed_placement
from src.math_engine.optimizer import DEFAULT_SCORE_WINDOW_MS


def run_workload_window_sweep(
    workload_name: str,
    windows: List[float],
    seed: int = 42,
    num_jobs: int = None,
    output_dir: Path = None,
    num_windows: int = 1
) -> Dict[str, Any]:
    print(f"\n==================================================================")
    print(f"  Running JCT Window Sweep for: {workload_name.upper()} (Seed={seed})")
    print(f"  Windows: {windows} ms | Strided segments: {num_windows}")
    print(f"==================================================================")

    loader = TraceLoader()
    if workload_name == "sample":
        default_count = 60
        bandwidth = 25.0
        num_links = 16
        incremental = False
        trace_path = TraceLoader.DEFAULT_TRACE_PATH
    elif workload_name == "2000":
        default_count = 2000
        bandwidth = 50.0
        num_links = 32
        incremental = True
        trace_path = ROOT / "data" / "traces" / "philly_2000_jobs.json"
        if not trace_path.exists():
            from experiments.large_scale_2000_jobs import ensure_2000_job_trace
            ensure_2000_job_trace(loader, num_jobs=2000, seed=42)
    else:
        raise ValueError(f"Unknown workload: {workload_name}")

    actual_jobs_count = num_jobs if num_jobs is not None else default_count
    jobs = loader.load_trace(str(trace_path), bandwidth_gbps=bandwidth, max_jobs=actual_jobs_count)
    links = [Link(f"L{i}", 50.0) for i in range(num_links)]
    base_cluster = Cluster([], links)
    placement = make_fixed_placement(jobs, links, seed=seed)

    # 1. Run Baseline (Uncoordinated FIFO, tau=0)
    print(f"[*] Running Uncoordinated Baseline ({len(jobs)} jobs)...", flush=True)
    b_sim = Simulator(
        base_cluster, penalty_factor=1.5, use_cassini=False,
        incremental=incremental, fixed_placement=placement
    )
    for j in copy.deepcopy(jobs):
        b_sim.add_job_arrival(j)
    t0 = time.perf_counter()
    b_sim.run_simulation()
    b_wall = time.perf_counter() - t0

    b_jcts = [r["turnaround_time"] for r in b_sim.completed_jobs]
    b_mean = float(np.mean(b_jcts))
    b_p50 = float(np.percentile(b_jcts, 50))
    b_p95 = float(np.percentile(b_jcts, 95))
    print(f"    Baseline Mean JCT: {b_mean:.2f} ms (P50: {b_p50:.2f} ms, P95: {b_p95:.2f} ms) [took {b_wall:.2f}s]")

    # 2. Sweep across scoring windows
    sweep_records = []
    for w in windows:
        print(f"[*] Running CASSINI with Score Window = {w:g} ms...", flush=True)
        c_sim = Simulator(
            base_cluster, penalty_factor=1.5, use_cassini=True,
            incremental=incremental, fixed_placement=placement,
            score_window_ms=w
        )
        for j in copy.deepcopy(jobs):
            c_sim.add_job_arrival(j)
        t_start = time.perf_counter()
        c_sim.run_simulation()
        c_wall = time.perf_counter() - t_start

        c_jcts = [r["turnaround_time"] for r in c_sim.completed_jobs]
        c_mean = float(np.mean(c_jcts))
        c_p50 = float(np.percentile(c_jcts, 50))
        c_p95 = float(np.percentile(c_jcts, 95))
        mean_reduction = 100.0 * (b_mean - c_mean) / b_mean
        p95_reduction = 100.0 * (b_p95 - c_p95) / b_p95

        total_wait = sum(r.get("shift_wait_ms", 0.0) for r in c_sim.completed_jobs)
        mean_wait = total_wait / len(c_jcts) if c_jcts else 0.0

        rec = {
            "window_ms": w,
            "mean_jct_ms": c_mean,
            "p50_jct_ms": c_p50,
            "p95_jct_ms": c_p95,
            "mean_reduction_percent": mean_reduction,
            "p95_reduction_percent": p95_reduction,
            "mean_wait_ms": mean_wait,
            "wall_time_seconds": c_wall
        }
        sweep_records.append(rec)
        print(f"    Window {w:4g} ms -> Mean Reduction: {mean_reduction:+.2f}% | P95 Reduction: {p95_reduction:+.2f}% | Wall Time: {c_wall:.2f}s")

    return {
        "workload": workload_name,
        "jobs": len(jobs),
        "seed": seed,
        "baseline": {
            "mean_jct_ms": b_mean,
            "p50_jct_ms": b_p50,
            "p95_jct_ms": b_p95,
            "wall_time_seconds": b_wall
        },
        "sweep": sweep_records
    }


def plot_sweep(results: List[Dict[str, Any]], plot_path: Path):
    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    colors = {"sample": "#00ddbb", "2000": "#ffbd59", "macro": "#cf99ff"}
    markers = {"sample": "o", "2000": "s", "macro": "^"}

    for res in results:
        w_name = res["workload"]
        c = colors.get(w_name, "#ffffff")
        m = markers.get(w_name, "o")
        label_base = f"{res['jobs']} jobs ({w_name})"

        x = [r["window_ms"] for r in res["sweep"]]
        y_mean = [r["mean_reduction_percent"] for r in res["sweep"]]
        y_p95 = [r["p95_reduction_percent"] for r in res["sweep"]]
        runtimes = [r["wall_time_seconds"] for r in res["sweep"]]

        # Panel 1: JCT Reductions
        ax1.plot(x, y_mean, marker=m, color=c, linewidth=2, label=f"{label_base} - Mean JCT")
        ax1.plot(x, y_p95, marker=m, color=c, linewidth=1.5, linestyle="--", alpha=0.7, label=f"{label_base} - P95 JCT")

        # Panel 2: Simulation Wall Time
        ax2.plot(x, runtimes, marker=m, color=c, linewidth=2, label=f"{label_base} Runtime")

    ax1.axhline(0, color="white", linestyle=":", alpha=0.5)
    ax1.set_ylabel("JCT Reduction vs Baseline (%)", fontsize=11)
    ax1.set_title("Cluster Completion Time vs. Scoring Window Bound (150ms to 2400ms)", fontsize=13, pad=10)
    ax1.grid(True, alpha=0.15)
    ax1.legend(loc="best", fontsize=9)

    ax2.set_xlabel("Scoring Window Limit (ms)", fontsize=11)
    ax2.set_ylabel("Simulation Wall Time (s)", fontsize=11)
    ax2.set_title("Simulator Computational Cost vs. Window Size", fontsize=12, pad=8)
    ax2.grid(True, alpha=0.15)
    ax2.legend(loc="best", fontsize=9)

    plt.tight_layout()
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"\n[+] Saved sweep plot to: {plot_path}")


def main():
    parser = argparse.ArgumentParser(description="End-to-End Cluster JCT Sweep Across Scoring Windows")
    parser.add_argument("--workloads", nargs="+", default=["sample", "2000"], choices=["sample", "2000"],
                        help="Workloads to sweep")
    parser.add_argument("--windows", nargs="+", type=float, default=[150.0, 300.0, 600.0, 1200.0, 2400.0],
                        help="List of scoring windows in ms to sweep")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for placement")
    parser.add_argument("--num-jobs", type=int, default=None, help="Override job count for smoke testing")
    parser.add_argument("--output-dir", type=str, default=str(ROOT / "visualizations" / "lcm_scoring"),
                        help="Directory to save output figures and results")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for w in args.workloads:
        res = run_workload_window_sweep(w, args.windows, seed=args.seed, num_jobs=args.num_jobs)
        all_results.append(res)

    # Save JSON results
    json_path = out_dir / "jct_window_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"[+] Saved results manifest to: {json_path}")

    # Generate Figure
    plot_path = out_dir / "jct_window_sweep.png"
    plot_sweep(all_results, plot_path)


if __name__ == "__main__":
    main()
