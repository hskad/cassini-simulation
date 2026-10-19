"""Phase events and a fluid network model. Time is in ms; rates are in Gbps."""
import heapq
import hashlib
import math
import warnings
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

from src.core.models import Job, Link, Cluster
from src.math_engine.optimizer import optimize_link, score_link, validate_profile
from src.scheduler.evaluator import PlacementCandidate, evaluate_placements

EPS = 1e-9


@dataclass(order=True)
class Event:
    time: float
    event_type: str = field(compare=False)
    job: Job = field(compare=False)
    sequence: int = 0


@dataclass
class JobState:
    job: Job
    links: Tuple[str, ...]
    phase_index: int = 0
    iteration: int = 0
    mode: str = "new"
    remaining: float = 0.0
    ready_time: float = 0.0
    origin: float = 0.0
    pending_alignment: bool = True
    wait_reason: str = "initial shift"
    wait_time: float = 0.0
    correct_drift: bool = False
    drift_checked: bool = False


def eval_link_compatibility(jobs: List[Job], link: Link, optimize: bool = True,
                            horizon: Optional[float] = None) -> Tuple[float, float]:
    """Preserve incumbent shifts and search only the arriving job's shift."""
    copies = [replace(j) for j in jobs]
    if optimize and len(copies) > 1:
        arriving = copies[-1]
        best_score, best_shift = -math.inf, 0.0
        for step in range(math.ceil(arriving.iteration_time)):
            arriving.time_shift = float(step)
            score = score_link(copies, link, horizon)
            if score > best_score + EPS:
                best_score, best_shift = score, float(step)
        arriving.time_shift = best_shift
    return score_link(copies, link, horizon), copies[-1].time_shift if copies else 0.0


def allocate_bandwidth(states: Dict[str, JobState], capacities: Dict[str, float]) -> Dict[str, float]:
    """Progressive filling with a demand cap and all path constraints."""
    demands = {jid: s.job.phases[s.phase_index].bandwidth_demand
               for jid, s in states.items() if s.mode == "phase"
               and s.job.phases[s.phase_index].bandwidth_demand > 0}
    rates = {jid: 0.0 for jid in demands}
    unfrozen = set(demands)
    while unfrozen:
        residual = {lid: capacity - sum(rates[jid] for jid in rates if lid in states[jid].links)
                    for lid, capacity in capacities.items()}
        counts = {lid: sum(lid in states[jid].links for jid in unfrozen) for lid in capacities}
        delta = min([demands[jid] - rates[jid] for jid in unfrozen] +
                    [max(0.0, residual[lid]) / count for lid, count in counts.items() if count])
        for jid in unfrozen:
            rates[jid] += delta
        saturated = {lid for lid, count in counts.items()
                     if count and residual[lid] - delta * count <= EPS}
        frozen = {jid for jid in unfrozen if demands[jid] - rates[jid] <= EPS
                  or any(lid in saturated for lid in states[jid].links)}
        if not frozen:
            raise RuntimeError("Bandwidth allocation did not converge.")
        unfrozen -= frozen
    return rates


