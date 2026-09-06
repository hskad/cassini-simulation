import math
from typing import List, Tuple
from src.core.models import Job, Link

def lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)

def discretize_phases(job: Job, lcm_time: float, resolution: float = 1.0) -> List[float]:
    """
    Converts a job's continuous phases into a discrete 1D array representing 
    bandwidth demand over the LCM time.
    """
    num_steps = int(lcm_time / resolution)
    bw_array = [0.0] * num_steps
    
    current_time = 0.0
    iteration_time = job.iteration_time
    
    # Repeat the job's phases over the lcm_time
    while current_time < lcm_time - 1e-9:
        for phase in job.phases:
            start_step = int((current_time + job.time_shift) / resolution) % num_steps
            end_step = int((current_time + job.time_shift + phase.duration) / resolution) % num_steps
            
            # Fill the bandwidth array for this phase
            if start_step <= end_step:
                for step in range(start_step, end_step):
                    bw_array[step] += phase.bandwidth_demand
            else:
                # Wrap around
                for step in range(start_step, num_steps):
                    bw_array[step] += phase.bandwidth_demand
                for step in range(0, end_step):
                    bw_array[step] += phase.bandwidth_demand
                    
            current_time += phase.duration
            if current_time >= lcm_time - 1e-9:
                break
                
    return bw_array

def calculate_score(arrays: List[List[float]], link_capacity: float) -> float:
    """
    Calculates the compatibility score: 1 - average(excess_bandwidth) / capacity.
    """
    if not arrays or not arrays[0]:
        return 1.0
        
    num_steps = len(arrays[0])
    total_excess = 0.0
    
    for step in range(num_steps):
        total_bw = sum(arr[step] for arr in arrays)
        if total_bw > link_capacity:
            total_excess += (total_bw - link_capacity)
            
    average_excess = total_excess / num_steps
    score = 1.0 - (average_excess / link_capacity)
    return score

def optimize_link(jobs: List[Job], link: Link, resolution: float = 1.0) -> None:
    """
    Finds the optimal time-shift for a set of jobs to maximize compatibility.
    (Simple Brute-force array-shifting for demonstration of the math).
    Modifies the jobs in-place with their new time_shift.
    """
    if len(jobs) < 2:
        return # Nothing to interleave
        
    # Calculate LCM of iteration times (round to nearest resolution)
    times = [int(job.iteration_time / resolution) for job in jobs]
    lcm_steps = times[0]
    for t in times[1:]:
        lcm_steps = lcm(lcm_steps, t)
    
    lcm_time = lcm_steps * resolution
    
    # We will hold job[0] fixed, and shift job[1]
    # For a full cluster this needs bipartite graph traversal, but for a single link
    # with 2 jobs, we just slide one against the other.
    if len(jobs) == 2:
        job1, job2 = jobs[0], jobs[1]
        job1.time_shift = 0.0
        
        best_shift = 0.0
        best_score = float('-inf')
        
        # Test all possible shifts for job2
        max_shift_steps = int(job2.iteration_time / resolution)
        for shift_step in range(max_shift_steps):
            shift_time = shift_step * resolution
            job2.time_shift = shift_time
            
            arr1 = discretize_phases(job1, lcm_time, resolution)
            arr2 = discretize_phases(job2, lcm_time, resolution)
            
            score = calculate_score([arr1, arr2], link.capacity)
            
            if score > best_score:
                best_score = score
                best_shift = shift_time
                
        # Apply the best shift
        job2.time_shift = best_shift

