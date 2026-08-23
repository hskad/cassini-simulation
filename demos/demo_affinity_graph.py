import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import Phase, Job, Link, Cluster, Server
from src.graph import build_affinity_graph, traverse_affinity_graph
from src.visualizer import plot_affinity_graph

def main():
    os.makedirs('visualizations', exist_ok=True)
    
    # 1. Setup Mock Complex Multi-Link Scenario
    job1 = Job(job_id="j1", name="VGG16", phases=[Phase("compute", 100, 0)])
    job2 = Job(job_id="j2", name="ResNet50", phases=[Phase("compute", 100, 0)])
    job3 = Job(job_id="j3", name="GPT2", phases=[Phase("compute", 100, 0)])
    job4 = Job(job_id="j4", name="BERT", phases=[Phase("compute", 100, 0)])
    job5 = Job(job_id="j5", name="DLRM", phases=[Phase("compute", 100, 0)])
    
    link1 = Link(link_id="l1", capacity=50)
    link2 = Link(link_id="l2", capacity=50)
    link3 = Link(link_id="l3", capacity=50)
    link4 = Link(link_id="l4", capacity=50)
    
    cluster = Cluster(
        servers=[], 
        links=[link1, link2, link3, link4],
        link_jobs={
            "l1": [job1, job2, job3],
            "l2": [job2, job4],
            "l3": [job3, job4, job5],
            "l4": [job1, job5]
        }
    )
    
    # Mocking the optimal shifts from the optimizer for simplicity of the demo
    optimal_shifts = {
        "l1": {"j1": 0.0, "j2": 10.0, "j3": 20.0},
        "l2": {"j2": 0.0, "j4": 30.0},
        "l3": {"j3": 0.0, "j4": 15.0, "j5": 40.0},
        "l4": {"j1": 0.0, "j5": 25.0}
    }
    
    # 2. Build the Bipartite Affinity Graph
    print("Building Complex Bipartite Affinity Graph...")
    graph = build_affinity_graph(cluster, optimal_shifts)
    
    # 3. Plot the Graph
    print("Plotting Affinity Graph...")
    plot_affinity_graph(graph, "Complex Cluster-Wide Affinity Graph", "visualizations/complex_affinity_graph.png")
    
    # 4. Traverse and resolve unique time-shifts
    print("Running Algorithm 1 (BFS Traversal)...")
    jobs_map = {"j1": job1, "j2": job2, "j3": job3, "j4": job4, "j5": job5}
    global_shifts = traverse_affinity_graph(graph, jobs_map)
    
    print("\nResolved Unique Global Time-Shifts:")
    for jid, shift in global_shifts.items():
        print(f"  Job {jid}: {shift}ms")
        
    print("\nDone! Check visualizations/complex_affinity_graph.png")

if __name__ == '__main__':
    main()
