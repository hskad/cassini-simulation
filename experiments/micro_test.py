import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.models import Phase, Job, Link
from src.math_engine.optimizer import optimize_link, lcm, discretize_phases, calculate_score
from src.utils.visualizer import plot_circular_alignment

def main():
    parser = argparse.ArgumentParser(description="Micro-Test (Figure 3 Replica)")
    parser.add_argument('--compute-a', type=float, default=30.0, help="Compute time for Job A (ms)")
    parser.add_argument('--comm-a', type=float, default=10.0, help="Comm time for Job A (ms)")
    parser.add_argument('--compute-b', type=float, default=50.0, help="Compute time for Job B (ms)")
    parser.add_argument('--comm-b', type=float, default=10.0, help="Comm time for Job B (ms)")
    parser.add_argument('--capacity', type=float, default=50.0, help="Link capacity (Gbps)")
    parser.add_argument('--demand-a', type=float, default=50.0, help="Bandwidth demand Job A")
    parser.add_argument('--demand-b', type=float, default=50.0, help="Bandwidth demand Job B")
    args = parser.parse_args()

    job_a = Job(job_id="A", name="Job A", phases=[
        Phase("compute", args.compute_a, 0.0),
        Phase("communicate", args.comm_a, args.demand_a)
    ])
    job_b = Job(job_id="B", name="Job B", phases=[
        Phase("compute", args.compute_b, 0.0),
        Phase("communicate", args.comm_b, args.demand_b)
    ])

    link = Link("L1", args.capacity)
    jobs = [job_a, job_b]

    # Pre-calculate LCM
    lcm_time = lcm(int(job_a.iteration_time), int(job_b.iteration_time))

    print(f"--- Micro-Test (Figure 3 Replica) ---")
    print(f"Job A: Iteration={job_a.iteration_time}ms (Compute={args.compute_a}ms, Comm={args.comm_a}ms)")
    print(f"Job B: Iteration={job_b.iteration_time}ms (Compute={args.compute_b}ms, Comm={args.comm_b}ms)")
    print(f"LCM (Unified Circle Perimeter): {lcm_time}ms")

    # Optimize Link
    optimize_link(jobs, link, resolution=1.0)

    # Calculate final score
    arr_a = discretize_phases(jobs[0], lcm_time, 1.0)
    arr_b = discretize_phases(jobs[1], lcm_time, 1.0)
    score = calculate_score([arr_a, arr_b], link.capacity)

    print(f"\nOptimization Complete!")
    print(f"Compatibility Score: {score * 100:.1f}%")
    
    # Calculate degrees
    for j in jobs:
        degrees = (j.time_shift / lcm_time) * 360
        print(f"{j.name} Time Shift: {j.time_shift}ms -> Geometric Shift: {degrees:.1f} degrees")

    # Save visualization
    output_dir = os.path.join(PROJECT_ROOT, "visualizations")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "micro_test_circular.png")
    plot_circular_alignment(jobs, link, "Micro-Test (Figure 3)", output_path)
    print(f"\nCircular visualization saved to {output_path}")

if __name__ == '__main__':
    main()
