import heapq
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from src.core.models import Job, Cluster
from src.scheduler.evaluator import generate_mock_candidates, evaluate_placements

@dataclass(order=True)
class Event:
    time: float
    event_type: str = field(compare=False) # 'arrival' or 'completion'
    job: Job = field(compare=False)

class Simulator:
    def __init__(self, base_cluster: Cluster, penalty_factor: float = 1.0):
        self.base_cluster = base_cluster
        self.penalty_factor = penalty_factor
        self.events: List[Event] = []
        self.active_jobs: Dict[str, Job] = {}
        self.current_time: float = 0.0
        self.completed_jobs: List[Dict] = []
        
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
                    # Update progress based on the total time required
                    total_time_required = effective_iteration_time[jid] * self.active_jobs[jid].total_iterations
                    progress[jid] += dt / total_time_required
                self.current_time = next_time
                
            placement_changed = False
            
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
                placement_changed = True
                
            # Handle Arrivals
            while self.events and self.events[0].time == next_time:
                event = heapq.heappop(self.events)
                job = event.job
                self.active_jobs[job.job_id] = job
                progress[job.job_id] = 0.0
                placement_changed = True
                
            # Re-evaluate placements if cluster state changed
            if placement_changed and self.active_jobs:
                jobs_list = list(self.active_jobs.values())
                candidates = generate_mock_candidates(self.base_cluster, jobs_list, num_candidates=5)
                
                try:
                    winning_candidate, _ = evaluate_placements(candidates)
                    self.active_cluster = winning_candidate.cluster
                    score = winning_candidate.compatibility_score
                except ValueError:
                    # Fallback if no valid candidates (e.g., all have cycles)
                    score = 0.0
                    
                # Calculate slowdowns
                slowdown_factor = 1.0 + (1.0 - score) * self.penalty_factor
                
                for jid, job in self.active_jobs.items():
                    effective_iteration_time[jid] = job.iteration_time * slowdown_factor
                    
                    # Update expected completion time
                    total_time_required = effective_iteration_time[jid] * job.total_iterations
                    remaining_progress = max(0.0, 1.0 - progress[jid])
                    expected_completion[jid] = self.current_time + (remaining_progress * total_time_required)

