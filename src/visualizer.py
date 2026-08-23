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
