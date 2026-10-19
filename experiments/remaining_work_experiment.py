"""Test systematic errors in the benefit rule's remaining-work estimate."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from experiments.shift_policy_experiment import run_case, source_metadata
from src.math_engine.optimizer import DEFAULT_SCORE_WINDOW_MS

DEFAULT_SCALES = (0.5, 0.75, 1.0, 1.25, 1.5)
COLORS = {"macro": "#00ddbb", "sample": "#cf99ff", "short": "#69aaff",
          "2000": "#ffbd59", "10000": "#ff7399"}
LABELS = {"macro": "50 generated jobs", "sample": "60 illustrative jobs",
          "short": "200 short jobs", "2000": "2,000 synthetic jobs",
          "10000": "10,000 synthetic jobs"}


def run_sweep(workloads, seeds, scales, *, output_dir, num_jobs=None,
              min_gain_ms=0, score_window_ms=DEFAULT_SCORE_WINDOW_MS):
    """Repeat paired runs and check that estimate error never changes the input."""
    runs = []
    for name in workloads:
        for seed in seeds:
            reference = None
            for scale in scales:
                print(f"Running {name}, seed {seed}, estimate scale {scale:g} ...", flush=True)
                case_dir = Path(output_dir) / f"scale-{scale:g}"
                case_dir.mkdir(parents=True, exist_ok=True)
                results, completed = run_case(
                    name, seed, num_jobs=num_jobs, min_gain_ms=min_gain_ms,
                    score_window_ms=score_window_ms, output_dir=case_dir,
                    policies=("compatibility", "benefit"), remaining_work_scale=scale)
                identity = (results["compatibility"]["input_sha256"],
                            results["compatibility"]["placement_sha256"],
                            sorted(completed["compatibility"], key=lambda row: row["job_id"]))
                if reference is None:
                    reference = identity
                elif identity != reference:
                    raise ValueError("Estimate error changed input, placement, or vanilla completions.")
                runs.extend(results.values())
                print(f"  Benefit mean JCT reduction: {results['benefit']['mean_jct_gain_percent']:+.3f}%",
                      flush=True)
    # Compare each biased case with the accurate estimate for the same seed.
    accurate = {(r["workload"], r["seed"]): r["mean_jct_ms"] for r in runs
                if r["policy"] == "benefit" and r["remaining_work_scale"] == 1}
    for row in runs:
        if row["policy"] == "benefit":
            base = accurate[row["workload"], row["seed"]]
            row["mean_jct_change_vs_accurate_percent"] = 100 * (row["mean_jct_ms"] - base) / base
    return runs


def summarize(runs):
    """Average paired seed percentages, rather than taking a ratio of means."""
    summary = {}
    for name in dict.fromkeys(row["workload"] for row in runs):
        summary[name] = []
        for scale in sorted({r["remaining_work_scale"] for r in runs if r["workload"] == name}):
            rows = [r for r in runs if r["workload"] == name
                    and r["remaining_work_scale"] == scale and r["policy"] == "benefit"]
            record = {"remaining_work_scale": scale, "estimate_error_percent": 100 * (scale - 1),
                      "seeds": len(rows), "jobs": rows[0]["jobs"]}
            for metric in ("mean_jct_gain_percent", "p95_jct_gain_percent",
                           "mean_jct_change_vs_accurate_percent", "mean_wait_ms", "shift_changes"):
                values = [r[metric] for r in rows]
                record[metric] = statistics.mean(values)
                record["min_" + metric] = min(values)
                record["max_" + metric] = max(values)
            summary[name].append(record)
    return summary


def plot_results(summary, plot_dir):
    plt.style.use("dark_background")
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for ax, metric, title in zip(axes, ("mean_jct_gain_percent", "p95_jct_gain_percent"),
                                  ("Mean job completion time", "P95 job completion time")):
        for name, rows in summary.items():
            x = [r["estimate_error_percent"] for r in rows]
            label = f"{rows[0]['jobs']:,} {LABELS[name].split(' ', 1)[1]}"
            ax.plot(x, [r[metric] for r in rows], marker="o", color=COLORS[name], label=label)
            ax.fill_between(x, [r["min_" + metric] for r in rows],
                            [r["max_" + metric] for r in rows], color=COLORS[name], alpha=0.15)
        ax.axhline(0, color="white", linewidth=0.8, linestyle="--", alpha=0.7)
        ax.axvline(0, color="white", linewidth=0.7, linestyle=":", alpha=0.5)
        ax.set_ylabel("Reduction vs vanilla (%)")
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=0.15)
        ax.margins(y=0.12)
    axes[0].legend(fontsize=9, ncol=2)
    axes[-1].set_xlabel("Remaining-work estimate error (%)\nNegative = too low; positive = too high")
    axes[-1].set_xticks(sorted({r["estimate_error_percent"] for rows in summary.values() for r in rows}))
    fig.suptitle("Benefit rule with inaccurate estimates", fontsize=14)
    fig.text(0.5, 0.935, "Same actual jobs and routes; shaded bands show seed ranges", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    path = Path(plot_dir) / "remaining_work_sensitivity.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workloads", nargs="+", choices=tuple(LABELS),
                        default=["macro", "sample", "short", "2000"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 19, 42])
    parser.add_argument("--scales", nargs="+", type=float, default=list(DEFAULT_SCALES))
    parser.add_argument("--num-jobs", type=int)
    parser.add_argument("--min-gain-ms", type=float, default=0)
    parser.add_argument("--score-window-ms", type=float, default=DEFAULT_SCORE_WINDOW_MS)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/remaining-work")
    parser.add_argument("--plot-dir", type=Path, default=ROOT / "visualizations/remaining_work")
    args = parser.parse_args(argv)
    if any(not math.isfinite(s) or s <= 0 for s in args.scales) or 1 not in args.scales:
        parser.error("Scales must be finite, positive, and include 1.0 for the accurate reference")
    if any(len(set(values)) != len(values) for values in (args.scales, args.seeds, args.workloads)):
        parser.error("Scales, seeds, and workloads must not contain duplicates")
    if args.num_jobs is not None and args.num_jobs <= 0:
        parser.error("--num-jobs must be positive")
    if not math.isfinite(args.min_gain_ms) or args.min_gain_ms < 0:
        parser.error("--min-gain-ms must be finite and nonnegative")
    if not math.isfinite(args.score_window_ms) or args.score_window_ms < 1:
        parser.error("--score-window-ms must be finite and at least 1 ms")
    provenance = source_metadata(["experiments/remaining_work_experiment.py"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.plot_dir.mkdir(parents=True, exist_ok=True)
    runs = run_sweep(args.workloads, args.seeds, args.scales, output_dir=args.output_dir,
                     num_jobs=args.num_jobs, min_gain_ms=args.min_gain_ms,
                     score_window_ms=args.score_window_ms)
    summary = summarize(runs)
    figures = plot_results(summary, args.plot_dir)
    manifest = {
        **provenance, "workloads": args.workloads, "seeds": args.seeds,
        "scales": args.scales, "num_jobs": args.num_jobs, "min_gain_ms": args.min_gain_ms,
        "score_window_ms": args.score_window_ms, "penalty": 1.5, "resolution_ms": 1,
        "policies": ["compatibility", "benefit"], "shift_waits_charged": True,
        "error_model": "true remaining work multiplied at each decision; same factor for all jobs; actual work unchanged",
        "validation": "same input and placement hashes and identical vanilla completion records across scales",
        "aggregation": "mean of paired per-seed percentages; bands are min-max ranges, not confidence intervals",
        "baseline": "Cassini-based fast model; not full paper implementation",
        "runs": runs, "summary": summary, "figures": figures,
    }
    (args.plot_dir / "remaining_work_results.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("\nMean JCT reduction vs vanilla, by estimate error:")
    for name, rows in summary.items():
        print(f"  {name}: " + ", ".join(
            f"{r['estimate_error_percent']:+g}% error: {r['mean_jct_gain_percent']:+.3f}%"
            for r in rows))
    print(f"Plot and manifest: {args.plot_dir}")
    return manifest


if __name__ == "__main__":
    main()
