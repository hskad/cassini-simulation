#!/usr/bin/env python
"""Run Cassini demos, checks, and comparisons from a Linux shell."""
import argparse
import copy
import csv
import hashlib
import json
import math
import random
import sys
import unittest
from dataclasses import asdict
from pathlib import Path

import numpy as np

from src.core.models import Cluster, Job, Link, Phase
from src.core.trace_loader import TraceLoader
from src.scheduler.simulator import Simulator

ROOT = Path(__file__).resolve().parent
PLOT_FILES = ("timeline.png", "bandwidth.png", "drift.png", "jct.png", "benchmark.png")
DATA_FILES = ("summary.csv", "summary.json", "parameters.json", "workload.json", "runs.json")
POLICY_FILES = ("completions.csv", "adjustments.csv", "link_totals.json", "routes.json",
                "phases.csv", "links.csv", "drift.csv", "schedules.json")


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Use a positive integer.")
    return number


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Use a finite positive number.")
    return number


def jitter_fraction(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number < 1:
        raise argparse.ArgumentTypeError("Compute jitter must be in [0, 1).")
    return number


def drift_fraction(value):
    number = float(value)
    if not math.isfinite(number) or not 0 < number < 0.5:
        raise argparse.ArgumentTypeError("Drift threshold must be in (0, 0.5).")
    return number


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()} for row in rows)


def build_workload(args):
    if args.command == "demo":
        count = 3 if args.scenario in ("multi-link", "dynamic") else 2
        compute, comm = (30, 70) if args.scenario == "partial" else (50, 50)
        jobs = [Job(chr(65 + i), chr(65 + i), [Phase("compute", compute, 0),
                    Phase("communicate", comm, args.capacity)],
                    arrival_time=100.0 * i if args.scenario == "dynamic" else 0.0,
                    total_iterations=args.iterations or 10) for i in range(count)]
        links = [Link("L1", args.capacity)]
        routes = {"L1": jobs}
        if args.scenario == "multi-link":
            links.append(Link("L2", args.capacity))
            routes = {"L1": jobs[:2], "L2": jobs[1:]}
        return jobs, Cluster([], links, routes), {"kind": "synthetic", "scenario": args.scenario}
    links = [Link(f"L{i+1}", args.capacity) for i in range(args.links)]
    if args.trace:
        path = Path(args.trace).resolve()
        metadata = json.loads(path.read_text(encoding="utf-8"))
        jobs = TraceLoader().load_trace(str(path), bandwidth_gbps=args.capacity, max_jobs=args.jobs)
        provenance = {"kind": metadata.get("provenance", {}).get("kind", "unverified"),
                      "trace_path": str(path), "description": metadata.get("description", "")}
        if args.iterations is not None:
            for job in jobs:
                job.total_iterations = args.iterations
            provenance["iteration_override"] = args.iterations
    elif args.catalog:
        jobs = TraceLoader().generate_synthetic_philly_workload(
            args.jobs, args.arrival_span, args.capacity, args.seed)
        if args.iterations is not None:
            for job in jobs:
                job.total_iterations = args.iterations
        provenance = {"kind": "synthetic", "profiles": "catalog with source limits"}
    else:
        rng = random.Random(args.seed)
        jobs = []
        for i in range(args.jobs):
            compute, comm = rng.choice([(30, 10), (40, 20), (60, 20)])
            jobs.append(Job(f"J{i+1:03}", "synthetic", [Phase("compute", compute, 0),
                Phase("communicate", comm, args.capacity)],
                arrival_time=round(rng.uniform(0, args.arrival_span), 3),
                total_iterations=args.iterations or rng.randint(5, 20)))
        provenance = {"kind": "synthetic", "profiles": "assumed phase durations"}
    if not jobs:
        raise ValueError("The workload contains no jobs.")
    routes = {link.link_id: [] for link in links}
    for index, job in enumerate(sorted(jobs, key=lambda job: (job.arrival_time, job.job_id))):
        routes[links[index % len(links)].link_id].append(job)
    return jobs, Cluster([], links, routes), provenance


def summarize(name, sim):
    times = [r["turnaround_time"] for r in sim.completed_jobs]
    return {"policy": name, "jobs": len(times), "mean_jct_ms": float(np.mean(times)),
            "p50_jct_ms": float(np.percentile(times, 50)),
            "p95_jct_ms": float(np.percentile(times, 95)),
            "mean_wait_ms": float(np.mean([r["wait_time"] for r in sim.completed_jobs])),
            "adjustments": len(sim.adjustments), "finish_time_ms": sim.current_time}


