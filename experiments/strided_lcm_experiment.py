"""
Evaluate Strided Multi-Window Sampling against Single Contiguous Windows.
Tests whether distributing the same 600 ms sampling budget across multiple
strided windows cuts score optimism across period families.
"""

import copy
import hashlib
import json
import math
import random
import statistics
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

from src.analysis.periodic_traffic import periodic_traffic
from src.core.models import Job, Link, Phase
from src.math_engine.optimizer import optimize_link, score_link, get_strided_windows

FAMILIES = {
    "short_pair": (40, 60),
    "short_three": (80, 120, 160),
    "shared_pair": (100, 140),
    "near_shared_pair": (96, 104),
    "coprime_pair": (100, 101),
    "mixed_three": (80, 100, 140),
    "near_shared_three": (96, 100, 104),
}


def build_case(name: str, seed: int) -> List[Job]:
    rng = random.Random(seed)
    jobs = []
    for index, period in enumerate(FAMILIES[name]):
        comm = rng.randint(math.ceil(0.2 * period), math.floor(0.65 * period))
        compute = period - comm
        bandwidth = 50 if len(FAMILIES[name]) == 2 else rng.choice((25, 40, 50))
        if (seed + index) % 2 == 0:
            phases = [
                Phase("compute", compute // 2, 0),
                Phase("communicate", comm // 2, bandwidth),
                Phase("compute", compute - compute // 2, 0),
                Phase("communicate", comm - comm // 2, bandwidth)
            ]
        else:
            phases = [Phase("compute", compute, 0), Phase("communicate", comm, bandwidth)]
        jobs.append(Job(f"j{index}", name, phases))
    return jobs


def run_experiment(seeds=(7, 19, 42)):
    link = Link("single-shared-link", 50.0)
    methods = [
        ("prefix-600 (1x600ms)", 600.0, 1),
        ("strided-3x200 (600ms)", 600.0, 3),
        ("strided-5x120 (600ms)", 600.0, 5),
        ("prefix-1200 (1x1200ms)", 1200.0, 1),
    ]

    all_results = []

    for name, periods in FAMILIES.items():
        horizon = math.lcm(*periods)
        print(f"\nEvaluating family: {name} (Periods={periods}, LCM={horizon}ms)")

        family_data = {
            "family": name,
            "periods": periods,
            "lcm": horizon,
            "methods": {m[0]: {"optimism": [], "gap": [], "wall_time_ms": []} for m in methods}
        }

        for seed in seeds:
            jobs = build_case(name, seed)

            # Full LCM reference search
            full_jobs = copy.deepcopy(jobs)
            optimize_link(full_jobs, link, score_window_ms=horizon, num_windows=1)
            full_ref_score = periodic_traffic(full_jobs, link.capacity, horizon, horizon)["score"]

            for m_label, win_budget, n_win in methods:
                test_jobs = copy.deepcopy(jobs)
                t0 = time.perf_counter()
                optimize_link(test_jobs, link, score_window_ms=win_budget, num_windows=n_win)
                t_elapsed = (time.perf_counter() - t0) * 1000.0

                # Estimated score by the optimizer
                estimated_score = score_link(test_jobs, link, score_window_ms=win_budget, num_windows=n_win)

                # Ground truth score over the disjoint full period [H, 2H)
                later_score = periodic_traffic(test_jobs, link.capacity, horizon, horizon)["score"]

                # Score optimism: estimated - actual later score (percentage points)
                optimism = (estimated_score - later_score) * 100.0
                # Gap to full reference search: full_ref - later_score (percentage points)
                gap = (full_ref_score - later_score) * 100.0

                family_data["methods"][m_label]["optimism"].append(optimism)
                family_data["methods"][m_label]["gap"].append(gap)
                family_data["methods"][m_label]["wall_time_ms"].append(t_elapsed)

        # Average across seeds
        print(f"{'Method':<25} | {'Optimism (pp)':<15} | {'Ref Gap (pp)':<15} | {'Runtime (ms)':<12}")
        print("-" * 75)
        summary_methods = {}
        for m_label, stats in family_data["methods"].items():
            mean_opt = float(np.mean(stats["optimism"]))
            mean_gap = float(np.mean(stats["gap"]))
            mean_time = float(np.mean(stats["wall_time_ms"]))
            summary_methods[m_label] = {
                "mean_optimism": mean_opt,
                "mean_gap": mean_gap,
                "mean_wall_time_ms": mean_time,
            }
            print(f"{m_label:<25} | {mean_opt:>+14.3f}% | {mean_gap:>+14.3f}% | {mean_time:>10.2f}ms")

        family_data["summary"] = summary_methods
        all_results.append(family_data)

    out_dir = ROOT / "visualizations" / "lcm_scoring"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "strided_sampling_results.json"
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[+] Saved strided results to: {json_path}")

    # Plot comparison
    plot_path = out_dir / "strided_vs_prefix_comparison.png"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    families_with_large_lcm = [f for f in all_results if f["lcm"] > 600]
    fam_names = [f["family"] for f in families_with_large_lcm]
    x = np.arange(len(fam_names))
    width = 0.2

    # Left plot: Score Optimism Error
    m_keys = [
        ("prefix-600 (1x600ms)", "#ff7f0e", "Prefix 1x600ms"),
        ("strided-3x200 (600ms)", "#2ca02c", "Strided 3x200ms (Same Budget)"),
        ("strided-5x120 (600ms)", "#1f77b4", "Strided 5x120ms (Same Budget)"),
        ("prefix-1200 (1x1200ms)", "#9467bd", "Prefix 1x1200ms (2x Budget)"),
    ]

    for i, (key, color, label) in enumerate(m_keys):
        opts = [f["summary"][key]["mean_optimism"] for f in families_with_large_lcm]
        ax1.bar(x + (i - 1.5) * width, opts, width, label=label, color=color, alpha=0.9)

    ax1.set_ylabel("Score Optimism Error (% points)", fontsize=11, fontweight="bold")
    ax1.set_title("Score Optimism by Method (Lower is More Accurate)", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels([f.replace("_", "\n") for f in fam_names], fontsize=9)
    ax1.grid(axis="y", linestyle="--", alpha=0.5)
    ax1.legend(fontsize=9)

    # Right plot: Runtime Comparison
    for i, (key, color, label) in enumerate(m_keys):
        runtimes = [f["summary"][key]["mean_wall_time_ms"] for f in families_with_large_lcm]
        ax2.bar(x + (i - 1.5) * width, runtimes, width, label=label, color=color, alpha=0.9)

    ax2.set_ylabel("Optimizer Wall Time (ms)", fontsize=11, fontweight="bold")
    ax2.set_title("Optimizer Wall Time Comparison", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels([f.replace("_", "\n") for f in fam_names], fontsize=9)
    ax2.grid(axis="y", linestyle="--", alpha=0.5)
    ax2.legend(fontsize=9)

    plt.tight_layout()
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"[+] Saved comparison plot to: {plot_path}")


if __name__ == "__main__":
    run_experiment()
