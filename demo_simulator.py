from src.models import Phase, Job, Link, Cluster
from src.simulator import Simulator

def main():
    print("--- CASSINI Time-Based Simulator Demo ---")
    
    # 1. Setup Jobs and Cluster
    # We create a timeline of jobs arriving
    job1 = Job(job_id="j1", name="VGG16", phases=[Phase("compute", 100, 20), Phase("communicate", 50, 40)], arrival_time=0.0, total_iterations=10)
    job2 = Job(job_id="j2", name="ResNet50", phases=[Phase("compute", 80, 10), Phase("communicate", 40, 30)], arrival_time=150.0, total_iterations=15)
    job3 = Job(job_id="j3", name="GPT2", phases=[Phase("compute", 120, 25), Phase("communicate", 60, 45)], arrival_time=300.0, total_iterations=5)
    
    link1 = Link("l1", 50)
    link2 = Link("l2", 50)
    
    cluster = Cluster(servers=[], links=[link1, link2])
    
    print("\nInitializing Simulator...")
    print(f"Cluster Links: 2 (Capacity 50 Gbps each)")
    print(f"Jobs Scheduled:")
    print(f"  - {job1.name} (Arrives at 0ms, 10 iterations)")
    print(f"  - {job2.name} (Arrives at 150ms, 15 iterations)")
    print(f"  - {job3.name} (Arrives at 300ms, 5 iterations)")
    
    sim = Simulator(cluster, penalty_factor=0.5) # Example penalty
    
    # Add jobs to the queue
    sim.add_job_arrival(job1)
    sim.add_job_arrival(job2)
    sim.add_job_arrival(job3)
    
    print("\nRunning Simulation Event Loop...")
    sim.run_simulation()
    
    print("\nSimulation Complete!")
    print("\n--- Final Turnaround Times ---")
    for comp in sim.completed_jobs:
        print(f"Job {comp['job_id']} ({comp['name']}):")
        print(f"  Arrival Time: {comp['arrival_time']:.2f}ms")
        print(f"  Completion Time: {comp['completion_time']:.2f}ms")
        print(f"  Total Turnaround: {comp['turnaround_time']:.2f}ms")

if __name__ == '__main__':
    main()