def prepare_output(out):
    """Replace only files that this utility creates."""
    out.mkdir(parents=True, exist_ok=True)
    for folder, names in [(out / "plots", PLOT_FILES), (out / "data", DATA_FILES)]:
        folder.mkdir(exist_ok=True)
        for name in names:
            (folder / name).unlink(missing_ok=True)
            # Remove stale files from the previous flat layout on a repeated run.
            (out / name).unlink(missing_ok=True)
    for base in [out, out / "data"]:
        for policy in ["uncoordinated", "static-shifts", "cassini"]:
            folder = base / policy
            for name in POLICY_FILES:
                (folder / name).unlink(missing_ok=True)
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
    write_json(out / "status.json", {"status": "running"})


def run_comparison(args):
    jobs, cluster, provenance = build_workload(args)
    snapshot = [asdict(job) for job in jobs]
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    input_routes = {job.job_id: [] for job in jobs}
    for link in cluster.links:
        for job in cluster.link_jobs.get(link.link_id, []):
            input_routes[job.job_id].append(link.link_id)
    out = Path(args.out).resolve()
    prepare_output(out)
    policies = [("uncoordinated", False, None)]
    if args.include_static:
        policies.append(("static-shifts", True, None))
    policies.append(("cassini", True, args.drift_threshold))
    simulations, summaries = {}, []
    print("Fluid network model | fixed routes | ms and Gbps")
    print("Workload source:", provenance["kind"])
    print("Score:", "full common period" if args.score_horizon is None
          else f"finite {args.score_horizon:g} ms window; no periodic guarantee")
    print("Shift solver:", args.solver)
    for name, use_cassini, threshold in policies:
        print(f"Running {name}...", flush=True)
        sim = Simulator(cluster, use_cassini=use_cassini, record_history=not args.no_history,
                        score_horizon=args.score_horizon, resolution=args.resolution,
                        compute_jitter=args.jitter, seed=args.seed, drift_threshold=threshold, solver=args.solver)
        for job in copy.deepcopy(jobs):
            sim.add_job_arrival(job)
        sim.run_simulation()
        if {jid: list(links) for jid, links in sim.job_to_links.items()} != input_routes:
            raise ValueError("The simulation changed the fixed input routes.")
        simulations[name] = sim
        summary = summarize(name, sim)
        summaries.append(summary)
        folder = out / "data" / name
        folder.mkdir(exist_ok=True)
        write_csv(folder / "completions.csv", sim.completed_jobs)
        write_csv(folder / "adjustments.csv", sim.adjustments)
        write_json(folder / "link_totals.json", sim.link_totals)
        write_json(folder / "routes.json", sim.job_to_links)
        if not args.no_history:
            write_csv(folder / "phases.csv", sim.phase_history)
            write_csv(folder / "links.csv", sim.link_history)
            write_csv(folder / "drift.csv", sim.drift_history)
            write_json(folder / "schedules.json", sim.schedule_history)
    write_json(out / "data" / "workload.json", snapshot)
    write_json(out / "data" / "parameters.json", {**vars(args), "workload_sha256": digest,
        "input_routes": input_routes,
        "route_sha256": hashlib.sha256(json.dumps(input_routes, sort_keys=True).encode()).hexdigest(),
        "provenance": provenance, "placement": "fixed routes; identical across policies",
        "network_model": "fluid max-min sharing with per-phase demand caps",
        "correction_action": "delay to the next nominal phase start; simulation assumption",
        "shift_solver": args.solver + " time grid", "units": {"time": "ms", "bandwidth": "Gbps"}})
    write_json(out / "data" / "summary.json", summaries)
    write_csv(out / "data" / "summary.csv", summaries)
    print(f"{'Policy':<18} {'Mean JCT (ms)':>15} {'P95 JCT (ms)':>15} {'Mean wait (ms)':>16} {'Adjustments':>12}")
    for row in summaries:
        print(f"{row['policy']:<18} {row['mean_jct_ms']:>15.3f} {row['p95_jct_ms']:>15.3f} "
              f"{row['mean_wait_ms']:>16.3f} {row['adjustments']:>12}")
    from src.visualization.comparison_plots import plot_comparison
    plot_comparison(simulations, out / "plots", args.plot_window, args.plot_jobs)
    write_json(out / "status.json", {"status": "complete", "workload_sha256": digest})
    print("Data:", out / "data")
    print("Plots:", out / "plots")
    return 0


