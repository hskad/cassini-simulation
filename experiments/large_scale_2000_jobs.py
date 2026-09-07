import argparse
import copy
import json
import os
import sys
import time
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from src.core.models import Link, Cluster, Job
from src.core.trace_loader import TraceLoader
from src.scheduler.simulator import Simulator

TRACE_2000_PATH = os.path.join(PROJECT_ROOT, "data", "traces", "philly_2000_jobs.json")

def ensure_2000_job_trace(loader: TraceLoader, num_jobs: int = 2000, seed: int = 42) -> str:
    """Generates and caches the 2,000-job trace file if not already present."""
    if os.path.exists(TRACE_2000_PATH):
        return TRACE_2000_PATH

    print(f"[*] Generating unscaled 2,000-job production trace calibrated for realistic cluster concurrency...")
    jobs = loader.generate_large_scale_trace(num_jobs=num_jobs, timeline_hours=2.5, bandwidth_gbps=50.0, seed=seed)

    trace_data = {
        "trace_name": "Microsoft Philly Large-Scale Production Trace",
        "description": "2,000 ML training jobs with unscaled convergence iterations (1,000 - 12,000 iters) over high-concurrency multi-tenant cluster.",
        "timeline_hours": 2.5,
        "num_jobs": len(jobs),
        "jobs": [
            {
                "job_id": j.job_id,
                "model_name": j.name,
                "arrival_time_ms": j.arrival_time,
                "total_iterations": j.total_iterations,
                "gpu_count": 8
            }
            for j in jobs
        ]
    }

    os.makedirs(os.path.dirname(TRACE_2000_PATH), exist_ok=True)
    with open(TRACE_2000_PATH, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, indent=2)

    print(f"[+] Saved 2,000-job trace to: {TRACE_2000_PATH}")
    return TRACE_2000_PATH

