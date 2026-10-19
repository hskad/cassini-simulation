"""Constructed input cases with explicit phase timings and fixed routes."""
import math
import random

from src.core.models import Cluster, Job, Link, Phase


def compatible_workload(seed=42, capacity=50.0, iterations=None):
    """Build a deliberately favorable example of periodic burst interleaving.

    Each link carries eight jobs with seven compute slots and one transfer slot.
    All arrivals are at zero. Only iteration counts are random, from 200 to 400.
    These profiles are synthetic; they do not represent measured model timings.
    """
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError("Link capacity must be finite and positive.")
    if iterations is not None and (not isinstance(iterations, int) or iterations <= 0):
        raise ValueError("Use a positive iteration count.")
    rng = random.Random(seed)
    jobs, links, routes, profiles = [], [], {}, []
    for group, slot in enumerate([5, 8, 10, 12, 15, 20, 25], 1):
        link = Link(f"L{group}", capacity)
        links.append(link)
        profile = f"Period {8*slot} ms"
        members = [Job(f"compatible-{group:02}-{index:02}", profile,
            [Phase("compute", 7*slot, 0), Phase("communicate", slot, capacity)],
            total_iterations=iterations if iterations is not None else rng.randint(200, 400))
            for index in range(8)]
        routes[link.link_id] = members
        jobs.extend(members)
        profiles.append({"name": profile, "compute_ms": 7*slot,
                         "communication_ms": slot, "period_ms": 8*slot, "jobs": 8})
    metadata = {"kind": "synthetic", "generator": "src/workloads.py::compatible_workload",
        "design": "constructed favorable case for phase interleaving; not a datacenter trace",
        "seed": seed, "jobs": len(jobs), "links": len(links), "jobs_per_link": 8,
        "capacity_gbps": capacity, "arrival_span_ms": 0,
        "iteration_range": [200, 400] if iterations is None else [iterations, iterations],
        "profile_source": "assumed synthetic timings; no measured model names", "profiles": profiles}
    return jobs, Cluster([], links, routes), metadata


def check_compatible_completion(cluster, sim, coordinated):
    """Check completion times against independent formulas for this input case."""
    completed = {row["job_id"]: row for row in sim.completed_jobs}
    for members in cluster.link_jobs.values():
        for index, job in enumerate(sorted(members, key=lambda member: member.job_id)):
            compute, comm = (phase.duration for phase in job.phases)
            if coordinated:
                expected = job.total_iterations * (compute + comm) + index * comm
            else:
                expected = compute * job.total_iterations + comm * sum(
                    min(job.total_iterations, other.total_iterations) for other in members)
            row = completed[job.job_id]
            if not math.isclose(row["turnaround_time"], expected, rel_tol=1e-9, abs_tol=1e-6):
                raise ValueError("The compatible workload differs from its analytical completion time.")
            expected_wait = index * comm if coordinated else 0
            if not math.isclose(row["wait_time"], expected_wait, rel_tol=1e-9, abs_tol=1e-6):
                raise ValueError("The compatible workload has an unexpected waiting cost.")
