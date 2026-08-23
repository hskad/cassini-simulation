import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from typing import List
from src.models import Job, Link
from src.optimizer import discretize_phases, lcm

def plot_link_alignment(jobs: List[Job], link: Link, title: str, filename: str, resolution: float = 1.0):
    """
    Generates a stacked bandwidth chart showing overlapping traffic.
    Aesthetically pleasing, modern dark-mode style.
    """
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Calculate LCM time
    times = [int(job.iteration_time / resolution) for job in jobs]
    lcm_steps = times[0]
    for t in times[1:]:
        lcm_steps = lcm(lcm_steps, t)
    lcm_time = lcm_steps * resolution
    
    x = np.arange(0, lcm_time, resolution)
    y_arrays = []
    
    # Define some vibrant colors
    colors = ['#00ffcc', '#ff007f', '#e6e6fa', '#f0e68c']
    
    bottom_y = np.zeros(len(x))
    
    for i, job in enumerate(jobs):
        arr = discretize_phases(job, lcm_time, resolution)
        arr = np.array(arr)
        y_arrays.append(arr)
        
        ax.fill_between(x, bottom_y, bottom_y + arr, label=f'Job {job.name} (Shift: {job.time_shift}ms)', 
                        color=colors[i % len(colors)], alpha=0.8, linewidth=0)
        bottom_y += arr

    # Draw the link capacity line
    ax.axhline(y=link.capacity, color='white', linestyle='--', linewidth=2, label=f'Capacity ({link.capacity} Gbps)')
    
    # Aesthetics
    ax.set_title(title, fontsize=16, color='white', pad=15)
    ax.set_xlabel('Time (ms)', fontsize=12, color='white')
    ax.set_ylabel('Bandwidth (Gbps)', fontsize=12, color='white')
    
    # Clean up grid and spines
    ax.grid(True, alpha=0.2, color='gray', linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('gray')
    ax.spines['bottom'].set_color('gray')
    
    ax.legend(loc='upper right', frameon=True, facecolor='#222222', edgecolor='none')
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='#111111')
    plt.close()

def plot_circular_alignment(jobs: List[Job], link: Link, title: str, filename: str, resolution: float = 1.0):
    """
    Generates a polar plot (circular abstraction) of the bandwidth overlapping,
    mimicking the 'circle' abstraction in the CASSINI paper.
    """
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    
    # Calculate LCM time
    times = [int(job.iteration_time / resolution) for job in jobs]
    lcm_steps = times[0]
    for t in times[1:]:
        lcm_steps = lcm(lcm_steps, t)
    lcm_time = lcm_steps * resolution
    
    # Map the LCM time onto 2*pi radians
    theta = np.linspace(0, 2 * np.pi, int(lcm_time / resolution), endpoint=False)
    
    colors = ['#00ffcc', '#ff007f', '#e6e6fa', '#f0e68c']
    
    bottom_r = np.zeros(len(theta))
    
    for i, job in enumerate(jobs):
        arr = discretize_phases(job, lcm_time, resolution)
        arr = np.array(arr)
        
        ax.fill_between(theta, bottom_r, bottom_r + arr, label=f'Job {job.name} (Shift: {job.time_shift}ms)', 
                        color=colors[i % len(colors)], alpha=0.6)
        bottom_r += arr
        
    # Draw capacity circle
    ax.plot(np.linspace(0, 2*np.pi, 100), [link.capacity]*100, color='white', linestyle='--', linewidth=2, label=f'Capacity ({link.capacity} Gbps)')

    # Aesthetics
    ax.set_title(title, fontsize=16, color='white', pad=20)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1) # Clockwise
    
    # Hide radial labels, keep angular but as time
    ax.set_yticklabels([])
    ax.set_xticks(np.linspace(0, 2*np.pi, 8, endpoint=False))
    ax.set_xticklabels([f"{int(t)}ms" for t in np.linspace(0, lcm_time, 8, endpoint=False)], color='gray')
    
    ax.grid(True, alpha=0.2, color='gray', linestyle='--')
    
    ax.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1), frameon=True, facecolor='#222222', edgecolor='none')
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='#111111')
    plt.close()

def plot_affinity_graph(graph, title: str, filename: str):
    """
    Plots the bipartite Affinity Graph using networkx.
    """
    try:
        import networkx as nx
    except ImportError:
        print("NetworkX is required for this visualization. Please install it.")
        return
        
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create networkx graph
    G = nx.Graph()
    
    # Add nodes with bipartite attribute
    G.add_nodes_from(graph.U, bipartite=0) # Jobs
    G.add_nodes_from(graph.V, bipartite=1) # Links
    
    # Add edges
    for u in graph.U:
        for v in graph.edges_U_to_V.get(u, []):
            G.add_edge(u, v)
            
    # Define positions for bipartite layout
    # Jobs on top (y=1), Links on bottom (y=0)
    pos = {}
    for i, u in enumerate(sorted(list(graph.U))):
        pos[u] = (i, 1)
    for i, v in enumerate(sorted(list(graph.V))):
        pos[v] = (i + 0.5 if len(graph.V) < len(graph.U) else i, 0)
        
    # Draw Jobs
    nx.draw_networkx_nodes(G, pos, nodelist=graph.U, node_color='#ff007f', node_size=1500, alpha=0.9, ax=ax)
    # Draw Links
    nx.draw_networkx_nodes(G, pos, nodelist=graph.V, node_color='#00ffcc', node_size=1500, alpha=0.9, node_shape='s', ax=ax)
    
    # Draw Edges
    nx.draw_networkx_edges(G, pos, width=2.0, alpha=0.7, edge_color='gray', ax=ax)
    
    # Draw Labels
    nx.draw_networkx_labels(G, pos, font_size=12, font_color='white', font_weight='bold', ax=ax)
    
    ax.set_title(title, fontsize=16, color='white', pad=20)
    ax.axis('off')
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='#111111')
    plt.close()
