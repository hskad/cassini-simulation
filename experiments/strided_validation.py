"""Compare bounded shift searches using one independent full-period metric."""
import argparse
import copy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experiments.strided_lcm_experiment import FAMILIES, build_case
from src.analysis.periodic_traffic import periodic_traffic
from src.core.models import Link
from src.math_engine.optimizer import get_strided_windows, optimize_link, score_link

METHODS = (("prefix-600", 600, 1), ("strided-3", 600, 3),
           ("strided-5", 600, 5), ("prefix-1200", 1200, 1))
PUBLISHED_SEEDS = (7, 19, 42)
ADDITIONAL_SEEDS = (101, 202, 303)


def evaluate_case(name, seed, jobs, *, repetitions=3, max_lcm_ms=100000,
                  sampling_seeds=()):
    """Select plans, then evaluate every plan with exact integration on [H,2H)."""
    if repetitions < 1:
        raise ValueError("Repetitions must be positive.")
    if not jobs or any(j.iteration_time <= 0 or
                       any(p.duration < 0 or not float(p.duration).is_integer()
                           for p in j.phases) for j in jobs):
        raise ValueError("Reference comparison requires positive integer periods and phases.")
    horizon = math.lcm(*(int(j.iteration_time) for j in jobs))
    if horizon > max_lcm_ms:
        raise ValueError("Full LCM exceeds the exact-reference limit.")
    profiles = [asdict(j) for j in jobs]
    link = Link("shared", 50)
    zero = copy.deepcopy(jobs)
    for j in zero:
        j.time_shift = 0
    zero_score = periodic_traffic(zero, 50, horizon, horizon)["score"]
    reference = copy.deepcopy(zero)
    optimize_link(reference, link, score_window_ms=horizon)
    reference_score = periodic_traffic(reference, 50, horizon, horizon)["score"]
    runs = []
    methods = [(*spec, None) for spec in METHODS]
    methods.extend((f"random-5-{s}", 600, 5, s) for s in sampling_seeds)
    for method, budget, count, sampling_seed in methods:
        sampling = {"sampling_seed": sampling_seed} if sampling_seed is not None else {}
        timings, plans = [], []
        for _ in range(repetitions):
            selected = copy.deepcopy(zero)
            start = time.perf_counter()
            optimize_link(selected, link, score_window_ms=budget, num_windows=count, **sampling)
            timings.append(time.perf_counter() - start)
            plans.append([j.time_shift for j in selected])
        if any(p != plans[0] for p in plans):
            raise ValueError("Repeated searches selected different plans.")
        windows = get_strided_windows(selected, score_window_ms=budget, num_windows=count, **sampling)
        duration = sum(d for _, d in windows)
        if duration > budget or any(s < 0 or d <= 0 or s+d > horizon for s, d in windows):
            raise ValueError("Sampling windows exceed their budget or common period.")
        if any(a+d > b for (a, d), (b, _) in zip(windows, windows[1:])):
            raise ValueError("Sampling windows overlap.")
        estimated = score_link(selected, link, score_window_ms=budget, num_windows=count, **sampling)
        checked = sum(periodic_traffic(selected, 50, s, d)["score"] * d
                      for s, d in windows) / duration
        if not math.isclose(estimated, checked, abs_tol=2e-6):
            raise ValueError("Sampled score disagrees with independent window integration.")
        validation = periodic_traffic(selected, 50, horizon, horizon)
        optimism = 100 * (estimated - validation["score"])
        runs.append({
            "method": method, "budget_ms": budget, "num_windows": count,
            "sampling_seed": sampling_seed,
            "actual_samples": int(duration), "windows_ms": windows,
            "shifts_ms": {j.job_id: j.time_shift for j in selected},
            "estimated_score": estimated, "independent_sample_score": checked,
            "validation": validation, "score_optimism_pp": optimism,
            "absolute_error_pp": abs(optimism),
            "gain_vs_zero_pp": 100 * (validation["score"] - zero_score),
            "gap_to_full_search_pp": 100 * (reference_score - validation["score"]),
            "selection_seconds": timings, "median_seconds": statistics.median(timings),
        })
    prefix_score = runs[0]["validation"]["score"]
    for row in runs:
        row["quality_gain_vs_prefix_pp"] = 100 * (row["validation"]["score"] - prefix_score)
    if profiles != [asdict(j) for j in jobs]:
        raise ValueError("Evaluation mutated the input jobs.")
    return {"family": name, "seed": seed, "profiles": profiles,
            "input_sha256": hashlib.sha256(json.dumps(profiles, sort_keys=True).encode()).hexdigest(),
            "lcm_ms": horizon, "capacity_gbps": 50,
            "validation_interval_ms": [horizon, 2*horizon],
            "zero_shift_score": zero_score, "full_search_score": reference_score,
            "full_search_shifts_ms": {j.job_id: j.time_shift for j in reference}, "runs": runs}


