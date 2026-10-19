import heapq
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from src.core.models import Job, Link, Cluster
from src.scheduler.evaluator import PlacementCandidate, generate_mock_candidates, evaluate_placements
from src.math_engine.optimizer import DEFAULT_SCORE_WINDOW_MS, get_score_window, optimize_link, score_link

@dataclass(order=True)
class Event:
    time: float
    event_type: str = field(compare=False) # 'arrival' or 'completion'
    job: Job = field(compare=False)

def eval_link_compatibility(jobs: List[Job], link: Link, optimize: bool = True, *,
                            score_window_ms: float = DEFAULT_SCORE_WINDOW_MS) -> Tuple[float, float]:
    """
    Evaluates compatibility score of a link with a set of jobs.
    Returns (compatibility_score, optimal_shift_for_last_job).
    """
    score, shifts = _link_plan(jobs, link, optimize, score_window_ms=score_window_ms)
    return score, (shifts.get(jobs[-1].job_id, 0.0) if jobs else 0.0)


def _link_plan(jobs: List[Job], link: Link, optimize: bool, *,
               score_window_ms: float) -> Tuple[float, Dict[str, float]]:
    """Return the score and the complete shift plan used to calculate it."""
    jobs_copy = [Job(j.job_id, j.name, j.phases, j.time_shift if optimize else 0.0)
                 for j in jobs]
    if optimize:
        optimize_link(jobs_copy, link, score_window_ms=score_window_ms)
    score = score_link(jobs_copy, link, score_window_ms=score_window_ms) if len(jobs) > 1 else 1.0
    return score, {j.job_id: j.time_shift for j in jobs_copy}

