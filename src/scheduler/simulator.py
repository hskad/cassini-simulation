import heapq
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from src.core.models import Job, Link, Cluster
from src.scheduler.evaluator import generate_mock_candidates, evaluate_placements
from src.math_engine.optimizer import optimize_link, calculate_score, discretize_phases, lcm

@dataclass(order=True)
class Event:
    time: float
    event_type: str = field(compare=False) # 'arrival' or 'completion'
    job: Job = field(compare=False)

def eval_link_compatibility(jobs: List[Job], link: Link, optimize: bool = True) -> Tuple[float, float]:
    """
    Evaluates compatibility score of a link with a set of jobs.
    Returns (compatibility_score, optimal_shift_for_last_job).
    """
    if len(jobs) <= 1:
        return 1.0, 0.0
    jobs_copy = [Job(j.job_id, j.name, j.phases, j.time_shift) for j in jobs]
    if optimize:
        optimize_link(jobs_copy, link, resolution=1.0)
    opt_shift = jobs_copy[-1].time_shift if optimize else 0.0
    
    lcm_steps = int(jobs_copy[0].iteration_time)
    for j in jobs_copy[1:]:
        lcm_steps = lcm(lcm_steps, int(j.iteration_time))
    lcm_steps = min(lcm_steps, 1200)
    arrs = [discretize_phases(j, float(lcm_steps), 1.0) for j in jobs_copy]
    score = calculate_score(arrs, link.capacity)
    return score, opt_shift

class Simulator:
    def __init__(self, base_cluster: Cluster, penalty_factor: float = 1.0, use_cassini: bool = True, incremental: bool = False):
        self.base_cluster = base_cluster
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
        heapq.heappush(self.events, Event(time=job.arrival_time, event_type='arrival', job=job))
        
    def run_simulation(self):
        # State tracking
        progress: Dict[str, float] = {}
        expected_completion: Dict[str, float] = {}
        effective_iteration_time: Dict[str, float] = {}
        
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
                    progress[jid] += dt / total_time_required
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
                    self.completed_jobs.append({
                        "job_id": job.job_id,
                        "name": job.name,
                        "arrival_time": job.arrival_time,
                        "completion_time": self.current_time,
                        "turnaround_time": self.current_time - job.arrival_time
                    })
                    
                    # Remove from link and update remaining jobs on that link
                    link_id = self.job_to_link.pop(jid, None)
                    if link_id:
                        rem_jobs = [j for j in self.active_cluster.link_jobs[link_id] if j.job_id != jid]
                        self.active_cluster.link_jobs[link_id] = rem_jobs
                        link_obj = next(l for l in self.base_cluster.links if l.link_id == link_id)
                        score, _ = eval_link_compatibility(rem_jobs, link_obj, optimize=self.use_cassini)
                        slowdown = 1.0 + (1.0 - score) * self.penalty_factor
                        for rj in rem_jobs:
                            effective_iteration_time[rj.job_id] = rj.iteration_time * slowdown
                            total_req = effective_iteration_time[rj.job_id] * rj.total_iterations
                            rem_prog = max(0.0, 1.0 - progress[rj.job_id])
                            expected_completion[rj.job_id] = self.current_time + (rem_prog * total_req)

                # Handle Arrivals
                while self.events and self.events[0].time == next_time:
                    event = heapq.heappop(self.events)
                    job = event.job
                    self.active_jobs[job.job_id] = job
                    progress[job.job_id] = 0.0
                    
                    # Candidate links: evaluate top least-loaded links
                    sorted_links = sorted(self.base_cluster.links, key=lambda l: len(self.active_cluster.link_jobs[l.link_id]))
                    candidate_links = sorted_links[:min(4, len(sorted_links))]
                    
                    best_link = candidate_links[0]
                    best_score = -1.0
                    best_shift = 0.0
                    
                    for cand_link in candidate_links:
                        curr_link_jobs = self.active_cluster.link_jobs[cand_link.link_id]
                        test_jobs = curr_link_jobs + [job]
                        score, opt_shift = eval_link_compatibility(test_jobs, cand_link, optimize=self.use_cassini)
                        if score > best_score:
                            best_score = score
                            best_shift = opt_shift
                            best_link = cand_link
                            if score >= 1.0:
                                break
                                
                    job.time_shift = best_shift if self.use_cassini else 0.0
                    self.active_cluster.link_jobs[best_link.link_id].append(job)
                    self.job_to_link[job.job_id] = best_link.link_id
                    
                    affected_jobs = self.active_cluster.link_jobs[best_link.link_id]
                    slowdown = 1.0 + (1.0 - best_score) * self.penalty_factor
                    for aj in affected_jobs:
                        effective_iteration_time[aj.job_id] = aj.iteration_time * slowdown
                        total_req = effective_iteration_time[aj.job_id] * aj.total_iterations
                        rem_prog = max(0.0, 1.0 - progress[aj.job_id])
                        expected_completion[aj.job_id] = self.current_time + (rem_prog * total_req)

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
                    self.completed_jobs.append({
                        "job_id": job.job_id,
                        "name": job.name,
                        "arrival_time": job.arrival_time,
                        "completion_time": self.current_time,
                        "turnaround_time": self.current_time - job.arrival_time
                    })
                    placement_changed = True
                    
                while self.events and self.events[0].time == next_time:
                    event = heapq.heappop(self.events)
                    job = event.job
                    self.active_jobs[job.job_id] = job
                    progress[job.job_id] = 0.0
                    placement_changed = True
                    
                if placement_changed and self.active_jobs:
                    jobs_list = list(self.active_jobs.values())
                    if self.use_cassini:
                        candidates = generate_mock_candidates(self.base_cluster, jobs_list, num_candidates=5)
                        try:
                            winning_candidate, _ = evaluate_placements(candidates)
                            self.active_cluster = winning_candidate.cluster
                            score = winning_candidate.compatibility_score
                        except ValueError:
                            score = 0.0
                    else:
                        from src.scheduler.evaluator import score_candidate
                        candidates = generate_mock_candidates(self.base_cluster, jobs_list, num_candidates=1)
                        winning_candidate = candidates[0]
                        self.active_cluster = winning_candidate.cluster
                        score, _ = score_candidate(winning_candidate, optimize=False)
                        
                    slowdown_factor = 1.0 + (1.0 - score) * self.penalty_factor
                    for jid, job in self.active_jobs.items():
                        effective_iteration_time[jid] = job.iteration_time * slowdown_factor
                        total_time_required = effective_iteration_time[jid] * job.total_iterations
                        remaining_progress = max(0.0, 1.0 - progress[jid])
                        expected_completion[jid] = self.current_time + (remaining_progress * total_time_required)


