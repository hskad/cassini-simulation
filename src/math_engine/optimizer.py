import math
from typing import List, Tuple
import numpy as np
from src.core.models import Job, Link

DEFAULT_SCORE_WINDOW_MS = 600.0

def lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)

def discretize_phases(job: Job, lcm_time: float, resolution: float = 1.0,
                      start_time: float = 0.0) -> List[float]:
    """
    Samples a repeating job profile over the requested time window [start_time, start_time + lcm_time].
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
    effective_shift = job.time_shift - start_time
    shift_steps = int(round(effective_shift / resolution)) % iter_steps
    if shift_steps > 0:
        iter_arr = iter_arr[-shift_steps:] + iter_arr[:-shift_steps]
    reps = (num_steps + iter_steps - 1) // iter_steps
    return (iter_arr * reps)[:num_steps]

def calculate_score(arrays: List[List[float]], link_capacity: float) -> float:
    """
    Calculates the compatibility score: 1 - average(excess_bandwidth) / capacity.
    """
    if len(arrays) == 0 or len(arrays[0]) == 0:
        return 1.0
    tot = np.sum(np.array(arrays, dtype=np.float32), axis=0)
    excess = np.sum(np.maximum(0.0, tot - link_capacity))
    return float(1.0 - (excess / (len(tot) * link_capacity)))

def get_score_window(jobs: List[Job], resolution: float = 1.0,
                     score_window_ms: float = DEFAULT_SCORE_WINDOW_MS) -> float:
    """Use the sampled common period, bounded by one shared limit in ms."""
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("Scoring resolution must be finite and positive.")
    if not math.isfinite(score_window_ms) or score_window_ms < resolution:
        raise ValueError("Scoring window must be finite and at least one sample long.")
    if not jobs:
        return 0.0
    limit_steps = int(math.floor(score_window_ms / resolution))
    common_steps = 1
    for job in jobs:
        # Match the cycle length used by discretize_phases.
        period_steps = max(1, int(round(job.iteration_time / resolution)))
        common_steps = lcm(common_steps, period_steps)
        if common_steps >= limit_steps:
            return limit_steps * resolution
    return common_steps * resolution


def get_strided_windows(jobs: List[Job], resolution: float = 1.0,
                        score_window_ms: float = DEFAULT_SCORE_WINDOW_MS,
                        num_windows: int = 1) -> List[Tuple[float, float]]:
    """
    Returns a list of (start_time_ms, duration_ms) segments.
    If num_windows == 1 or LCM <= score_window_ms, returns a single window [(0.0, window_ms)].
    Otherwise, splits the total budget (score_window_ms) into num_windows segments
    spread evenly across the true hyperperiod [0, LCM].
    """
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("Scoring resolution must be finite and positive.")
    if not math.isfinite(score_window_ms) or score_window_ms < resolution:
        raise ValueError("Scoring window must be finite and at least one sample long.")
    if not jobs:
        return [(0.0, 0.0)]
    if num_windows <= 1:
        window = get_score_window(jobs, resolution, score_window_ms)
        return [(0.0, window)]

    common_steps = 1
    for job in jobs:
        period_steps = max(1, int(round(job.iteration_time / resolution)))
        common_steps = lcm(common_steps, period_steps)
    full_lcm_ms = common_steps * resolution

    limit_steps = int(math.floor(score_window_ms / resolution))
    if common_steps <= limit_steps:
        return [(0.0, full_lcm_ms)]

    total_budget_steps = limit_steps
    seg_steps = max(1, total_budget_steps // num_windows)
    seg_duration_ms = seg_steps * resolution
    actual_windows = min(num_windows, total_budget_steps // seg_steps)

    span = full_lcm_ms - seg_duration_ms
    windows = []
    for k in range(actual_windows):
        frac = k / (actual_windows - 1) if actual_windows > 1 else 0.0
        start_ms = round(frac * span / resolution) * resolution
        windows.append((float(start_ms), float(seg_duration_ms)))
    return windows


def score_link(jobs: List[Job], link: Link, resolution: float = 1.0,
               score_window_ms: float = DEFAULT_SCORE_WINDOW_MS,
               num_windows: int = 1) -> float:
    """Score the link over a contiguous window or multiple strided windows."""
    windows = get_strided_windows(jobs, resolution, score_window_ms, num_windows)
    arrays = []
    for job in jobs:
        job_slices = [
            np.array(discretize_phases(job, dur, resolution, start_time=st), dtype=np.float32)
            for st, dur in windows
        ]
        arrays.append(np.concatenate(job_slices) if len(job_slices) > 1 else job_slices[0])
    return calculate_score(arrays, link.capacity)


def optimize_link(jobs: List[Job], link: Link, resolution: float = 1.0, *,
                  score_window_ms: float = DEFAULT_SCORE_WINDOW_MS,
                  num_windows: int = 1) -> None:
    """
    Finds the optimal time-shift for a set of jobs to maximize compatibility.
    (Fast circular sliding and greedy multi-job phase alignment).
    Supports either a single contiguous window (num_windows=1) or multiple
    strided windows spread across the hyperperiod.
    Modifies the jobs in-place with their new time_shift.
    """
    windows = get_strided_windows(jobs, resolution, score_window_ms, num_windows)
    if len(jobs) < 2:
        return
    
    # Hold jobs[0] fixed at 0.0 shift
    jobs[0].time_shift = 0.0
    curr_slices = [
        np.array(discretize_phases(jobs[0], dur, resolution, start_time=st), dtype=np.float32)
        for st, dur in windows
    ]
    curr = np.concatenate(curr_slices) if len(curr_slices) > 1 else curr_slices[0]
    
    # For exactly 2 jobs (like Figure 3 micro-test), check all discrete steps
    # For multi-job links, fine step ensures speed and quality
    step_sz = 1 if len(jobs) == 2 else max(1, int(2.0 / resolution))
    
    for job in jobs[1:]:
        old_shift = job.time_shift
        job.time_shift = 0.0
        period_steps = max(1, int(round(job.iteration_time / resolution)))
        
        # Prepare the base periodic tiles for each window segment
        window_bases = []
        for st, dur in windows:
            n_k = int(round(dur / resolution))
            period_k = np.array(discretize_phases(
                job, period_steps * resolution, resolution, start_time=st), dtype=np.float32)
            base_k = np.tile(period_k, n_k // period_steps + 2)
            window_bases.append((base_k, n_k))
        job.time_shift = old_shift
        
        max_shifts = int(job.iteration_time / resolution)
        best_shift = 0.0
        min_excess = float('inf')
        
        for shift_step in range(0, max_shifts, step_sz):
            start = (-shift_step) % period_steps
            if len(window_bases) == 1:
                rolled = window_bases[0][0][start:start + window_bases[0][1]]
            else:
                rolled = np.concatenate([
                    base_k[start:start + n_k] for base_k, n_k in window_bases
                ])
            exc = np.sum(np.maximum(0.0, curr + rolled - link.capacity))
            if exc < min_excess:
                min_excess = exc
                best_shift = float(shift_step * resolution)
                
        job.time_shift = best_shift
        start = (-int(round(best_shift / resolution))) % period_steps
        if len(window_bases) == 1:
            best_rolled = window_bases[0][0][start:start + window_bases[0][1]]
        else:
            best_rolled = np.concatenate([
                base_k[start:start + n_k] for base_k, n_k in window_bases
            ])
        curr = curr + best_rolled