class Simulator:
    def __init__(self, base_cluster: Cluster, penalty_factor: float = 1.0, use_cassini: bool = True, incremental: bool = False, *,
                 score_window_ms: float = DEFAULT_SCORE_WINDOW_MS,
                 fixed_placement: Optional[Dict[str, str]] = None):
        get_score_window([], score_window_ms=score_window_ms)
        self.fixed_placement = dict(fixed_placement) if fixed_placement is not None else None
        if self.fixed_placement is not None:
            link_ids = {link.link_id for link in base_cluster.links}
            if any(link not in link_ids for link in self.fixed_placement.values()):
                raise ValueError("Fixed placement references an unknown link.")
        self.base_cluster = base_cluster
        self.score_window_ms = score_window_ms
        self.penalty_factor = penalty_factor
        self.use_cassini = use_cassini
        self.incremental = incremental
        self.events: List[Event] = []
        self.active_jobs: Dict[str, Job] = {}
        self.current_time: float = 0.0
        self.completed_jobs: List[Dict] = []
        self.job_to_link: Dict[str, str] = {}
        
        # Track active placement
        self.active_cluster = Cluster(
            servers=base_cluster.servers,
            links=base_cluster.links,
            link_jobs={link.link_id: [] for link in base_cluster.links}
        )

    def add_job_arrival(self, job: Job):
        if self.fixed_placement is not None and job.job_id not in self.fixed_placement:
            raise ValueError(f"Fixed placement has no link for job {job.job_id!r}.")
        heapq.heappush(self.events, Event(time=job.arrival_time, event_type='arrival', job=job))
        
    def run_simulation(self):
        # State tracking
        progress: Dict[str, float] = {}
        expected_completion: Dict[str, float] = {}
        effective_iteration_time: Dict[str, float] = {}
        pending_wait: Dict[str, float] = {}
        total_wait: Dict[str, float] = {}
        applied_shift: Dict[str, float] = {}

        def apply_shifts(shifts):
            for jid, shift in shifts.items():
                job = self.active_jobs[jid]
                target = shift % job.iteration_time if self.use_cassini else 0.0
                # A phase can only move forward in time. Reusing the same
                # target adds no wait; a lower target wraps to the next cycle.
                delay = (target - applied_shift[jid]) % job.iteration_time
                pending_wait[jid] += delay
                total_wait[jid] += delay
                applied_shift[jid] = target
                job.time_shift = target

        def completion_time(jid):
            work = effective_iteration_time[jid] * self.active_jobs[jid].total_iterations
            return self.current_time + pending_wait[jid] + max(0.0, 1.0 - progress[jid]) * work
        
        while self.events or self.active_jobs:
            next_arrival_time = self.events[0].time if self.events else float('inf')
            next_completion_time = min(expected_completion.values()) if expected_completion else float('inf')
            
            if next_arrival_time == float('inf') and next_completion_time == float('inf'):
                break
                
            next_time = min(next_arrival_time, next_completion_time)
            
            # Fast-forward time
            dt = next_time - self.current_time
            if dt > 0:
                for jid in self.active_jobs:
                    total_time_required = effective_iteration_time[jid] * self.active_jobs[jid].total_iterations
                    waited = min(dt, pending_wait[jid])
                    pending_wait[jid] -= waited
                    progress[jid] += (dt - waited) / total_time_required
                self.current_time = next_time

            # -------------------------------------------------------------
            # Incremental Placement Mode (Production Datacenter Model)
            # -------------------------------------------------------------
            if self.incremental:
                # Handle Completions
                completed_this_tick = []
                for jid, comp_time in list(expected_completion.items()):
                    if abs(comp_time - self.current_time) < 1e-6:
                        completed_this_tick.append(jid)
                        
                for jid in completed_this_tick:
                    job = self.active_jobs.pop(jid)
                    del progress[jid]
                    del expected_completion[jid]
                    del effective_iteration_time[jid]
                    del pending_wait[jid]
                    del applied_shift[jid]
                    self.completed_jobs.append({
                        "job_id": job.job_id,
                        "link_id": (self.fixed_placement[jid] if self.fixed_placement is not None
                                    else self.job_to_link.get(jid)),
                        "name": job.name,
                        "arrival_time": job.arrival_time,
                        "completion_time": self.current_time,
                        "turnaround_time": self.current_time - job.arrival_time,
                        "shift_wait_ms": total_wait.pop(jid)
                    })
                    
                    # Remove from link and update remaining jobs on that link
                    link_id = self.job_to_link.pop(jid, None)
                    if link_id:
                        rem_jobs = [j for j in self.active_cluster.link_jobs[link_id] if j.job_id not in completed_this_tick]
                        self.active_cluster.link_jobs[link_id] = rem_jobs
                        link_obj = next(l for l in self.base_cluster.links if l.link_id == link_id)
                        score, shifts = _link_plan(rem_jobs, link_obj, optimize=self.use_cassini,
                                                   score_window_ms=self.score_window_ms)
                        apply_shifts(shifts)
                        slowdown = 1.0 + (1.0 - score) * self.penalty_factor
                        for rj in rem_jobs:
                            effective_iteration_time[rj.job_id] = rj.iteration_time * slowdown
                            expected_completion[rj.job_id] = completion_time(rj.job_id)

                # Handle Arrivals
                while self.events and self.events[0].time == next_time:
                    event = heapq.heappop(self.events)
                    job = event.job
                    self.active_jobs[job.job_id] = job
                    progress[job.job_id] = 0.0
                    pending_wait[job.job_id] = 0.0
                    total_wait[job.job_id] = 0.0
                    applied_shift[job.job_id] = 0.0
                    if not self.use_cassini:
                        job.time_shift = 0.0
                    
                    if self.fixed_placement is not None:
                        candidate_links = [link for link in self.base_cluster.links
                                           if link.link_id == self.fixed_placement[job.job_id]]
                    else:
                        # Legacy joint placement/shift search, used only when
                        # no shared placement map is supplied.
                        sorted_links = sorted(self.base_cluster.links,
                                              key=lambda link: len(self.active_cluster.link_jobs[link.link_id]))
                        candidate_links = sorted_links[:min(4, len(sorted_links))]

                    best_link = candidate_links[0]
                    # Heavy traffic can give every candidate a score below -1.
                    best_score = float('-inf')
                    best_shifts = {}
                    
                    for cand_link in candidate_links:
                        curr_link_jobs = self.active_cluster.link_jobs[cand_link.link_id]
                        test_jobs = curr_link_jobs + [job]
                        score, shifts = _link_plan(test_jobs, cand_link, optimize=self.use_cassini,
                                                           score_window_ms=self.score_window_ms)
                        if score > best_score:
                            best_score = score
                            best_shifts = shifts
                            best_link = cand_link
                            if score >= 1.0:
                                break
                                
                    apply_shifts(best_shifts)
                    self.active_cluster.link_jobs[best_link.link_id].append(job)
                    self.job_to_link[job.job_id] = best_link.link_id
                    
                    affected_jobs = self.active_cluster.link_jobs[best_link.link_id]
                    slowdown = 1.0 + (1.0 - best_score) * self.penalty_factor
                    for aj in affected_jobs:
                        effective_iteration_time[aj.job_id] = aj.iteration_time * slowdown
                        expected_completion[aj.job_id] = completion_time(aj.job_id)

            # -------------------------------------------------------------
            # Global Reshuffle Mode (Original Baseline for Small Mock Demos)
            # -------------------------------------------------------------
            else:
                placement_changed = False
                completed_this_tick = []
                for jid, comp_time in list(expected_completion.items()):
                    if abs(comp_time - self.current_time) < 1e-6:
                        completed_this_tick.append(jid)
                        
                for jid in completed_this_tick:
                    job = self.active_jobs.pop(jid)
                    del progress[jid]
                    del expected_completion[jid]
                    del effective_iteration_time[jid]
                    del pending_wait[jid]
                    del applied_shift[jid]
                    self.completed_jobs.append({
                        "job_id": job.job_id,
                        "link_id": (self.fixed_placement[jid] if self.fixed_placement is not None
                                    else self.job_to_link.get(jid)),
                        "name": job.name,
                        "arrival_time": job.arrival_time,
                        "completion_time": self.current_time,
                        "turnaround_time": self.current_time - job.arrival_time,
                        "shift_wait_ms": total_wait.pop(jid)
                    })
                    placement_changed = True
                    
                while self.events and self.events[0].time == next_time:
                    event = heapq.heappop(self.events)
                    job = event.job
                    self.active_jobs[job.job_id] = job
                    progress[job.job_id] = 0.0
                    pending_wait[job.job_id] = 0.0
                    total_wait[job.job_id] = 0.0
                    applied_shift[job.job_id] = 0.0
                    if not self.use_cassini:
                        job.time_shift = 0.0
                    placement_changed = True
                    
                if placement_changed and self.active_jobs:
                    jobs_list = list(self.active_jobs.values())
                    if self.fixed_placement is not None:
                        link_jobs = {link.link_id: [] for link in self.base_cluster.links}
                        for job in jobs_list:
                            link_jobs[self.fixed_placement[job.job_id]].append(job)
                        candidates = [PlacementCandidate("fixed", Cluster(
                            self.base_cluster.servers, self.base_cluster.links, link_jobs))]
                    else:
                        candidates = generate_mock_candidates(
                            self.base_cluster, jobs_list, num_candidates=5 if self.use_cassini else 1)
                    if self.use_cassini:
                        try:
                            winning_candidate, shifts = evaluate_placements(candidates, score_window_ms=self.score_window_ms)
                            self.active_cluster = winning_candidate.cluster
                            score = winning_candidate.compatibility_score
                        except ValueError:
                            score = 0.0
                            shifts = {}
                    else:
                        from src.scheduler.evaluator import score_candidate
                        winning_candidate = candidates[0]
                        self.active_cluster = winning_candidate.cluster
                        score, _ = score_candidate(winning_candidate, optimize=False,
                                                   score_window_ms=self.score_window_ms)
                        
                    if self.use_cassini:
                        apply_shifts(shifts)
                    slowdown_factor = 1.0 + (1.0 - score) * self.penalty_factor
                    for jid, job in self.active_jobs.items():
                        effective_iteration_time[jid] = job.iteration_time * slowdown_factor
                        expected_completion[jid] = completion_time(jid)


