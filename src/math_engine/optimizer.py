"""Periodic bandwidth profiles and a discrete, greedy shift search."""
import math
import itertools
from fractions import Fraction
from typing import List, Optional
import numpy as np
from src.core.models import Job, Link


class ProfileLimitError(ValueError):
    """The requested profile exceeds the explicit calculation budget."""


def lcm(a: int, b: int) -> int:
    return math.lcm(a, b)


def validate_profile(job: Job) -> None:
    if not job.phases:
        raise ValueError("A job must have at least one phase.")
    for phase in job.phases:
        if not math.isfinite(phase.duration) or phase.duration <= 0:
            raise ValueError("Phase duration must be finite and positive.")
        if not math.isfinite(phase.bandwidth_demand) or phase.bandwidth_demand < 0:
            raise ValueError("Bandwidth demand must be finite and nonnegative.")
    if not math.isfinite(job.time_shift):
        raise ValueError("Time shift must be finite.")


def hyperperiod(jobs: List[Job]) -> float:
    """Return the common period without rounding fractional phase times."""
    if not jobs:
        return 0.0
    periods = []
    for job in jobs:
        validate_profile(job)
        periods.append(sum((Fraction(str(p.duration)) for p in job.phases), Fraction()))
    denominator = math.lcm(*(p.denominator for p in periods))
    ticks = [p.numerator * (denominator // p.denominator) for p in periods]
    return float(Fraction(math.lcm(*ticks), denominator))


def discretize_phases(job: Job, lcm_time: float, resolution: float = 1.0) -> List[float]:
    """Sample a profile for plots. Scoring uses phase boundaries instead."""
    validate_profile(job)
    if not math.isfinite(resolution) or resolution <= 0 or lcm_time <= 0:
        raise ValueError("Resolution and sample duration must be positive.")
    times = (np.arange(math.ceil(lcm_time / resolution)) * resolution - job.time_shift) % job.iteration_time
    ends = np.cumsum([p.duration for p in job.phases])
    indices = np.searchsorted(ends, times, side="right")
    return [job.phases[min(int(i), len(job.phases) - 1)].bandwidth_demand for i in indices]


def calculate_score(arrays: List[List[float]], link_capacity: float) -> float:
    """Score sampled arrays. Fractional boundaries need score_link instead."""
    if not math.isfinite(link_capacity) or link_capacity <= 0:
        raise ValueError("Link capacity must be finite and positive.")
    if not arrays or not len(arrays[0]):
        return 1.0
    total = np.sum(np.asarray(arrays, dtype=float), axis=0)
    return float(1 - np.maximum(0, total - link_capacity).mean() / link_capacity)


def score_link(jobs: List[Job], link: Link, horizon: Optional[float] = None,
               max_events: int = 200_000) -> float:
    """Integrate excess demand at every phase boundary.

    The default covers the full hyperperiod. An explicit horizon covers only
    [0, horizon); it is a finite-window estimate, not a periodic guarantee.
    Work above max_events is rejected, never silently truncated.
    """
    if not math.isfinite(link.capacity) or link.capacity <= 0:
        raise ValueError("Link capacity must be finite and positive.")
    if not jobs:
        return 1.0
    for job in jobs:
        validate_profile(job)
    duration = hyperperiod(jobs) if horizon is None else horizon
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Score horizon must be finite and positive.")
    event_bound = sum((math.ceil(duration / j.iteration_time) + 2) * len(j.phases) * 2 for j in jobs)
    if event_bound > max_events:
        raise ProfileLimitError(
            "The profile exceeds the event budget. Set an explicit score horizon "
            "for a finite-window estimate, or increase max_events.")
    events = {0.0: 0.0, duration: 0.0}
    for job in jobs:
        period = job.iteration_time
        offset = job.time_shift % period
        for cycle in range(-1, math.ceil(duration / period) + 1):
            start = offset + cycle * period
            for phase in job.phases:
                end = start + phase.duration
                left, right = max(0.0, start), min(duration, end)
                if right > left and phase.bandwidth_demand:
                    events[left] = events.get(left, 0.0) + phase.bandwidth_demand
                    events[right] = events.get(right, 0.0) - phase.bandwidth_demand
                start = end
    demand, excess, previous = 0.0, 0.0, 0.0
    for time, delta in sorted(events.items()):
        excess += max(0.0, demand - link.capacity) * (time - previous)
        demand += delta
        previous = time
    return 1.0 - excess / (duration * link.capacity)


def optimize_link(jobs: List[Job], link: Link, resolution: float = 1.0,
                  horizon: Optional[float] = None, method: str = "greedy",
                  max_trials: int = 20_000) -> None:
    """Hold the first job at zero and greedily search each later job's grid.

    method="exact" searches all relative grid combinations, with the first
    job fixed at zero. method="greedy" fixes each job in sequence. Both modes
    stop with an error when their explicit trial budget is exceeded.
    """
    if method not in ("greedy", "exact"):
        raise ValueError("Shift solver must be greedy or exact.")
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("Resolution must be finite and positive.")
    for job in jobs:
        validate_profile(job)
    if len(jobs) < 2:
        return
    score_link(jobs, link, horizon)
    counts = [math.ceil(j.iteration_time / resolution) for j in jobs[1:]]
    trials = math.prod(counts) if method == "exact" else sum(counts)
    if trials > max_trials:
        raise ProfileLimitError(
            f"The {method} shift search needs {trials} trials; the limit is {max_trials}. "
            "Increase resolution, use fewer jobs, or select the greedy solver explicitly.")
    jobs[0].time_shift = 0.0
    if method == "exact":
        best_score, best_shifts = -math.inf, None
        for combination in itertools.product(*(range(count) for count in counts)):
            for job, step in zip(jobs[1:], combination):
                job.time_shift = step * resolution
            score = score_link(jobs, link, horizon)
            if score > best_score + 1e-12:
                best_score, best_shifts = score, combination
            if score >= 1.0 - 1e-12:
                break
        for job, step in zip(jobs[1:], best_shifts):
            job.time_shift = step * resolution
        return
    for index, job in enumerate(jobs[1:], 1):
        best_score, best_shift = -math.inf, 0.0
        for step in range(counts[index - 1]):
            job.time_shift = step * resolution
            score = score_link(jobs[:index + 1], link, horizon)
            if score > best_score + 1e-12:
                best_score, best_shift = score, job.time_shift
            if score >= 1.0 - 1e-12:
                break
        job.time_shift = best_shift

