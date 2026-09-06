import math
from typing import List, Tuple
import numpy as np
from src.core.models import Job, Link

def lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)

def discretize_phases(job: Job, lcm_time: float, resolution: float = 1.0) -> List[float]:
    """
    Converts a job's continuous phases into a discrete 1D array representing 
    bandwidth demand over the LCM time.
    """
    iter_steps = max(1, int(round(job.iteration_time / resolution)))
    iter_arr = [0.0] * iter_steps
    curr = 0
    for p in job.phases:
        d = int(round(p.duration / resolution))
        if p.bandwidth_demand > 0:
            for s in range(curr, min(iter_steps, curr + d)):
                iter_arr[s] = p.bandwidth_demand
        curr += d
    num_steps = max(1, int(round(lcm_time / resolution)))
    reps = (num_steps // iter_steps) + 2
    full_arr = (iter_arr * reps)[:num_steps]
    shift_steps = int(round(job.time_shift / resolution)) % num_steps
    if shift_steps > 0:
        return full_arr[-shift_steps:] + full_arr[:-shift_steps]
    return full_arr

def calculate_score(arrays: List[List[float]], link_capacity: float) -> float:
    """
    Calculates the compatibility score: 1 - average(excess_bandwidth) / capacity.
    """
    if not arrays or not arrays[0]:
        return 1.0
    tot = np.sum(np.array(arrays, dtype=np.float32), axis=0)
    excess = np.sum(np.maximum(0.0, tot - link_capacity))
    return float(1.0 - (excess / (len(tot) * link_capacity)))

def optimize_link(jobs: List[Job], link: Link, resolution: float = 1.0) -> None:
    """
    Finds the optimal time-shift for a set of jobs to maximize compatibility.
    (Fast circular sliding and greedy multi-job phase alignment).
    Modifies the jobs in-place with their new time_shift.
    """
    if len(jobs) < 2:
        return
        
    times = [int(job.iteration_time / resolution) for job in jobs]
    lcm_steps = times[0]
    for t in times[1:]:
        lcm_steps = lcm(lcm_steps, t)
    
    # Cap hyperperiod for computational tractability
    lcm_steps = min(lcm_steps, 600)
    lcm_time = lcm_steps * resolution
    
    # Hold jobs[0] fixed at 0.0 shift
    jobs[0].time_shift = 0.0
    curr = np.array(discretize_phases(jobs[0], lcm_time, resolution), dtype=np.float32)
    n = len(curr)
    
    # For exactly 2 jobs (like Figure 3 micro-test), check all discrete steps
    # For multi-job links, fine step ensures speed and quality
    step_sz = 1 if len(jobs) == 2 else max(1, int(2.0 / resolution))
    
    for job in jobs[1:]:
        old_shift = job.time_shift
        job.time_shift = 0.0
        base = np.array(discretize_phases(job, lcm_time, resolution), dtype=np.float32)
        job.time_shift = old_shift
        
        max_shifts = int(job.iteration_time / resolution)
        best_shift = 0.0
        min_excess = float('inf')
        
        for shift_step in range(0, max_shifts, step_sz):
            rolled = np.roll(base, shift_step)
            exc = np.sum(np.maximum(0.0, curr + rolled - link.capacity))
            if exc < min_excess:
                min_excess = exc
                best_shift = float(shift_step * resolution)
                
        job.time_shift = best_shift
        roll = int(round(best_shift / resolution)) % n
        curr = curr + np.roll(base, roll)