def summarize(cases, seeds):
    # Long-period cases isolate behaviour when a 600 ms budget truncates the LCM.
    selected = [c for c in cases if c["seed"] in seeds and c["lcm_ms"] > 600]
    result = {}
    for method, _, _ in METHODS:
        rows = [r for c in selected for r in c["runs"] if r["method"] == method]
        error_changes = [r["absolute_error_pp"] - c["runs"][0]["absolute_error_pp"]
                         for c in selected for r in c["runs"] if r["method"] == method]
        result[method] = {
            "cases": len(rows),
            "mean_absolute_error_pp": statistics.mean(r["absolute_error_pp"] for r in rows),
            "mean_signed_optimism_pp": statistics.mean(r["score_optimism_pp"] for r in rows),
            "mean_quality_gain_vs_prefix_pp": statistics.mean(r["quality_gain_vs_prefix_pp"] for r in rows),
            "max_gap_to_full_search_pp": max(r["gap_to_full_search_pp"] for r in rows),
            "lower_error_cases": sum(x < -1e-5 for x in error_changes),
            "equal_error_cases": sum(abs(x) <= 1e-5 for x in error_changes),
            "higher_error_cases": sum(x > 1e-5 for x in error_changes),
            "better_quality_cases": sum(r["quality_gain_vs_prefix_pp"] > 1e-5 for r in rows),
            "equal_quality_cases": sum(abs(r["quality_gain_vs_prefix_pp"]) <= 1e-5 for r in rows),
            "worse_quality_cases": sum(r["quality_gain_vs_prefix_pp"] < -1e-5 for r in rows),
        }
    return result


def provenance(extra_sources=()):
    paths = ["experiments/strided_validation.py", "experiments/strided_lcm_experiment.py",
             "src/math_engine/optimizer.py", "src/analysis/periodic_traffic.py", "src/core/models.py"]
    paths.extend(extra_sources)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    records = {}
    for path in paths:
        working = (ROOT / path).read_bytes()
        committed = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
        records[path] = {
            "working_sha256": hashlib.sha256(working).hexdigest(),
            "git_blob_sha256": hashlib.sha256(committed).hexdigest(),
            "matches_after_lf_normalization": working.replace(b"\r\n", b"\n") == committed.replace(b"\r\n", b"\n")}
    if not all(r["matches_after_lf_normalization"] for r in records.values()):
        raise ValueError("Commit experiment sources before publishing results.")
    return {"source_commit": commit, "source_files": records,
            "versions": {"python": sys.version, "numpy": np.__version__, "matplotlib": matplotlib.__version__}}


def plot_results(cases, path):
    families = list(FAMILIES)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    colours = ("#0072B2", "#E69F00", "#009E73", "#CC79A7")
    for (method, _, _), colour in zip(METHODS, colours):
        for ax, metric, scale in zip(axes, ("absolute_error_pp", "quality_gain_vs_prefix_pp", "median_seconds"), (1, 1, 1000)):
            values = [[r[metric]*scale for c in cases if c["family"] == family
                       for r in c["runs"] if r["method"] == method] for family in families]
            means = [statistics.mean(v) for v in values]
            ax.errorbar(range(len(families)), means,
                        yerr=[[max(0, avg-min(v)) for avg, v in zip(means, values)],
                              [max(0, max(v)-avg) for avg, v in zip(means, values)]],
                        marker="o", capsize=2, label=method, color=colour)
    for ax, title, ylabel in zip(axes,
            ("Score accuracy", "Selected-shift quality", "Selection cost"),
            ("Absolute score error (percentage points)", "Full-period gain vs prefix-600 (pp)", "Optimizer time (ms)")):
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.set_xticks(range(len(families)), ["/".join(map(str, FAMILIES[f])) for f in families], rotation=45, ha="right")
        ax.set_xlabel("Job periods (ms)")
        ax.grid(alpha=.2)
    axes[1].axhline(0, color="black", linewidth=.7)
    axes[0].legend(fontsize=8)
    fig.suptitle("One independent full-period check for all methods\nSix seeds; points show means and whiskers show observed ranges", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "visualizations/lcm_scoring")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-lcm-ms", type=int, default=100000)
    args = parser.parse_args()
    if args.repetitions < 1 or args.max_lcm_ms < 1:
        parser.error("Repetitions and reference limit must be positive.")
    metadata = provenance()
    seeds = (*PUBLISHED_SEEDS, *ADDITIONAL_SEEDS)
    cases = [evaluate_case(name, seed, build_case(name, seed), repetitions=args.repetitions,
                           max_lcm_ms=args.max_lcm_ms) for name in FAMILIES for seed in seeds]
    summary = {"published": summarize(cases, PUBLISHED_SEEDS),
               "additional": summarize(cases, ADDITIONAL_SEEDS), "all": summarize(cases, seeds)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figure = args.output_dir / "strided_validation.png"
    plot_results(cases, figure)
    manifest = {**metadata, "seeds": list(seeds), "published_seeds": list(PUBLISHED_SEEDS),
                "additional_seeds": list(ADDITIONAL_SEEDS), "resolution_ms": 1,
                "repetitions": args.repetitions, "max_lcm_ms": args.max_lcm_ms,
                "scope": "stationary offered traffic; full-period integration; no JCT claims",
                "reference": "same ordered greedy search on full LCM; not a global optimum for three jobs",
                "timing": "median repeated optimizer calls; cloning and validation excluded",
                "summary_scope": "cases with LCM above 600 ms; short cases remain in raw records and plots",
                "cases": cases, "summary": summary,
                "figures": {figure.name: hashlib.sha256(figure.read_bytes()).hexdigest()}}
    (args.output_dir / "strided_validation_results.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
