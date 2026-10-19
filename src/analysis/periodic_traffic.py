"""Integrate periodic bandwidth demand directly from phase boundary events.

This checker does not call the optimizer or construct sampled traffic arrays.
It models offered traffic, not network queues, transport, or job completion.
"""
import math
from typing import Sequence

from src.core.models import Job


def periodic_traffic(jobs: Sequence[Job], capacity: float, start_ms: float,
                     duration_ms: float):
    """Return exact offered-load metrics over a half-open finite interval.

    A positive time_shift delays every phase. Profiles repeat indefinitely.
    Each communication interval contributes a start and end event, including
    intervals which cross either evaluation boundary.
    """
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError("Capacity must be finite and positive.")
    if not math.isfinite(start_ms) or not math.isfinite(duration_ms) or duration_ms <= 0:
        raise ValueError("Evaluation interval must be finite and have positive duration.")
    end_ms = start_ms + duration_ms
    if not math.isfinite(end_ms) or end_ms <= start_ms:
        raise ValueError("Evaluation end must be finite and later than its start.")
    events = []
    for job in jobs:
        period = job.iteration_time
        if not math.isfinite(period) or period <= 0 or not math.isfinite(job.time_shift):
            raise ValueError("Periods must be positive and periods and shifts must be finite.")
        phase_start = job.time_shift % period
        for phase in job.phases:
            if (not math.isfinite(phase.duration) or phase.duration < 0
                    or not math.isfinite(phase.bandwidth_demand) or phase.bandwidth_demand < 0):
                raise ValueError("Phase durations and bandwidth must be finite and nonnegative.")
            if phase.bandwidth_demand > 0 and phase.duration > 0:
                first = math.floor((start_ms - phase_start - phase.duration) / period) + 1
                last = math.ceil((end_ms - phase_start) / period)
                for cycle in range(first, last):
                    begin = max(start_ms, phase_start + cycle * period)
                    end = min(end_ms, phase_start + cycle * period + phase.duration)
                    if end > begin:
                        events.append((begin, phase.bandwidth_demand))
                        events.append((end, -phase.bandwidth_demand))
            phase_start += phase.duration
    events.sort()
    demand, previous, excess_area, overloaded_ms, peak = 0.0, start_ms, 0.0, 0.0, 0.0
    index = 0
    while index < len(events):
        time = events[index][0]
        dt = time - previous
        excess_area += max(0.0, demand - capacity) * dt
        if demand > capacity:
            overloaded_ms += dt
        if dt > 0:
            peak = max(peak, demand)
        while index < len(events) and events[index][0] == time:
            demand += events[index][1]
            index += 1
        previous = time
    # Every positive interval ends with a matching end event inside the window.
    return {
        "score": 1.0 - excess_area / (duration_ms * capacity),
        "excess_area_gbps_ms": excess_area,
        "overloaded_fraction": overloaded_ms / duration_ms,
        "peak_demand_gbps": peak,
        "phase_boundary_events": len(events),
    }
