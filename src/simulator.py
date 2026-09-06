import heapq
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from src.models import Job, Cluster
from src.evaluator import generate_mock_candidates, evaluate_placements

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
