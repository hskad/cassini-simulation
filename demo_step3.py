import os
from src.models import Phase, Job, Link, Cluster, Server
from src.graph import build_affinity_graph, traverse_affinity_graph
from src.visualizer import plot_affinity_graph

def main():
    os.makedirs('visualizations', exist_ok=True)
    
    # 1. Setup Mock Multi-Link Scenario
    job1 = Job(job_id="j1", name="VGG16_1", phases=[Phase("compute", 100, 0)], iteration_time=100)
    job2 = Job(job_id="j2", name="VGG16_2", phases=[Phase("compute", 100, 0)], iteration_time=100)
    job3 = Job(job_id="j3", name="VGG16_3", phases=[Phase("compute", 100, 0)], iteration_time=100)
    
    link1 = Link(link_id="l1", capacity=50)
    link2 = Link(link_id="l2", capacity=50)
    
    cluster = Cluster(
        servers=[], 
        links=[link1, link2],
        link_jobs={
            "l1": [job1, job2],
            "l2": [job2, job3]
        }
    )
    
    # Mocking the optimal shifts from the optimizer for simplicity of the demo
    optimal_shifts = {
        "l1": {"j1": 0.0, "j2": 30.0},
        "l2": {"j2": 0.0, "j3": 40.0}
    }
    
    # 2. Build the Bipartite Affinity Graph
    print("Building Bipartite Affinity Graph...")
    graph = build_affinity_graph(cluster, optimal_shifts)
    
    # 3. Plot the Graph
    print("Plotting Affinity Graph...")
    plot_affinity_graph(graph, "Cluster-Wide Affinity Graph", "visualizations/affinity_graph.png")
    
    # 4. Traverse and resolve unique time-shifts
    print("Running Algorithm 1 (BFS Traversal)...")
    jobs_map = {"j1": job1, "j2": job2, "j3": job3}
    global_shifts = traverse_affinity_graph(graph, jobs_map)
    
    print("\nResolved Unique Global Time-Shifts:")
    for jid, shift in global_shifts.items():
        print(f"  Job {jid}: {shift}ms")
        
    print("\nDone! Check visualizations/affinity_graph.png")

if __name__ == '__main__':
    main()
