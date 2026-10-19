"""Check bounded-window shift selection against exact full-period traffic."""
import argparse
import copy
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.analysis.periodic_traffic import periodic_traffic
from src.core.models import Job, Link, Phase
from src.math_engine.optimizer import get_score_window, optimize_link, score_link

FAMILIES = {
    "short_pair": (40, 60), "short_three": (80, 120, 160),
    "shared_pair": (100, 140), "near_shared_pair": (96, 104),
    "coprime_pair": (100, 101), "mixed_three": (80, 100, 140),
    "near_shared_three": (96, 100, 104),
}
COLORS = ("#00ddbb", "#69aaff", "#ffbd59", "#cf99ff")


def build_case(name, seed):
    rng = random.Random(seed)
    jobs = []
    for index, period in enumerate(FAMILIES[name]):
        comm = rng.randint(math.ceil(0.2 * period), math.floor(0.65 * period))
        compute = period - comm
        bandwidth = 50 if len(FAMILIES[name]) == 2 else rng.choice((25, 40, 50))
        if (seed + index) % 2 == 0:
            phases = [Phase("compute", compute // 2, 0),
                      Phase("communicate", comm // 2, bandwidth),
                      Phase("compute", compute - compute // 2, 0),
                      Phase("communicate", comm - comm // 2, bandwidth)]
        else:
            phases = [Phase("compute", compute, 0), Phase("communicate", comm, bandwidth)]
        jobs.append(Job(f"j{index}", name, phases))
    return jobs


def measure_selection(jobs, link, window, repetitions):
    timings, plans = [], []
    for _ in range(repetitions):
        selected = copy.deepcopy(jobs)
        begin = time.perf_counter()
        optimize_link(selected, link, score_window_ms=window)
        timings.append(time.perf_counter() - begin)
        plans.append([j.time_shift for j in selected])
    # Measure traced allocations in a separate call to keep tracing overhead
    # out of selection timings. Copies are created before tracing starts.
    memory_jobs = copy.deepcopy(jobs)
    tracemalloc.start()
    try:
        optimize_link(memory_jobs, link, score_window_ms=window)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    if any(plan != plans[0] for plan in plans) or [j.time_shift for j in memory_jobs] != plans[0]:
        raise ValueError("Repeated optimizer calls selected different shifts.")
    return selected, timings, peak


def evaluate_case(name, seed, jobs, windows, repetitions=3, max_lcm_ms=100000):
    if any(p.duration < 0 or not float(p.duration).is_integer() for j in jobs for p in j.phases):
        raise ValueError("This comparison requires integer nonnegative phase durations.")
    periods = [int(j.iteration_time) for j in jobs]
    if not periods or any(period <= 0 for period in periods):
        raise ValueError("This comparison requires positive job periods.")
    horizon = math.lcm(*periods)
    if horizon > max_lcm_ms:
        raise ValueError(f"Full LCM {horizon} ms exceeds the exact-reference limit {max_lcm_ms} ms.")
    link = Link("single-shared-link", 50)
    profiles = [asdict(job) for job in jobs]
    input_hash = hashlib.sha256(json.dumps(profiles, sort_keys=True).encode()).hexdigest()
    zero = copy.deepcopy(jobs)
    for job in zero:
        job.time_shift = 0
    zero_reference = periodic_traffic(zero, link.capacity, horizon, horizon)["score"]
    runs = []
    methods = [(f"prefix-{window}", window) for window in windows] + [("full-lcm", horizon)]
    for method, limit in methods:
        selected, timings, peak = measure_selection(jobs, link, limit, repetitions)
        actual_window = get_score_window(selected, score_window_ms=limit)
        estimated = score_link(selected, link, score_window_ms=limit)
        checked_prefix = periodic_traffic(selected, link.capacity, 0, actual_window)["score"]
        if not math.isclose(estimated, checked_prefix, abs_tol=2e-6):
            raise ValueError("Sampled score and independent phase-event score disagree.")
        # [H,2H) is later than, and disjoint from, every selection interval.
        validation = periodic_traffic(selected, link.capacity, horizon, horizon)
        zero_prefix = periodic_traffic(zero, link.capacity, 0, actual_window)["score"]
        runs.append({
            "method": method, "requested_window_ms": limit, "actual_window_ms": actual_window,
            "shifts_ms": {j.job_id: j.time_shift for j in selected},
            "estimated_score": estimated, "independent_selection_score": checked_prefix,
            "validation": validation, "score_optimism_pp": 100 * (estimated - validation["score"]),
            "estimated_gain_vs_zero_pp": 100 * (estimated - zero_prefix),
            "validated_gain_vs_zero_pp": 100 * (validation["score"] - zero_reference),
            "selection_seconds": timings, "median_selection_seconds": statistics.median(timings),
            "peak_traced_bytes": peak,
        })
    reference = runs[-1]["validation"]["score"]
    for row in runs:
        row["gap_to_full_window_search_pp"] = 100 * (reference - row["validation"]["score"])
    if [asdict(job) for job in jobs] != profiles:
        raise ValueError("Experiment modified its original jobs.")
    return {"case": name, "seed": seed, "profiles": profiles, "input_sha256": input_hash,
            "periods_ms": periods, "lcm_ms": horizon, "capacity_gbps": link.capacity,
            "validation_start_ms": horizon, "validation_duration_ms": horizon,
            "unshifted_reference_score": zero_reference,
            "dense_float32_profile_bytes_lower_bound": len(jobs) * horizon * 4, "runs": runs}


def growth_examples():
    primes = (101, 103, 107, 109, 113, 127, 131, 137)
    return [{"jobs": n, "periods_ms": list(primes[:n]), "lcm_ms": math.lcm(*primes[:n]),
             "dense_float32_profile_bytes_lower_bound": n * math.lcm(*primes[:n]) * 4}
            for n in range(1, len(primes) + 1)]


def provenance():
    paths = ["src/core/models.py", "src/math_engine/optimizer.py",
             "src/analysis/periodic_traffic.py", "experiments/lcm_scoring_experiment.py"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    working, canonical = {}, {}
    matches = True
    for path in paths:
        data = (ROOT / path).read_bytes()
        working[path] = hashlib.sha256(data).hexdigest()
        version = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True)
        canonical[path] = hashlib.sha256(version.stdout).hexdigest() if version.returncode == 0 else None
        matches &= version.returncode == 0 and data.replace(b"\r\n", b"\n") == version.stdout.replace(b"\r\n", b"\n")
    return {"source_commit": commit, "working_source_sha256": working, "git_blob_sha256": canonical,
            "source_matches_commit_after_lf_normalization": matches,
            "versions": {p: importlib.metadata.version(p) for p in ("numpy", "matplotlib")}}


def plots(cases, growth, plot_dir):
    plt.style.use("dark_background")
    names = list(dict.fromkeys(case["case"] for case in cases))
    labels = ["/".join(map(str, FAMILIES[name])) for name in names]
    methods = [r["method"] for r in cases[0]["runs"]]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for ax, metric, title in zip(axes, ("score_optimism_pp", "gap_to_full_window_search_pp"),
                                ("Estimated score minus full-period score", "Full-window reference score minus selected score")):
        for index, method in enumerate(methods):
            values = [[r[metric] for c in cases if c["case"] == name
                       for r in c["runs"] if r["method"] == method] for name in names]
            means = [statistics.mean(v) for v in values]
            ax.errorbar(range(len(names)), means,
                        yerr=[[max(0, avg - min(v)) for avg, v in zip(means, values)],
                              [max(0, max(v) - avg) for avg, v in zip(means, values)]],
                        marker="o", capsize=3, label=method, color=COLORS[index % len(COLORS)])
        ax.axhline(0, color="white", linewidth=0.8, alpha=0.6)
        ax.set_ylabel("Score difference (percentage points)")
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=0.15)
    axes[0].legend(ncol=2, fontsize=9)
    axes[-1].set_xticks(range(len(names)), labels, rotation=20)
    axes[-1].set_xlabel("Job periods (ms)")
    fig.suptitle("LCM scoring diagnostic: means and min-max seed ranges")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    error_path = plot_dir / "lcm_score_error.png"
    fig.savefig(error_path, dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    axes[0].semilogy([r["jobs"] for r in growth], [r["lcm_ms"] for r in growth], "o-", color=COLORS[0])
    axes[0].set_xlabel("Number of distinct prime periods")
    axes[0].set_ylabel("Full LCM (ms, logarithmic scale)")
    axes[0].set_title("Analytical growth; no full arrays allocated")
    for ax, metric, factor, ylabel in ((axes[1], "median_selection_seconds", 1000, "Selection time (ms, log scale)"),
                                       (axes[2], "peak_traced_bytes", 1 / 1024, "Peak traced allocation (KiB, log scale)")):
        for method, color in ((methods[0], COLORS[0]), ("full-lcm", COLORS[-1])):
            values = [statistics.median(r[metric] for c in cases if c["case"] == name
                                        for r in c["runs"] if r["method"] == method) * factor for name in names]
            ax.semilogy(range(len(names)), values, "o-", color=color, label=method)
        ax.set_xticks(range(len(names)), labels, rotation=40, ha="right", fontsize=8)
        ax.set_xlabel("Job periods (ms)")
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=9)
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.suptitle("LCM growth and measured optimizer cost; medians across seeds")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    cost_path = plot_dir / "lcm_cost.png"
    fig.savefig(cost_path, dpi=180)
    plt.close(fig)
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (error_path, cost_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=tuple(FAMILIES), default=list(FAMILIES))
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 19, 42])
    parser.add_argument("--windows-ms", nargs="+", type=int, default=[600, 1200, 6000])
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-lcm-ms", type=int, default=100000)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/lcm-scoring")
    parser.add_argument("--plot-dir", type=Path, default=ROOT / "visualizations/lcm_scoring")
    args = parser.parse_args(argv)
    if args.repetitions < 1 or args.max_lcm_ms < 1 or any(w < 1 for w in args.windows_ms):
        parser.error("Repetitions, LCM limit, and windows must be positive")
    if any(len(set(v)) != len(v) for v in (args.cases, args.seeds, args.windows_ms)):
        parser.error("Cases, seeds, and windows must not contain duplicates")
    metadata = provenance()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.plot_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for name in args.cases:
        for seed in args.seeds:
            print(f"Running {name}, seed {seed} ...", flush=True)
            case = evaluate_case(name, seed, build_case(name, seed), args.windows_ms,
                                 args.repetitions, args.max_lcm_ms)
            cases.append(case)
            (args.output_dir / f"{name}-seed{seed}.json").write_text(
                json.dumps(case, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    growth = growth_examples()
    figures = plots(cases, growth, args.plot_dir)
    manifest = {**metadata, "seeds": args.seeds, "windows_ms": args.windows_ms,
                "repetitions": args.repetitions, "max_lcm_ms": args.max_lcm_ms, "resolution_ms": 1,
                "reference": "exact phase-event integration on [H,2H); H is the full LCM",
                "search": "unchanged baseline optimizer; first job at zero; exhaustive 1 ms two-job shifts; ordered greedy 2 ms steps for three jobs",
                "timing": "optimizer only; clones, scoring checks, and reference integration excluded",
                "memory": "peak traced allocation in separate untimed optimizer call; not process RSS",
                "scope": "stationary offered traffic; no arrivals, queues, drift, completion times, or shift-wait benefit claims",
                "cases": cases, "analytical_growth": growth, "figures": figures}
    (args.plot_dir / "lcm_results.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Saved {len(cases)} cases and {sum(len(c['runs']) for c in cases)} shift plans.")
    print(f"Plots and source manifest: {args.plot_dir}")
    return manifest


if __name__ == "__main__":
    main()