def run_benchmark(args):
    from src.benchmark import run_benchmarks
    from src.visualization.benchmark_plots import plot_benchmarks
    out = Path(args.out).resolve()
    prepare_output(out)
    rows, workloads, runs = run_benchmarks(args.iterations, args.seeds)
    write_csv(out / "data" / "summary.csv", rows)
    write_json(out / "data" / "summary.json", rows)
    write_json(out / "data" / "workload.json", workloads)
    write_json(out / "data" / "runs.json", runs)
    sources = ["src/benchmark.py", "src/scheduler/simulator.py", "src/scheduler/evaluator.py",
               "src/math_engine/optimizer.py", "src/math_engine/graph.py", "src/core/models.py",
               "src/core/trace_loader.py", "data/models/real_models.json"]
    write_json(out / "data" / "parameters.json", {**vars(args),
        "source": "synthetic validation cases; no hardware performance claim",
        "profile_source": "VGG-16 timing from the catalog; other cases use synthetic profiles",
        "solver": "greedy", "resolution_ms": 1, "score_horizon_ms": None,
        "drift_threshold": 0.05, "jitter_fraction": 0.04,
        "seed_scope": "compute-jitter case; deterministic cases run once with seed 0",
        "checks": ["analytical completion times", "fixed identical routes", "matched compute noise",
                   "per-job network work", "per-link capacity and work", "all elapsed time charged"],
        "source_sha256": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
        "units": {"time": "ms", "bandwidth": "Gbps"}})
    plot_benchmarks(rows, out / "plots" / "benchmark.png")
    write_json(out / "status.json", {"status": "complete", "validated_runs": len(rows)})
    print(f"{'Case':<19} {'Seed':>4} {'Policy':<15} {'Mean JCT (ms)':>14} {'Reduction (%)':>14}")
    for row in rows:
        print(f"{row['case']:<19} {row['seed']:>4} {row['policy']:<15} "
              f"{row['mean_jct_ms']:>14.3f} {row['jct_reduction_percent']:>14.3f}")
    print("Negative reduction means longer completion time. All input cases are included.")
    print("Data:", out / "data")
    print("Plot:", out / "plots" / "benchmark.png")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Cassini phase scheduling checks and plots.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("test", help="Run all unit tests.")
    benchmark = commands.add_parser("benchmark", help="Run matched cases and analytical checks.")
    benchmark.add_argument("--iterations", type=positive_int, default=100)
    benchmark.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4],
                           help="Distinct seeds for compute jitter. Other cases run once.")
    benchmark.add_argument("--out", default=str(ROOT / "output" / "benchmark"))
    docs = commands.add_parser("docs", help="Rebuild README PNG plots and GIF animations.")
    docs.add_argument("--out", default=str(ROOT / "visualizations" / "readme"), help="Folder for the README images.")
    for command in ["demo", "experiment"]:
        p = commands.add_parser(command, help="Run a comparison and save plots.")
        p.add_argument("--capacity", type=positive_float, default=50.0, help="Link capacity in Gbps.")
        p.add_argument("--iterations", type=positive_int, help="Iterations per job. Overrides trace counts if set.")
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--jitter", type=jitter_fraction, default=0.0, help="Uniform compute jitter fraction, for example 0.04.")
        p.add_argument("--drift-threshold", type=drift_fraction, default=0.05, help="Fraction of nominal iteration time.")
        p.add_argument("--include-static", action="store_true", help="Also run shifts without drift correction.")
        p.add_argument("--score-horizon", type=positive_float, help="Explicit finite scoring window in ms.")
        p.add_argument("--solver", choices=["greedy", "exact"], default="greedy", help="Exact searches joint grid combinations, up to 20,000 trials.")
        p.add_argument("--resolution", type=positive_float, default=1.0, help="Shift search grid in ms.")
        p.add_argument("--plot-window", type=positive_float, default=600.0, help="Timeline and bandwidth plot window in ms.")
        p.add_argument("--plot-jobs", type=positive_int, default=8, help="Maximum jobs shown on timelines.")
        p.add_argument("--no-history", action="store_true", help="Save aggregate data and JCT plot only.")
        p.add_argument("--out", default=str(ROOT / "output" / command), help="Run folder with data/ and plots/. Existing result files are replaced.")
        if command == "demo":
            p.add_argument("--scenario", choices=["aligned", "partial", "multi-link", "dynamic"], default="aligned")
        else:
            p.add_argument("--jobs", "--num-jobs", type=positive_int, default=20)
            p.add_argument("--links", "--num-links", type=positive_int, default=4)
            p.add_argument("--arrival-span", type=positive_float, default=400.0)
            source = p.add_mutually_exclusive_group()
            source.add_argument("--trace", help="Workload JSON file. See its provenance metadata.")
            source.add_argument("--catalog", action="store_true", help="Generate synthetic arrivals with catalog profiles.")
    args = parser.parse_args(argv)
    if args.command == "test":
        sys.path.insert(0, str(ROOT / "tests"))
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT / "tests")))
        return 0 if result.wasSuccessful() else 1
    try:
        if args.command == "benchmark":
            return run_benchmark(args)
        if args.command == "docs":
            from src.visualization.readme_visuals import build_readme_visuals
            build_readme_visuals(args.out)
            return 0
        return run_comparison(args)
    except (ValueError, OSError, KeyError) as error:
        out = Path(args.out).resolve()
        if out.is_dir():
            write_json(out / "status.json", {"status": "failed", "error": str(error)})
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
