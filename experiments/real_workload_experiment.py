import argparse
import copy
import os
import random
import sys
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from src.core.models import Link, Cluster
from src.core.trace_loader import TraceLoader
from src.scheduler.simulator import Simulator

def main():
    parser = argparse.ArgumentParser(description="Real-World Production Workload Experiment (Microsoft Philly Trace)")
    parser.add_argument('--trace-path', type=str, default=None, help="Path to JSON cluster trace")
    parser.add_argument('--num-jobs', type=int, default=60, help="Number of jobs to simulate")
    parser.add_argument('--num-links', type=int, default=16, help="Number of bottleneck links in cluster")
    parser.add_argument('--capacity', type=float, default=50.0, help="Link capacity in Gbps")
    parser.add_argument('--penalty', type=float, default=1.5, help="Contention slowdown penalty factor")
    parser.add_argument('--synthetic', action='store_true', help="Use stochastic Philly generator instead of static trace")
    parser.add_argument('--seed', type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print("=================================================================")
    print("      CASSINI Real-World Cluster Workload Experiment             ")
    print("  Grounded in Microsoft Philly Traces & NSDI '24 Benchmarks      ")
    print("=================================================================\n")

    # 1. Load Trace and Models
    loader = TraceLoader()
    if args.synthetic:
        print(f"[*] Generating stochastic Philly workload ({args.num_jobs} jobs, seed={args.seed})...")
        jobs = loader.generate_synthetic_philly_workload(
            num_jobs=args.num_jobs,
            arrival_span_ms=1000.0,
            bandwidth_gbps=args.capacity / 2.0,
            seed=args.seed
        )
    else:
        trace_file = args.trace_path or TraceLoader.DEFAULT_TRACE_PATH
        print(f"[*] Loading empirical cluster trace from: {os.path.basename(trace_file)}...")
        jobs = loader.load_trace(
            trace_path=trace_file,
            bandwidth_gbps=args.capacity / 2.0,
            max_jobs=args.num_jobs
        )

    print(f"    Loaded {len(jobs)} jobs across {len(set(j.name for j in jobs))} model architectures:")
    model_counts = defaultdict(int)
    for j in jobs:
        model_counts[j.name] += 1
    for model_name, count in sorted(model_counts.items(), key=lambda x: -x[1]):
        prof = loader.models[model_name]
        print(f"      - {model_name:<14} ({prof.domain:<14}): {count:>2} jobs | Comp: {prof.compute_time_ms:>5.1f}ms, Comm: {prof.default_comm_time_ms:>5.1f}ms")

    # 2. Setup Cluster
    links = [Link(f"L{i}", args.capacity) for i in range(args.num_links)]
    cluster = Cluster(servers=[], links=links)
    print(f"\n[*] Cluster Setup: {args.num_links} shared links with {args.capacity} Gbps line rate capacity.\n")

    # 3. Execute CASSINI Simulation
    print("-----------------------------------------------------------------")
    print("  Running Simulation 1: CASSINI Scheduler (Network-Aware Phase Interleaving)")
    print("-----------------------------------------------------------------")
    sim_cassini = Simulator(cluster, penalty_factor=args.penalty, use_cassini=True)
    for job in jobs:
        sim_cassini.add_job_arrival(copy.deepcopy(job))
    sim_cassini.run_simulation()
    print(f"  [+] Completed {len(sim_cassini.completed_jobs)} jobs.")

    # 4. Execute Baseline Simulation
    print("\n-----------------------------------------------------------------")
    print("  Running Simulation 2: Baseline Uncoordinated Scheduler")
    print("-----------------------------------------------------------------")
    sim_baseline = Simulator(cluster, penalty_factor=args.penalty, use_cassini=False)
    for job in jobs:
        sim_baseline.add_job_arrival(copy.deepcopy(job))
    sim_baseline.run_simulation()
    print(f"  [+] Completed {len(sim_baseline.completed_jobs)} jobs.\n")

    # 5. Extract Analytics & Metrics
    cassini_map = {j["job_id"]: j for j in sim_cassini.completed_jobs}
    baseline_map = {j["job_id"]: j for j in sim_baseline.completed_jobs}

    cassini_turnarounds = [j["turnaround_time"] for j in sim_cassini.completed_jobs]
    baseline_turnarounds = [j["turnaround_time"] for j in sim_baseline.completed_jobs]

    c_mean, b_mean = np.mean(cassini_turnarounds), np.mean(baseline_turnarounds)
    c_p50, b_p50 = np.percentile(cassini_turnarounds, 50), np.percentile(baseline_turnarounds, 50)
    c_p90, b_p90 = np.percentile(cassini_turnarounds, 90), np.percentile(baseline_turnarounds, 90)
    c_p95, b_p95 = np.percentile(cassini_turnarounds, 95), np.percentile(baseline_turnarounds, 95)
    overall_speedup = ((b_mean - c_mean) / b_mean) * 100

    print("=================================================================")
    print("                     EXPERIMENT RESULTS SUMMARY                  ")
    print("=================================================================")
    print(f"{'Metric':<25} | {'Baseline':>12} | {'CASSINI':>12} | {'Improvement':>12}")
    print("-" * 69)
    print(f"{'Mean JCT (ms)':<25} | {b_mean:>12.2f} | {c_mean:>12.2f} | {overall_speedup:>11.1f}%")
    print(f"{'Median P50 JCT (ms)':<25} | {b_p50:>12.2f} | {c_p50:>12.2f} | {((b_p50 - c_p50)/b_p50)*100:>11.1f}%")
    print(f"{'P90 Tail Latency (ms)':<25} | {b_p90:>12.2f} | {c_p90:>12.2f} | {((b_p90 - c_p90)/b_p90)*100:>11.1f}%")
    print(f"{'P95 Tail Latency (ms)':<25} | {b_p95:>12.2f} | {c_p95:>12.2f} | {((b_p95 - c_p95)/b_p95)*100:>11.1f}%")
    print("=" * 69)

    # 6. Per-Model Speedup Breakdown
    model_turnarounds_c = defaultdict(list)
    model_turnarounds_b = defaultdict(list)
    for jid, c_job in cassini_map.items():
        b_job = baseline_map[jid]
        model_name = c_job["name"]
        model_turnarounds_c[model_name].append(c_job["turnaround_time"])
        model_turnarounds_b[model_name].append(b_job["turnaround_time"])

    print("\n-----------------------------------------------------------------")
    print("  Per-Model Speedup Analysis (Comm-Heavy vs Compute-Heavy)        ")
    print("-----------------------------------------------------------------")
    print(f"{'Model Architecture':<16} | {'Baseline (ms)':>13} | {'CASSINI (ms)':>12} | {'Speedup':>10}")
    print("-" * 59)
    model_speedups = {}
    for m in sorted(model_turnarounds_c.keys()):
        m_c = np.mean(model_turnarounds_c[m])
        m_b = np.mean(model_turnarounds_b[m])
        sp = ((m_b - m_c) / m_b) * 100
        model_speedups[m] = (m_b, m_c, sp)
        print(f"{m:<16} | {m_b:>13.1f} | {m_c:>12.1f} | {sp:>9.1f}%")
    print("=" * 59)

    # 7. Generate Visualizations
    out_dir = os.path.join(PROJECT_ROOT, "visualizations")
    os.makedirs(out_dir, exist_ok=True)

    # Plot 1: CDF of JCT
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(9, 6.5))

    sorted_c = np.sort(cassini_turnarounds)
    sorted_b = np.sort(baseline_turnarounds)
    y_c = np.arange(1, len(sorted_c) + 1) / len(sorted_c)
    y_b = np.arange(1, len(sorted_b) + 1) / len(sorted_b)

    ax.plot(sorted_c, y_c, marker='o', markersize=3.5, linestyle='-', color='#00ffcc', linewidth=2.0,
            label=f'CASSINI (Mean: {c_mean:.1f}ms | P95: {c_p95:.1f}ms)')
    ax.plot(sorted_b, y_b, marker='s', markersize=3.5, linestyle='--', color='#ff007f', linewidth=2.0,
            label=f'Baseline (Mean: {b_mean:.1f}ms | P95: {b_p95:.1f}ms)')

    ax.set_title("CDF of Job Completion Time: Microsoft Philly Production Trace", fontsize=14, color='white', pad=15)
    ax.set_xlabel("Job Completion Time (ms)", fontsize=12, color='white')
    ax.set_ylabel("Cumulative Probability (CDF)", fontsize=12, color='white')
    ax.grid(True, alpha=0.25, color='gray', linestyle='--')
    ax.legend(loc='lower right', frameon=True, facecolor='#1e1e1e', edgecolor='#444444', fontsize=10.5)

    cdf_path = os.path.join(out_dir, "real_workload_cdf.png")
    plt.tight_layout()
    plt.savefig(cdf_path, dpi=300, bbox_inches='tight', facecolor='#111111')
    plt.close()
    print(f"\n[+] Saved CDF Plot to: {cdf_path}")

    # Plot 2: Per-Model Speedup Bar Chart
    fig, ax = plt.subplots(figsize=(10, 5.5))
    models_sorted = sorted(model_speedups.keys(), key=lambda m: model_speedups[m][2], reverse=True)
    y_pos = np.arange(len(models_sorted))
    bar_height = 0.35

    b_vals = [model_speedups[m][0] for m in models_sorted]
    c_vals = [model_speedups[m][1] for m in models_sorted]

    rects1 = ax.barh(y_pos - bar_height/2, b_vals, bar_height, label='Baseline', color='#ff007f', alpha=0.85)
    rects2 = ax.barh(y_pos + bar_height/2, c_vals, bar_height, label='CASSINI', color='#00ffcc', alpha=0.85)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(models_sorted, fontsize=11, color='white')
    ax.invert_yaxis()
    ax.set_xlabel('Average Job Completion Time (ms)', fontsize=12, color='white')
    ax.set_title('Turnaround Time Comparison by Model Architecture (Philly Workload)', fontsize=14, color='white', pad=15)
    ax.grid(True, alpha=0.2, color='gray', linestyle='--', axis='x')
    ax.legend(loc='lower right', frameon=True, facecolor='#1e1e1e', edgecolor='#444444')

    # Add speedup annotations on bars
    for idx, m in enumerate(models_sorted):
        sp = model_speedups[m][2]
        c_val = model_speedups[m][1]
        ax.text(c_val + 20, idx + bar_height/2, f"+{sp:.1f}% speedup", va='center', fontsize=9.5, color='#00ffcc', fontweight='bold')

    breakdown_path = os.path.join(out_dir, "real_workload_model_breakdown.png")
    plt.tight_layout()
    plt.savefig(breakdown_path, dpi=300, bbox_inches='tight', facecolor='#111111')
    plt.close()
    print(f"[+] Saved Model Breakdown Chart to: {breakdown_path}")
    print("\nExperiment completed successfully!\n")

if __name__ == '__main__':
    main()