class Simulator:
    def __init__(self, base_cluster: Cluster, penalty_factor: Optional[float] = None,
                 use_cassini: bool = True, incremental: bool = False, *,
                 record_history: bool = False, score_horizon: Optional[float] = None,
                 resolution: float = 1.0, compute_jitter: float = 0.0,
                 seed: int = 42, drift_threshold: Optional[float] = 0.05):
        if penalty_factor is not None:
            warnings.warn("penalty_factor is obsolete. Link capacity now determines communication time.",
                          DeprecationWarning, stacklevel=2)
        if not math.isfinite(compute_jitter) or not 0 <= compute_jitter < 1:
            raise ValueError("Compute jitter must be in [0, 1).")
        if drift_threshold is not None and (not math.isfinite(drift_threshold) or not 0 < drift_threshold < 0.5):
            raise ValueError("Drift threshold must be in (0, 0.5), or None.")
        self.compute_jitter = compute_jitter
        self.seed = seed
        self.drift_threshold = drift_threshold
        self.drift_history = []
        self.adjustments = []
        self.base_cluster = base_cluster
        self.use_cassini = use_cassini
        self.incremental = incremental  # Kept for callers; paths now stay fixed in both modes.
        self.record_history = record_history
        self.score_horizon = score_horizon
        self.resolution = resolution
        self.events: List[Event] = []
        self.active_jobs: Dict[str, Job] = {}
        self.states: Dict[str, JobState] = {}
        self.current_time = 0.0
        self.completed_jobs: List[Dict] = []
        self.phase_history: List[Dict] = []
        self.link_history: List[Dict] = []
        self.schedule_history: List[Dict] = []
        self.job_to_link: Dict[str, str] = {}
        self.job_to_links: Dict[str, Tuple[str, ...]] = {}
        self._ids = set()
        self._last_segment = {}
        self.capacities = {link.link_id: link.capacity for link in base_cluster.links}
        if len(self.capacities) != len(base_cluster.links):
            raise ValueError("Link IDs must be unique.")
        if any(not math.isfinite(c) or c <= 0 for c in self.capacities.values()):
            raise ValueError("Link capacity must be finite and positive.")
        self.link_totals = {lid: {"served_work_gbps_ms": 0.0, "overcapacity_time_ms": 0.0, "busy_time_ms": 0.0}
                            for lid in self.capacities}
        self._routes = {}
        for lid, jobs in base_cluster.link_jobs.items():
            if lid not in self.capacities:
                raise ValueError("A route refers to an unknown link.")
            for job in jobs:
                if lid in self._routes.setdefault(job.job_id, []):
                    raise ValueError("A job route contains a duplicate link.")
                self._routes[job.job_id].append(lid)
        self.active_cluster = Cluster(base_cluster.servers, base_cluster.links,
                                      {lid: [] for lid in self.capacities})

    def add_job_arrival(self, job: Job):
        validate_profile(job)
        if job.job_id in self._ids:
            raise ValueError("Job IDs must be unique.")
        if not math.isfinite(job.arrival_time) or job.arrival_time < self.current_time:
            raise ValueError("Arrival time must be finite and cannot be in the past.")
        if isinstance(job.total_iterations, bool) or not isinstance(job.total_iterations, int) or job.total_iterations <= 0:
            raise ValueError("Iteration count must be a positive integer.")
        if job.time_shift < 0:
            raise ValueError("Initial time shift cannot be negative.")
        if not self.capacities and any(p.bandwidth_demand for p in job.phases):
            raise ValueError("A job with network traffic needs a link.")
        self._ids.add(job.job_id)
        heapq.heappush(self.events, Event(job.arrival_time, "arrival", job, len(self._ids)))

    def _admit(self, job):
        links = tuple(self._routes.get(job.job_id, ()))
        if not links and self.capacities:
            lid = min(self.capacities, key=lambda l: (len(self.active_cluster.link_jobs[l]), l))
            links = (lid,)
        self.active_jobs[job.job_id] = job
        self.states[job.job_id] = JobState(job, links, origin=job.arrival_time + job.time_shift)
        self.job_to_links[job.job_id] = links
        if links:
            self.job_to_link[job.job_id] = links[0]
        for lid in links:
            self.active_cluster.link_jobs[lid].append(job)

    def _plan(self):
        if not self.use_cassini or not self.states:
            return
        candidate = PlacementCandidate("fixed routes", self.active_cluster)
        _, shifts = evaluate_placements([candidate], horizon=self.score_horizon, resolution=self.resolution)
        planned = {jid: replace(state.job, time_shift=shifts.get(jid, state.job.time_shift))
                   for jid, state in self.states.items()}
        link_scores = {link.link_id: score_link(
            [planned[j.job_id] for j in self.active_cluster.link_jobs[link.link_id]], link, self.score_horizon)
            for link in self.base_cluster.links}
        for jid, state in self.states.items():
            shared = [lid for lid in state.links if len(self.active_cluster.link_jobs[lid]) > 1]
            state.correct_drift = bool(shared) and all(link_scores[lid] >= 1 - EPS for lid in shared)
            if jid in shifts:
                state.origin = self.current_time + shifts[jid]
                state.pending_alignment = True
                state.job.time_shift = shifts[jid]
            elif state.mode != "new":
                state.pending_alignment = False
        if self.record_history:
            self.schedule_history.append({"time": self.current_time, "shifts": shifts,
                                          "score_horizon_ms": self.score_horizon,
                                          "link_scores": link_scores})

    def _complete(self, jid):
        state = self.states.pop(jid)
        job = self.active_jobs.pop(jid)
        self.completed_jobs.append({
            "job_id": jid, "name": job.name, "arrival_time": job.arrival_time,
            "completion_time": self.current_time,
            "turnaround_time": self.current_time - job.arrival_time,
            "wait_time": state.wait_time,
        })
        for lid in state.links:
            self.active_cluster.link_jobs[lid] = [j for j in self.active_cluster.link_jobs[lid] if j.job_id != jid]

    def _finish_phases(self):
        departed = False
        for jid, state in list(self.states.items()):
            if state.mode != "phase" or state.remaining > EPS:
                continue
            state.phase_index += 1
            state.mode = "new"
            state.drift_checked = False
            if state.phase_index == len(state.job.phases):
                state.phase_index = 0
                state.iteration += 1
                if state.iteration == state.job.total_iterations:
                    self._complete(jid)
                    departed = True
        return departed

    def _compute_duration(self, state):
        phase = state.job.phases[state.phase_index]
        if phase.type != "compute" or phase.bandwidth_demand or not self.compute_jitter:
            return phase.duration
        # Index noise by job and iteration. Policies receive the same noise.
        key = f"{self.seed}:{state.job.job_id}:{state.iteration}:{state.phase_index}".encode()
        uniform = int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big") / 2**64
        return phase.duration * (1 + self.compute_jitter * (2 * uniform - 1))

    def _enter_phase(self, state):
        if state.phase_index == 0 and state.pending_alignment:
            delay = state.origin - self.current_time
            if delay < -EPS:
                delay %= state.job.iteration_time
            state.pending_alignment = False
            if delay > EPS:
                state.mode = "wait"
                state.ready_time = self.current_time + delay
                state.wait_reason = "phase alignment"
                return
        phase = state.job.phases[state.phase_index]
        if phase.bandwidth_demand and not state.drift_checked:
            state.drift_checked = True
            offset = sum(p.duration for p in state.job.phases[:state.phase_index])
            ideal = state.origin + state.iteration * state.job.iteration_time + offset
            error = math.remainder(self.current_time - ideal, state.job.iteration_time)
            observation = {"job_id": state.job.job_id, "iteration": state.iteration,
                           "phase_index": state.phase_index, "time": self.current_time,
                           "period_ms": state.job.iteration_time,
                           "error_ms": self.current_time - ideal, "phase_error_ms": error}
            if self.record_history:
                self.drift_history.append(observation)
            if (self.use_cassini and state.correct_drift and self.drift_threshold is not None
                    and abs(error) > self.drift_threshold * state.job.iteration_time + EPS):
                # Delay to the next occurrence of this phase's nominal start.
                delay = (-error) % state.job.iteration_time
                self.adjustments.append(dict(observation, delay_ms=delay))
                state.mode = "wait"
                state.ready_time = self.current_time + delay
                state.wait_reason = "drift correction"
                return
        duration = self._compute_duration(state)
        state.remaining = duration * (phase.bandwidth_demand or 1.0)
        state.mode = "phase"

    def _activate(self):
        for state in self.states.values():
            if state.mode == "wait" and state.ready_time <= self.current_time + EPS:
                state.mode = "new"
            if state.mode == "new":
                self._enter_phase(state)

    def _record(self, jid, state, start, end, rate):
        phase = state.job.phases[state.phase_index]
        entry = {"job_id": jid, "iteration": state.iteration,
                 "phase_index": state.phase_index, "type": "wait" if state.mode == "wait" else phase.type,
                 "start": start, "end": end, "rate_gbps": rate,
                 "demand_gbps": 0.0 if state.mode == "wait" else phase.bandwidth_demand,
                 "links": list(state.links),
                 "reason": state.wait_reason if state.mode == "wait" else ""}
        old = self._last_segment.get(jid)
        keys = ("iteration", "phase_index", "type", "rate_gbps", "reason")
        if old and abs(old["end"] - start) <= EPS and all(old[k] == entry[k] for k in keys):
            old["end"] = end
        else:
            self.phase_history.append(entry)
            self._last_segment[jid] = entry

    def _advance(self, end, rates):
        dt = end - self.current_time
        if dt <= 0:
            raise RuntimeError("The event clock did not advance.")
        for jid, state in self.states.items():
            phase = state.job.phases[state.phase_index]
            rate = rates.get(jid, 0.0)
            if state.mode == "phase":
                state.remaining = max(0.0, state.remaining - dt * (rate if phase.bandwidth_demand else 1.0))
            elif state.mode == "wait":
                state.wait_time += dt
            if self.record_history:
                self._record(jid, state, self.current_time, end, rate)
        for lid, capacity in self.capacities.items():
            demand = sum(s.job.phases[s.phase_index].bandwidth_demand for s in self.states.values()
                         if s.mode == "phase" and lid in s.links)
            served = sum(rate for jid, rate in rates.items() if lid in self.states[jid].links)
            totals = self.link_totals[lid]
            totals["served_work_gbps_ms"] += served * dt
            totals["overcapacity_time_ms"] += dt if demand > capacity + EPS else 0.0
            totals["busy_time_ms"] += dt if served > EPS else 0.0
            if self.record_history:
                self.link_history.append({"link_id": lid, "start": self.current_time, "end": end,
                                          "demand_gbps": demand, "served_gbps": served,
                                          "capacity_gbps": capacity})
        self.current_time = end

    def run_simulation(self):
        while self.events or self.states:
            changed = self._finish_phases()
            while self.events and self.events[0].time <= self.current_time:
                self._admit(heapq.heappop(self.events).job)
                changed = True
            if changed:
                self._plan()
            self._activate()
            if not self.states and not self.events:
                break
            rates = allocate_bandwidth(self.states, self.capacities)
            times = [self.events[0].time] if self.events else []
            for jid, state in self.states.items():
                if state.mode == "wait":
                    times.append(state.ready_time)
                elif state.mode == "phase":
                    demand = state.job.phases[state.phase_index].bandwidth_demand
                    speed = rates[jid] if demand else 1.0
                    times.append(self.current_time + state.remaining / speed)
            self._advance(min(times), rates)

