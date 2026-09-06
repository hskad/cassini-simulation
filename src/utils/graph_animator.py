import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx
from collections import deque

from src.models import Phase, Job, Link, Cluster
from src.graph import build_affinity_graph

def trace_bfs(graph, jobs_map):
    """
    Yields the state of the BFS algorithm at every step to build animation frames.
    Yields: (visited_U, visited_V, current_node, active_edge)
    """
    visited_U = set()
    visited_V = set()
    global_time_shifts = {}
    
    # Initial state (nothing visited)
    yield visited_U, visited_V, None, None
    
    for u in graph.U:
        if u in visited_U:
            continue
            
        queue = deque([u])
        global_time_shifts[u] = 0.0
        visited_U.add(u)
        
        # State: Root node added
        yield visited_U.copy(), visited_V.copy(), u, None
        
        while queue:
            current_job = queue.popleft()
            
            for link_id in graph.edges_U_to_V.get(current_job, []):
                visited_V.add(link_id)
                # State: Exploring an edge to a link
                yield visited_U.copy(), visited_V.copy(), current_job, (current_job, link_id)
                
                for neighbor_job in graph.edges_V_to_U.get(link_id, []):
                    # State: Exploring edge from link to neighbor job
                    yield visited_U.copy(), visited_V.copy(), link_id, (link_id, neighbor_job)
                    
                    if neighbor_job not in visited_U:
                        visited_U.add(neighbor_job)
                        queue.append(neighbor_job)
                        
                        # State: Discovered a new job
                        yield visited_U.copy(), visited_V.copy(), neighbor_job, (link_id, neighbor_job)
                        
    # Final state: Hold for a few frames
    for _ in range(10):
        yield visited_U, visited_V, None, None

def create_bfs_animation(filename: str):
    # Setup Complex Cluster (from demo)
    j1 = Job(job_id="j1", name="VGG16", phases=[Phase("compute", 100, 0)])
    j2 = Job(job_id="j2", name="ResNet50", phases=[Phase("compute", 100, 0)])
    j3 = Job(job_id="j3", name="GPT2", phases=[Phase("compute", 100, 0)])
    j4 = Job(job_id="j4", name="BERT", phases=[Phase("compute", 100, 0)])
    j5 = Job(job_id="j5", name="DLRM", phases=[Phase("compute", 100, 0)])
    
    cluster = Cluster(
        servers=[], 
        links=[Link("l1", 50), Link("l2", 50), Link("l3", 50), Link("l4", 50)],
        link_jobs={
            "l1": [j1, j2, j3],
            "l2": [j2, j4],
            "l3": [j3, j4, j5],
            "l4": [j1, j5]
        }
    )
    optimal_shifts = {
        "l1": {"j1": 0.0, "j2": 10.0, "j3": 20.0},
        "l2": {"j2": 0.0, "j4": 30.0},
        "l3": {"j3": 0.0, "j4": 15.0, "j5": 40.0},
        "l4": {"j1": 0.0, "j5": 25.0}
    }
    
    graph = build_affinity_graph(cluster, optimal_shifts)
    jobs_map = {"j1": j1, "j2": j2, "j3": j3, "j4": j4, "j5": j5}
    
    # Setup nx Graph and Layout
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    G = nx.Graph()
    G.add_nodes_from(graph.U, bipartite=0)
    G.add_nodes_from(graph.V, bipartite=1)
    for u in graph.U:
        for v in graph.edges_U_to_V.get(u, []):
            G.add_edge(u, v)
            
    pos = {}
    for i, u in enumerate(sorted(list(graph.U))):
        pos[u] = (i, 1)
    for i, v in enumerate(sorted(list(graph.V))):
        pos[v] = (i + 0.5, 0)
        
    frames_data = list(trace_bfs(graph, jobs_map))
    
    def update(frame_idx):
        ax.clear()
        visited_U, visited_V, current, active_edge = frames_data[frame_idx]
        
        # Determine Node Colors
        node_colors = []
        for n in G.nodes():
            if n == current:
                node_colors.append('#FFFF00') # Yellow active
            elif n in graph.U: # Job
                node_colors.append('#ff007f' if n in visited_U else '#444444')
            else: # Link
                node_colors.append('#00ffcc' if n in visited_V else '#444444')
                
        # Determine Edge Colors
        edge_colors = []
        edge_widths = []
        for e in G.edges():
            u, v = e
            if active_edge and ((u == active_edge[0] and v == active_edge[1]) or (u == active_edge[1] and v == active_edge[0])):
                edge_colors.append('#FFFF00')
                edge_widths.append(4.0)
            elif (u in visited_U and v in visited_V) or (v in visited_U and u in visited_V):
                # Edge has been fully traversed
                edge_colors.append('#aaaaaa')
                edge_widths.append(2.0)
            else:
                edge_colors.append('#333333')
                edge_widths.append(1.0)
                
        nx.draw_networkx_nodes(G, pos, nodelist=graph.U, node_color=[c for n,c in zip(G.nodes(), node_colors) if n in graph.U], node_size=1500, alpha=0.9, ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=graph.V, node_color=[c for n,c in zip(G.nodes(), node_colors) if n in graph.V], node_size=1500, alpha=0.9, node_shape='s', ax=ax)
        nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color=edge_colors, ax=ax)
        nx.draw_networkx_labels(G, pos, font_size=12, font_color='white', font_weight='bold', ax=ax)
        
        ax.set_title("Bipartite Affinity Graph BFS Traversal", fontsize=16, color='white', pad=20)
        ax.axis('off')
        
    print(f"Generating animation with {len(frames_data)} frames...")
    ani = animation.FuncAnimation(fig, update, frames=len(frames_data), interval=400)
    
    writer = animation.PillowWriter(fps=3)
    ani.save(filename, writer=writer)
    print(f"Saved animation to {filename}")

if __name__ == '__main__':
    os.makedirs('visualizations', exist_ok=True)
    create_bfs_animation('visualizations/affinity_bfs_animation.gif')
