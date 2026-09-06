import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import Phase, Job, Link
from src.math_engine.optimizer import optimize_link

def main():
    print("--- CASSINI Link-Level Optimizer Demo ---")
    
    # 1. Setup Mock Jobs and Link (Capacity 25 Gbps to force a bottleneck if they overlap)
    job1 = Job(job_id="j1", name="VGG16_A", phases=[
        Phase("compute", duration=141.0, bandwidth_demand=0.0),
        Phase("communicate", duration=114.0, bandwidth_demand=25.0)
    ])
    
    job2 = Job(job_id="j2", name="VGG16_B", phases=[
        Phase("compute", duration=141.0, bandwidth_demand=0.0),
        Phase("communicate", duration=114.0, bandwidth_demand=25.0)
    ])
    
    link = Link(link_id="l1", capacity=25.0)
    
    print("Initial State:")
    print(f"  {job1.name}: Iteration={job1.iteration_time}ms, TimeShift={job1.time_shift}ms")
    print(f"  {job2.name}: Iteration={job2.iteration_time}ms, TimeShift={job2.time_shift}ms")
    print(f"  Link Capacity: {link.capacity} Gbps")
    
    # 2. Optimize
    print("\nRunning Link-Level Optimizer...")
    optimize_link([job1, job2], link)
    print(f"Optimal Time-Shift for {job2.name}: {job2.time_shift}ms")
    print("\nOptimization Complete! (See visualizations/optimization_animation.gif for animated demonstration)")

if __name__ == '__main__':
    main()
