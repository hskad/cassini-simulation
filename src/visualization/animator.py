import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from src.core.models import Phase, Job, Link
from src.core.optimizer import discretize_phases, lcm

def create_optimization_gif(job1: Job, job2: Job, link: Link, filename: str, resolution: float = 1.0):
    """
    Creates a GIF animation showing the geometric circle of job2 rotating
    to avoid collision with job1.
    """
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    
    times = [int(job1.iteration_time / resolution), int(job2.iteration_time / resolution)]
    lcm_steps = lcm(times[0], times[1])
    lcm_time = lcm_steps * resolution
    
    theta = np.linspace(0, 2 * np.pi, int(lcm_time / resolution), endpoint=False)
    
    # We will animate job2's time shift from 0 to its optimal shift.
    # The optimal shift from demo_step2 was 114.0ms. We'll simulate rotating to it.
    optimal_shift = 114.0
    move_frames = 40
    hold_frames = 20 # Hold for 2 seconds at 10 fps
    
    # Create the shifts array: move smoothly, then hold the last value
    moving_shifts = np.linspace(0, optimal_shift, move_frames)
    holding_shifts = np.full(hold_frames, optimal_shift)
    shifts = np.concatenate((moving_shifts, holding_shifts))
    total_frames = len(shifts)
    
    # Base array for job1 (fixed)
    job1.time_shift = 0.0
    arr1 = np.array(discretize_phases(job1, lcm_time, resolution))
    
    def update(frame):
        ax.clear()
        
        current_shift = shifts[frame]
        job2.time_shift = current_shift
        
        arr2 = np.array(discretize_phases(job2, lcm_time, resolution))
        
        base_r = np.zeros(len(theta))
        
        # Plot job1 (starting at base_r = 0)
        ax.fill_between(theta, base_r, base_r + arr1, label=f'{job1.name}', color='#00ffcc', alpha=0.6)
        
        # Plot job2 OVERLAPPING (starting at base_r = 0 instead of stacking)
        ax.fill_between(theta, base_r, base_r + arr2, label=f'{job2.name} (Shift: {int(current_shift)}ms)', color='#ff007f', alpha=0.6)
        
        # Draw capacity (overlapping regions will exceed this)
        ax.plot(np.linspace(0, 2*np.pi, 100), [link.capacity]*100, color='white', linestyle='--', linewidth=2, label=f'Capacity ({link.capacity} Gbps)')

        # Aesthetics
        ax.set_title("CASSINI Geometric Alignment", fontsize=16, color='white', pad=20)
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1) # Clockwise
        ax.set_yticklabels([])
        ax.set_xticks(np.linspace(0, 2*np.pi, 8, endpoint=False))
        ax.set_xticklabels([f"{int(t)}ms" for t in np.linspace(0, lcm_time, 8, endpoint=False)], color='gray')
        ax.grid(True, alpha=0.2, color='gray', linestyle='--')
        
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), frameon=True, facecolor='#222222', edgecolor='none')
        
    fig.subplots_adjust(right=0.75)
    print(f"Generating animation with {total_frames} frames...")
    ani = animation.FuncAnimation(fig, update, frames=total_frames, interval=100)
    
    writer = animation.PillowWriter(fps=10)
    ani.save(filename, writer=writer)
    print(f"Saved animation to {filename}")

if __name__ == '__main__':
    os.makedirs('visualizations', exist_ok=True)
    
    # 1. Setup Mock Jobs and Link (Capacity 25 Gbps to force a bottleneck if they overlap)
    j1 = Job(job_id="j1", name="VGG16_A", phases=[
        Phase("compute", duration=141.0, bandwidth_demand=0.0),
        Phase("communicate", duration=114.0, bandwidth_demand=25.0)
    ])
    
    j2 = Job(job_id="j2", name="VGG16_B", phases=[
        Phase("compute", duration=141.0, bandwidth_demand=0.0),
        Phase("communicate", duration=114.0, bandwidth_demand=25.0)
    ])
    
    l1 = Link(link_id="l1", capacity=25.0)
    
    create_optimization_gif(j1, j2, l1, "visualizations/optimization_animation.gif")
