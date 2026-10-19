import math
from typing import List, Tuple
import numpy as np
from src.core.models import Job, Link

def lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)

def discretize_phases(job: Job, lcm_time: float, resolution: float = 1.0) -> List[float]:
    """
    Samples a repeating job profile over the requested time window.
    Shift one sampled iteration before repeating and truncating the profile.
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
    shift_steps = int(round(job.time_shift / resolution)) % iter_steps
    if shift_steps > 0:
        iter_arr = iter_arr[-shift_steps:] + iter_arr[:-shift_steps]
    reps = (num_steps + iter_steps - 1) // iter_steps
    return (iter_arr * reps)[:num_steps]

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
        period_steps = max(1, int(round(job.iteration_time / resolution)))
        period = np.array(discretize_phases(
            job, period_steps * resolution, resolution), dtype=np.float32)
        job.time_shift = old_shift
        # Every candidate is a slice of the repeating profile, including when
        # the scoring window ends partway through an iteration.
        base = np.tile(period, n // period_steps + 2)
        
        max_shifts = int(job.iteration_time / resolution)
        best_shift = 0.0
        min_excess = float('inf')
        
        for shift_step in range(0, max_shifts, step_sz):
            start = (-shift_step) % period_steps
            rolled = base[start:start + n]
            exc = np.sum(np.maximum(0.0, curr + rolled - link.capacity))
            if exc < min_excess:
                min_excess = exc
                best_shift = float(shift_step * resolution)
                
        job.time_shift = best_shift
        start = (-int(round(best_shift / resolution))) % period_steps
        curr = curr + base[start:start + n]

