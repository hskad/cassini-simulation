import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx
from collections import deque

from examples.affinity_scenario import build_demo_scenario
from src.math_engine.graph import traverse_affinity_graph

def trace_bfs(graph, jobs_map):
    """
    Yields the state of the BFS algorithm at every step to build animation frames.
    Yields: (visited_jobs, visited_links, current_node, active_edge, assigned_shifts)
    """
    shifts = traverse_affinity_graph(graph, jobs_map)  # Reject cycles first.
    visited_U, visited_V = set(), set()
    yield visited_U.copy(), visited_V.copy(), None, None, {}
    for root in jobs_map:
        if root not in graph.U or root in visited_U:
            continue
        queue = deque([root])
        visited_U.add(root)
        yield visited_U.copy(), visited_V.copy(), ("job", root), None, {j: shifts[j] for j in visited_U}
        while queue:
            job = queue.popleft()
            for link in graph.edges_U_to_V[job]:
                if link in visited_V:
                    continue
                visited_V.add(link)
                yield visited_U.copy(), visited_V.copy(), ("link", link), (("job", job), ("link", link)), {j: shifts[j] for j in visited_U}
                for neighbor in graph.edges_V_to_U[link]:
                    if neighbor in visited_U:
                        continue
                    visited_U.add(neighbor)
                    queue.append(neighbor)
                    yield visited_U.copy(), visited_V.copy(), ("job", neighbor), (("link", link), ("job", neighbor)), {j: shifts[j] for j in visited_U}
    final = (visited_U.copy(), visited_V.copy(), None, None, shifts)
    for _ in range(6):
        yield final


def create_bfs_animation(filename: str):
    graph, jobs_map = build_demo_scenario()
    # Setup nx Graph and Layout
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(9, 7))
    fig.subplots_adjust(bottom=0.12)
    fig.text(0.5, 0.035, "Illustrative edge shifts; all job periods = 100 ms", ha="center", fontsize=11)
    
    G = nx.Graph()
    G.add_nodes_from([("job", j) for j in sorted(graph.U)], bipartite=0)
    G.add_nodes_from([("link", l) for l in sorted(graph.V)], bipartite=1)
    for u in graph.U:
        for v in graph.edges_U_to_V.get(u, []):
            G.add_edge(("job", u), ("link", v))
            
    # Lay out this shared tree by depth so edges and labels do not cross.
    pos = {
        ("job", "j1"): (0, 3), ("link", "l1"): (0, 2),
        ("job", "j2"): (-1, 1), ("job", "j3"): (1, 1),
        ("link", "l2"): (-1, 0), ("link", "l3"): (1, 0),
        ("job", "j4"): (-1, -1), ("job", "j5"): (1, -1),
    }

    frames_data = list(trace_bfs(graph, jobs_map))
    
    def update(frame_idx):
        ax.clear()
        visited_U, visited_V, current, active_edge, shifts = frames_data[frame_idx]
        
        # Determine Node Colors
        node_colors = []
        for n in G.nodes():
            if n == current:
                node_colors.append('#FFFF00') # Yellow active
            elif n[0] == "job": # Job
                node_colors.append('#ff007f' if n[1] in visited_U else '#444444')
            else: # Link
                node_colors.append('#00ffcc' if n[1] in visited_V else '#444444')
                
        # Determine Edge Colors
        edge_colors = []
        edge_widths = []
        for e in G.edges():
            u, v = e
            if active_edge and ((u == active_edge[0] and v == active_edge[1]) or (u == active_edge[1] and v == active_edge[0])):
                edge_colors.append('#FFFF00')
                edge_widths.append(4.0)
            elif u[1] in (visited_U if u[0] == "job" else visited_V) and v[1] in (visited_U if v[0] == "job" else visited_V):
                # Edge has been fully traversed
                edge_colors.append('#aaaaaa')
                edge_widths.append(2.0)
            else:
                edge_colors.append('#333333')
                edge_widths.append(1.0)
                
        nx.draw_networkx_nodes(G, pos, nodelist=[n for n in G if n[0] == "job"], node_color=[c for n,c in zip(G.nodes(), node_colors) if n[0] == "job"], node_size=1500, alpha=0.9, ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=[n for n in G if n[0] == "link"], node_color=[c for n,c in zip(G.nodes(), node_colors) if n[0] == "link"], node_size=1500, alpha=0.9, node_shape='s', ax=ax)
        nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color=edge_colors, ax=ax)
        edge_labels = {(("job", j), ("link", link)): f"{graph.weights[(j, link)]:g} ms"
                       for j in graph.edges_U_to_V for link in graph.edges_U_to_V[j]}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels,
                                     font_size=8, font_color="white", ax=ax,
                                     bbox={"facecolor": "#222222", "edgecolor": "none"})
        labels = {n: (f"{n[1]}\n{shifts[n[1]]:g} ms" if n[0] == "job" and n[1] in shifts else n[1]) for n in G}
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=11, font_color='white', font_weight='bold', ax=ax)
        
        ax.set_title("Acyclic affinity graph: shift propagation", fontsize=16, color='white', pad=20)
        ax.axis('off')
        
    print(f"Generating animation with {len(frames_data)} frames...")
    ani = animation.FuncAnimation(fig, update, frames=len(frames_data), interval=400)
    
    writer = animation.PillowWriter(fps=3)
    ani.save(filename, writer=writer)
    plt.close(fig)
    print(f"Saved animation to {filename}")

if __name__ == '__main__':
    output_dir = os.path.join(PROJECT_ROOT, 'visualizations')
    os.makedirs(output_dir, exist_ok=True)
    create_bfs_animation(os.path.join(output_dir, 'affinity_bfs_animation.gif'))
