"""Test random window positions with fixed budgets and an independent reference."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from experiments.strided_lcm_experiment import FAMILIES, build_case
from experiments.strided_validation import (ADDITIONAL_SEEDS, PUBLISHED_SEEDS,
                                            evaluate_case, provenance)

# Fixed before running; independent of workload seeds; report all ten, not the best.
SAMPLING_SEEDS = (11, 23, 37, 51, 67, 79, 97, 113, 131, 149)
COMPARISONS = ("prefix-600", "strided-5", "random-5")


def method_rows(case, method):
    return [r for r in case["runs"] if
            (r["method"].startswith("random-5-") if method == "random-5" else r["method"] == method)]


def summary(cases, workload_seeds):
    selected = [c for c in cases if c["seed"] in workload_seeds and c["lcm_ms"] > 600]
    result = {}
    for method in COMPARISONS:
        # Average sampling trials within each workload case first, then weight cases equally.
        error, quality, times, error_change = [], [], [], []
        trials = []
        for case in selected:
            rows = method_rows(case, method)
            trials.extend(rows)
            error.append(statistics.mean(r["absolute_error_pp"] for r in rows))
            quality.append(statistics.mean(r["quality_gain_vs_prefix_pp"] for r in rows))
            times.append(statistics.mean(r["median_seconds"] for r in rows))
            error_change.append(error[-1] - case["runs"][0]["absolute_error_pp"])
        result[method] = {
            "workload_cases": len(selected), "sampling_trials": len(trials),
            "mean_absolute_error_pp": statistics.mean(error),
            "mean_quality_gain_vs_prefix_pp": statistics.mean(quality),
            "mean_optimizer_ms": 1000 * statistics.mean(times),
            "better_mean_quality_cases": sum(x > 1e-5 for x in quality),
            "equal_mean_quality_cases": sum(abs(x) <= 1e-5 for x in quality),
            "worse_mean_quality_cases": sum(x < -1e-5 for x in quality),
            "lower_mean_error_cases": sum(x < -1e-5 for x in error_change),
            "higher_mean_error_cases": sum(x > 1e-5 for x in error_change),
            "better_quality_trials": sum(r["quality_gain_vs_prefix_pp"] > 1e-5 for r in trials),
            "equal_quality_trials": sum(abs(r["quality_gain_vs_prefix_pp"]) <= 1e-5 for r in trials),
            "worse_quality_trials": sum(r["quality_gain_vs_prefix_pp"] < -1e-5 for r in trials),
            "worst_trial_quality_gain_pp": min(r["quality_gain_vs_prefix_pp"] for r in trials),
            "max_trial_gap_to_full_search_pp": max(r["gap_to_full_search_pp"] for r in trials),
        }
    seed_results = []
    for seed in SAMPLING_SEEDS:
        rows = [r for c in selected for r in c["runs"] if r["sampling_seed"] == seed]
        seed_results.append({"sampling_seed": seed,
                             "mean_absolute_error_pp": statistics.mean(r["absolute_error_pp"] for r in rows),
                             "mean_quality_gain_vs_prefix_pp": statistics.mean(r["quality_gain_vs_prefix_pp"] for r in rows)})
    return {"methods": result, "random_sampling_seed_results": seed_results}


def plot_results(cases, path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    families = list(FAMILIES)
    for method, colour in zip(COMPARISONS, ("#0072B2", "#009E73", "#D55E00")):
        for ax, metric, factor in zip(axes, ("absolute_error_pp", "quality_gain_vs_prefix_pp", "median_seconds"), (1, 1, 1000)):
            groups = [[statistics.mean(r[metric] for r in method_rows(c, method))*factor
                       for c in cases if c["family"] == family] for family in families]
            means = [statistics.mean(g) for g in groups]
            ax.errorbar(range(len(families)), means,
                        yerr=[[max(0, m-min(g)) for m,g in zip(means, groups)],
                              [max(0, max(g)-m) for m,g in zip(means, groups)]],
                        marker="o", capsize=2, label=method, color=colour)
    for ax, title, label in zip(axes, ("Score accuracy", "Selected-shift quality", "Selection cost"),
            ("Absolute score error (pp)", "Full-period gain vs prefix-600 (pp)", "Optimizer time (ms)")):
        ax.set_title(title)
        ax.set_ylabel(label)
        ax.set_xticks(range(len(families)), ["/".join(map(str,FAMILIES[f])) for f in families], rotation=45, ha="right")
        ax.set_xlabel("Job periods (ms)")
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    axes[1].axhline(0, color="black", linewidth=.7)
    fig.suptitle("Random window positions: the same 600 ms budget\nSix workload seeds; random method averages ten sampling trials per case; whiskers span case means", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "visualizations/lcm_scoring")
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("Repetitions must be positive.")
    metadata = provenance(("experiments/random_window_experiment.py",))
    seeds = (*PUBLISHED_SEEDS, *ADDITIONAL_SEEDS)
    cases = [evaluate_case(f, s, build_case(f,s), repetitions=args.repetitions,
                           sampling_seeds=SAMPLING_SEEDS) for f in FAMILIES for s in seeds]
    results = {"published": summary(cases, PUBLISHED_SEEDS),
               "additional": summary(cases, ADDITIONAL_SEEDS), "all": summary(cases, seeds)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figure = args.output_dir / "random_windows.png"
    plot_results(cases, figure)
    manifest = {**metadata, "workload_seeds": list(seeds), "sampling_seeds": list(SAMPLING_SEEDS),
                "published_seeds": list(PUBLISHED_SEEDS), "additional_seeds": list(ADDITIONAL_SEEDS),
                "budget_ms": 600, "num_windows": 5, "resolution_ms": 1,
                "repetitions": args.repetitions, "max_lcm_ms": 100000,
                "scope": "stationary offered traffic; no completion-time claim",
                "selection": "one fixed set of random windows per sampling seed; same windows for all candidate shifts",
                "assessment": "independent exact phase integration on [H,2H) for all plans; no best-seed selection",
                "aggregation": "average sampling trials within workload case, then average cases equally; summaries exclude H <= 600 controls",
                "timing": "median of three optimizer calls per plan; cloning and validation excluded",
                "cases": cases, "summary": results,
                "figures": {figure.name: hashlib.sha256(figure.read_bytes()).hexdigest()}}
    (args.output_dir / "random_window_results.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({k:v["methods"] for k,v in results.items()}, indent=2))


if __name__ == "__main__":
    main()
