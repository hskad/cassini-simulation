import os
from src.models import Phase, Job, Link
from src.optimizer import optimize_link
from src.visualizer import plot_link_alignment

def main():
    # Make sure we have an output directory for images
    os.makedirs('visualizations', exist_ok=True)
    
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
    
    # 2. Plot Before Optimization
    print("Plotting Before Optimization...")
    plot_link_alignment([job1, job2], link, "Before Optimization: Bandwidth Collision", "visualizations/before_optimization.png")
    
    # 3. Optimize
    print("Running Link-Level Optimizer...")
    optimize_link([job1, job2], link)
    print(f"Optimal Time-Shift for {job2.name}: {job2.time_shift}ms")
    
    # 4. Plot After Optimization
    print("Plotting After Optimization...")
    plot_link_alignment([job1, job2], link, "After Optimization: Perfectly Interleaved", "visualizations/after_optimization.png")
    print("Done! Check the visualizations folder.")

if __name__ == '__main__':
    main()
