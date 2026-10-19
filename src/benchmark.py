"""Matched phase-scheduling experiments with analytical and conservation checks."""
import copy
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass

import numpy as np

from src.core.models import Cluster, Job, Link, Phase
from src.core.trace_loader import TraceLoader
from src.scheduler.simulator import Simulator


POLICIES = (("uncoordinated", False, None), ("static-shifts", True, None),
            ("cassini", True, 0.05))


@dataclass
class BenchmarkCase:
    name: str
    jobs: list
    cluster: Cluster
    seed: int = 0
    jitter: float = 0.0


def benchmark_cases(iterations=100, seeds=(0, 1, 2, 3, 4)):
    if iterations <= 0 or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Use positive iterations and distinct noise seeds.")

    def job(jid, compute=50, comm=50, arrival=0):
        return Job(jid, jid, [Phase("compute", compute, 0), Phase("communicate", comm, 50)],
                   arrival_time=arrival, total_iterations=iterations)

    def pair(name, **options):
        jobs = [job("A"), job("B", **options)]
        return BenchmarkCase(name, jobs, Cluster([], [Link("L", 50)], {"L": jobs}))

    yield pair("aligned-pair")
    profile = TraceLoader().models["VGG-16"]
    jobs = [profile.to_job(jid, total_iterations=iterations, bandwidth_gbps=50) for jid in ["A", "B"]]
    yield BenchmarkCase("vgg-timing-profile", jobs, Cluster([], [Link("L", 50)], {"L": jobs}))
    yield pair("already-aligned", arrival=50)
    jobs = [job(jid, 80, 20) for jid in ["A", "B", "C"]]
    yield BenchmarkCase("multi-link", jobs, Cluster([], [Link("L1", 50), Link("L2", 50)],
        {"L1": jobs[:2], "L2": jobs[1:]}))
    jobs = [job(jid, 30, 70) for jid in ["A", "B"]]
    yield BenchmarkCase("overloaded-link", jobs, Cluster([], [Link("L", 50)], {"L": jobs}))
    jobs = [job("A", 30, 10), job("B", 50, 10)]
    yield BenchmarkCase("mixed-periods", jobs, Cluster([], [Link("L", 50)], {"L": jobs}))
    jobs = [job("A"), job("B")]
    yield BenchmarkCase("separate-links", jobs, Cluster([], [Link("L1", 50), Link("L2", 50)],
        {"L1": jobs[:1], "L2": jobs[1:]}))
    for seed in seeds:
        case = pair("compute-jitter")
        case.seed, case.jitter = seed, 0.04
        yield case


def audit_run(case, sim):
    """Check delivered work, capacity limits, and the full time of every job."""
    delivered, elapsed, compute, waits = (defaultdict(float) for _ in range(4))
    for event in sim.phase_history:
        duration = event["end"] - event["start"]
        jid = event["job_id"]
        delivered[jid] += duration * event["rate_gbps"]
        elapsed[jid] += duration
        if event["type"] == "compute":
            compute[jid] += duration
        if event["type"] == "wait":
            waits[event["reason"]] += duration
        if duration < 0 or event["rate_gbps"] > event["demand_gbps"] + 1e-8:
            raise ValueError("A phase has invalid time or exceeds its demand cap.")
    completed = {row["job_id"]: row for row in sim.completed_jobs}
    if set(completed) != {job.job_id for job in case.jobs}:
        raise ValueError("The completed jobs differ from the input jobs.")
    for job in case.jobs:
        expected = job.total_iterations * sum(p.duration * p.bandwidth_demand for p in job.phases)
        if not math.isclose(delivered[job.job_id], expected, rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError("Delivered network work differs from the input work.")
        if not math.isclose(elapsed[job.job_id], completed[job.job_id]["turnaround_time"],
                            rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError("Completion time omits phase time or waiting time.")
    for event in sim.link_history:
        if event["served_gbps"] > event["capacity_gbps"] + 1e-8:
            raise ValueError("Served bandwidth exceeds link capacity.")
    for lid, jobs in case.cluster.link_jobs.items():
        expected = sum(delivered[job.job_id] for job in jobs)
        if not math.isclose(sim.link_totals[lid]["served_work_gbps_ms"], expected,
                            rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError("Link totals do not conserve routed network work.")
    expected_routes = {job.job_id: tuple(link.link_id for link in case.cluster.links
        if job in case.cluster.link_jobs.get(link.link_id, [])) for job in case.jobs}
    if sim.job_to_links != expected_routes:
        raise ValueError("The simulation changed the fixed input routes.")
    return dict(compute), {reason: value / len(case.jobs) for reason, value in waits.items()}


def run_benchmarks(iterations=100, seeds=(0, 1, 2, 3, 4)):
    rows, workloads, runs = [], [], []
    for case in benchmark_cases(iterations, seeds):
        print(f"Benchmark: {case.name}, seed {case.seed}", flush=True)
        inputs = {"case": case.name, "seed": case.seed, "jitter": case.jitter,
                  "jobs": [asdict(job) for job in case.jobs],
                  "links": [asdict(link) for link in case.cluster.links],
                  "routes": {lid: [job.job_id for job in jobs]
                             for lid, jobs in case.cluster.link_jobs.items()}}
        digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        workloads.append(dict(inputs, workload_sha256=digest))
        baseline_mean, baseline_compute = None, None
        for policy, enabled, threshold in POLICIES:
            sim = Simulator(case.cluster, use_cassini=enabled, record_history=True,
                compute_jitter=case.jitter, seed=case.seed, drift_threshold=threshold)
            for job in copy.deepcopy(case.jobs):
                sim.add_job_arrival(job)
            sim.run_simulation()
            compute, waits = audit_run(case, sim)
            times = [row["turnaround_time"] for row in sim.completed_jobs]
            mean = float(np.mean(times))
            if baseline_mean is None:
                baseline_mean, baseline_compute = mean, compute
            elif any(not math.isclose(value, baseline_compute[jid], abs_tol=1e-6)
                     for jid, value in compute.items()):
                raise ValueError("Policies received different compute work or noise.")
            # These formulas follow from alternating transfers at 50 Gbps.
            expected = None
            if case.name == "aligned-pair":
                expected = 150 * iterations if not enabled else 100 * iterations + 25
            elif case.name == "vgg-timing-profile":
                expected = 369 * iterations if not enabled else 255 * iterations + 57
            elif case.name == "multi-link":
                expected = 120 * iterations if not enabled else 100 * iterations + 20
            elif case.name in ("already-aligned", "separate-links"):
                expected = 100 * iterations
            if expected is not None and not math.isclose(mean, expected, abs_tol=1e-6):
                raise ValueError(f"{case.name}: mean JCT differs from the analytical result.")
            rows.append({"case": case.name, "seed": case.seed, "policy": policy,
                "jobs": len(case.jobs), "mean_jct_ms": mean,
                "p95_jct_ms": float(np.percentile(times, 95)),
                "mean_wait_ms": float(np.mean([row["wait_time"] for row in sim.completed_jobs])),
                "alignment_wait_ms": waits.get("phase alignment", 0),
                "correction_wait_ms": waits.get("drift correction", 0),
                "adjustments": len(sim.adjustments),
                "jct_reduction_percent": 100 * (1 - mean / baseline_mean),
                "workload_sha256": digest})
            runs.append({"case": case.name, "seed": case.seed, "policy": policy,
                "completions": sim.completed_jobs, "adjustments": sim.adjustments,
                "routes": sim.job_to_links, "link_totals": sim.link_totals})
    return rows, workloads, runs
