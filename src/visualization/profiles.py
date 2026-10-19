"""Circular bandwidth plot for the geometric example."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from typing import List
from src.core.models import Job, Link
from src.math_engine.optimizer import discretize_phases, hyperperiod

def plot_circular_alignment(jobs: List[Job], link: Link, title: str, filename: str, resolution: float = 1.0):
    """
    Generates a polar plot (circular abstraction) of the bandwidth overlapping,
    mimicking the 'circle' abstraction in the CASSINI paper.
    """
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    
    # Calculate LCM time
    lcm_time = hyperperiod(jobs)
    if lcm_time / resolution > 200_000:
        raise ValueError("The plot exceeds 200,000 samples. Increase resolution.")
    
    # Map the LCM time onto 2*pi radians
    theta = np.linspace(0, 2 * np.pi, int(np.ceil(lcm_time / resolution)), endpoint=False)
    
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
