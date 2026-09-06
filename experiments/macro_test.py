import argparse
import copy
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from src.core.models import Phase, Job, Link, Cluster
from src.scheduler.simulator import Simulator

def main():
    parser = argparse.ArgumentParser(description="Macro-Test (Figure 9 Replica)")
    parser.add_argument('--num-jobs', type=int, default=50, help="Number of jobs to simulate")
    parser.add_argument('--num-links', type=int, default=16, help="Number of cluster links")
    parser.add_argument('--capacity', type=float, default=50.0, help="Link capacity (Gbps)")
    parser.add_argument('--penalty', type=float, default=1.5, help="Slowdown penalty factor")
    parser.add_argument('--seed', type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)

    # 1. Generate Cluster
    links = [Link(f"L{i}", args.capacity) for i in range(args.num_links)]
    cluster = Cluster(servers=[], links=links)

    # 2. Generate Jobs
    jobs = []
    for i in range(args.num_jobs):
        comp_time = float(random.choice([25, 35, 45, 55]))
        comm_time = float(random.choice([15, 20, 25]))
        demand = float(random.choice([40, 50]))
        arrival = float(random.randint(0, 400))
        iters = random.randint(5, 25)
        
        job = Job(job_id=f"J{i}", name=f"Job_{i}", phases=[
            Phase("compute", comp_time, 0.0),
            Phase("communicate", comm_time, demand)
        ], arrival_time=arrival, total_iterations=iters)
        jobs.append(job)

    # We need to run them on two independent simulators
    print(f"--- Running CASSINI Scheduler (Optimized) ---", flush=True)
    sim_cassini = Simulator(cluster, penalty_factor=args.penalty, use_cassini=True)
    for job in jobs:
        sim_cassini.add_job_arrival(copy.deepcopy(job))
    sim_cassini.run_simulation()
    
    print(f"--- Running Random Scheduler (Baseline) ---", flush=True)
    sim_random = Simulator(cluster, penalty_factor=args.penalty, use_cassini=False)
    for job in jobs:
        sim_random.add_job_arrival(copy.deepcopy(job))
    sim_random.run_simulation()

    # 3. Extract Turnaround Times
    cassini_times = sorted([j["turnaround_time"] for j in sim_cassini.completed_jobs])
    random_times = sorted([j["turnaround_time"] for j in sim_random.completed_jobs])

    # 4. Plot CDF
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(9, 6.5))

    y_cassini = np.arange(1, len(cassini_times) + 1) / len(cassini_times)
    y_random = np.arange(1, len(random_times) + 1) / len(random_times)

    ax.plot(cassini_times, y_cassini, marker='o', markersize=4, linestyle='-', color='#00ffcc', label=f'CASSINI Scheduler (Mean: {np.mean(cassini_times):.1f}ms)')
    ax.plot(random_times, y_random, marker='s', markersize=4, linestyle='--', color='#ff007f', label=f'Random Scheduler (Mean: {np.mean(random_times):.1f}ms)')

    ax.set_title("CDF of Job Completion Times (Figure 9 Replica)", fontsize=15, color='white', pad=15)
    ax.set_xlabel("Job Completion Time (ms)", fontsize=12, color='white')
    ax.set_ylabel("Cumulative Probability (CDF)", fontsize=12, color='white')
    ax.grid(True, alpha=0.25, color='gray', linestyle='--')
    ax.legend(loc='lower right', frameon=True, facecolor='#1e1e1e', edgecolor='#444444', fontsize=11)
    
    os.makedirs("visualizations", exist_ok=True)
    output_path = "visualizations/macro_test_cdf.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#111111')
    plt.close()
    
    speedup = (np.mean(random_times) - np.mean(cassini_times)) / np.mean(random_times) * 100
    # Print stats
    print(f"\n--- Results Summary ---")
    print(f"Average JCT (CASSINI): {np.mean(cassini_times):.2f}ms")
    print(f"Average JCT (Random) : {np.mean(random_times):.2f}ms")
    print(f"Performance Gain    : {speedup:.1f}% faster with CASSINI")
    print(f"CDF Graph saved to {output_path}")

if __name__ == '__main__':
    main()