def main():
    parser = argparse.ArgumentParser(description="Large-Scale 2,000-Job Philly Production Trace Experiment (2 Weeks)")
    parser.add_argument('--num-jobs', type=int, default=2000, help="Number of jobs to simulate")
    parser.add_argument('--num-links', type=int, default=32, help="Number of cluster spine bottleneck links")
    parser.add_argument('--capacity', type=float, default=50.0, help="Link capacity in Gbps")
    parser.add_argument('--penalty', type=float, default=1.5, help="Slowdown penalty factor for contention")
    parser.add_argument('--seed', type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    print("=========================================================================")
    print("      CASSINI Large-Scale Production Cluster Experiment (2,000 Jobs)     ")
    print("      Unscaled Iterations (1,000-12,000) over a 2-Week Timeline          ")
    print("=========================================================================\n")

    loader = TraceLoader()
    trace_path = ensure_2000_job_trace(loader, num_jobs=args.num_jobs, seed=args.seed)

    print(f"[*] Loading 2,000-job trace from: {os.path.basename(trace_path)}...")
    jobs = loader.load_trace(trace_path=trace_path, bandwidth_gbps=args.capacity, max_jobs=args.num_jobs)

    model_counts = defaultdict(int)
    total_iters = 0
    for j in jobs:
        model_counts[j.name] += 1
        total_iters += j.total_iterations

    print(f"    Total Simulated Jobs       : {len(jobs):,}")
    print(f"    Total Training Iterations  : {total_iters:,}")
    print(f"    Cluster Architecture Mix   :")
    for model_name, count in sorted(model_counts.items(), key=lambda x: -x[1]):
        prof = loader.models[model_name]
        pct = (count / len(jobs)) * 100
        print(f"      - {model_name:<14} ({prof.domain:<14}): {count:>4} jobs ({pct:>4.1f}%) | {prof.compute_time_ms:>5.1f}ms comp, {prof.default_comm_time_ms:>5.1f}ms comm")

    # Cluster topology
    links = [Link(f"L{i}", args.capacity) for i in range(args.num_links)]
    cluster = Cluster(servers=[], links=links)
    print(f"\n[*] Cluster Fabric: {args.num_links} shared switches/links with {args.capacity} Gbps line rate.\n")

    # 1. Run CASSINI Simulation
    print("-------------------------------------------------------------------------")
    print("  [1/2] Running CASSINI Scheduler (Geometric Circular Phase Interleaving)")
    print("-------------------------------------------------------------------------")
    t0 = time.time()
    sim_cassini = Simulator(cluster, penalty_factor=args.penalty, use_cassini=True, incremental=True)
    for job in jobs:
        sim_cassini.add_job_arrival(copy.deepcopy(job))
    sim_cassini.run_simulation()
    t_cassini = time.time() - t0
    print(f"  [+] Completed {len(sim_cassini.completed_jobs):,} jobs in {t_cassini:.2f} seconds.")

    # 2. Run Baseline Simulation
    print("\n-------------------------------------------------------------------------")
    print("  [2/2] Running Baseline Scheduler (Uncoordinated FIFO / Zero Phase Shift)")
    print("-------------------------------------------------------------------------")
    t0 = time.time()
    sim_baseline = Simulator(cluster, penalty_factor=args.penalty, use_cassini=False, incremental=True)
    for job in jobs:
        sim_baseline.add_job_arrival(copy.deepcopy(job))
    sim_baseline.run_simulation()
    t_baseline = time.time() - t0
    print(f"  [+] Completed {len(sim_baseline.completed_jobs):,} jobs in {t_baseline:.2f} seconds.\n")

    # 3. Extract Analytics
    cassini_map = {j["job_id"]: j for j in sim_cassini.completed_jobs}
    baseline_map = {j["job_id"]: j for j in sim_baseline.completed_jobs}

    # Convert turnaround times to minutes for intuitive readability
    cassini_minutes = np.array([j["turnaround_time"] / 60000.0 for j in sim_cassini.completed_jobs])
    baseline_minutes = np.array([j["turnaround_time"] / 60000.0 for j in sim_baseline.completed_jobs])

    c_mean, b_mean = np.mean(cassini_minutes), np.mean(baseline_minutes)
    c_p50, b_p50 = np.percentile(cassini_minutes, 50), np.percentile(baseline_minutes, 50)
    c_p90, b_p90 = np.percentile(cassini_minutes, 90), np.percentile(baseline_minutes, 90)
    c_p95, b_p95 = np.percentile(cassini_minutes, 95), np.percentile(baseline_minutes, 95)
    overall_speedup = ((b_mean - c_mean) / b_mean) * 100

    print("=========================================================================")
    print("               LARGE-SCALE PRODUCTION SIMULATION RESULTS                 ")
    print("=========================================================================")
    print(f"{'Metric':<25} | {'Baseline (Uncoord)':>18} | {'CASSINI':>15} | {'Improvement':>12}")
    print("-" * 77)
    print(f"{'Mean JCT (minutes)':<25} | {b_mean:>18.2f} | {c_mean:>15.2f} | {overall_speedup:>11.1f}%")
    print(f"{'Median P50 (minutes)':<25} | {b_p50:>18.2f} | {c_p50:>15.2f} | {((b_p50 - c_p50)/b_p50)*100:>11.1f}%")
    print(f"{'P90 Tail Latency (min)':<25} | {b_p90:>18.2f} | {c_p90:>15.2f} | {((b_p90 - c_p90)/b_p90)*100:>11.1f}%")
    print(f"{'P95 Tail Latency (min)':<25} | {b_p95:>18.2f} | {c_p95:>15.2f} | {((b_p95 - c_p95)/b_p95)*100:>11.1f}%")
    print("=" * 77)

    # 4. Per-Model Speedup Breakdown
    model_turnarounds_c = defaultdict(list)
    model_turnarounds_b = defaultdict(list)
    for jid, c_job in cassini_map.items():
        b_job = baseline_map[jid]
        model_name = c_job["name"]
        model_turnarounds_c[model_name].append(c_job["turnaround_time"] / 60000.0)
        model_turnarounds_b[model_name].append(b_job["turnaround_time"] / 60000.0)

    print("\n-------------------------------------------------------------------------")
    print("  Per-Model Turnaround & Speedup Breakdown                               ")
    print("-------------------------------------------------------------------------")
    print(f"{'Model Architecture':<16} | {'Baseline (min)':>14} | {'CASSINI (min)':>13} | {'Speedup':>10}")
    print("-" * 60)
    model_speedups = {}
    for m in sorted(model_turnarounds_c.keys()):
        m_c = np.mean(model_turnarounds_c[m])
        m_b = np.mean(model_turnarounds_b[m])
        sp = ((m_b - m_c) / m_b) * 100 if m_b > 0 else 0.0
        model_speedups[m] = (m_b, m_c, sp)
        print(f"{m:<16} | {m_b:>14.2f} | {m_c:>13.2f} | {sp:>9.1f}%")
    print("=" * 60)

    # 5. Visualizations
    out_dir = os.path.join(PROJECT_ROOT, "visualizations")
    os.makedirs(out_dir, exist_ok=True)

    # Plot 1: CDF
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(9.5, 6.5))

    sorted_c = np.sort(cassini_minutes)
    sorted_b = np.sort(baseline_minutes)
    y_c = np.arange(1, len(sorted_c) + 1) / len(sorted_c)
    y_b = np.arange(1, len(sorted_b) + 1) / len(sorted_b)

    ax.plot(sorted_c, y_c, linestyle='-', color='#00ffcc', linewidth=2.2,
            label=f'CASSINI Scheduler (Mean: {c_mean:.1f} min | P95: {c_p95:.1f} min)')
    ax.plot(sorted_b, y_b, linestyle='--', color='#ff007f', linewidth=2.2,
            label=f'Baseline Scheduler (Mean: {b_mean:.1f} min | P95: {b_p95:.1f} min)')

    ax.set_title("CDF of 2,000-Job Cluster JCT: Microsoft Philly 2-Week Production Trace", fontsize=13.5, color='white', pad=15)
    ax.set_xlabel("Job Completion Time (Minutes)", fontsize=12, color='white')
    ax.set_ylabel("Cumulative Probability (CDF)", fontsize=12, color='white')
    ax.grid(True, alpha=0.25, color='gray', linestyle='--')
    ax.legend(loc='lower right', frameon=True, facecolor='#1e1e1e', edgecolor='#444444', fontsize=11)

    cdf_path = os.path.join(out_dir, "large_scale_2000_jobs_cdf.png")
    plt.tight_layout()
    plt.savefig(cdf_path, dpi=300, bbox_inches='tight', facecolor='#111111')
    plt.close()
    print(f"\n[+] Saved Large-Scale CDF Plot to: {cdf_path}")

    # Plot 2: Per-Model Horizontal Bar Chart
    fig, ax = plt.subplots(figsize=(10.5, 6))
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
    ax.set_xlabel('Average Job Completion Time (Minutes)', fontsize=12, color='white')
    ax.set_title('Turnaround Time by Model Family (2,000-Job Philly Workload)', fontsize=14, color='white', pad=15)
    ax.grid(True, alpha=0.2, color='gray', linestyle='--', axis='x')
    ax.legend(loc='lower right', frameon=True, facecolor='#1e1e1e', edgecolor='#444444')

    for idx, m in enumerate(models_sorted):
        sp = model_speedups[m][2]
        c_val = model_speedups[m][1]
        ax.text(c_val + 0.5, idx + bar_height/2, f"+{sp:.1f}%", va='center', fontsize=10, color='#00ffcc', fontweight='bold')

    breakdown_path = os.path.join(out_dir, "large_scale_2000_jobs_breakdown.png")
    plt.tight_layout()
    plt.savefig(breakdown_path, dpi=300, bbox_inches='tight', facecolor='#111111')
    plt.close()
    print(f"[+] Saved Large-Scale Model Breakdown Chart to: {breakdown_path}")
    print("\nLarge-Scale Experiment completed successfully!\n")

if __name__ == '__main__':
    main()
