from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Phase:
    """Represents a slice of time in a job's iteration."""
    type: str  # "compute" (Up phase) or "communicate" (Down phase)
    duration: float  # Length of this phase in ms
    bandwidth_demand: float  # Network bandwidth required in Gbps

@dataclass
class Job:
    """Represents an ML training job."""
    job_id: str
    name: str
    phases: List[Phase]
    time_shift: float = 0.0  # The calculated delay for this job

    @property
    def iteration_time(self) -> float:
        """Computed automatically by summing the durations of its phases."""
        return sum(phase.duration for phase in self.phases)

@dataclass
class Link:
    """Represents a network link in the datacenter."""
    link_id: str
    capacity: float  # Maximum bandwidth in Gbps

@dataclass
class Server:
    """Represents a GPU server."""
    server_id: str
    gpu_count: int

@dataclass
class Cluster:
    """Represents the network topology."""
    servers: List[Server]
    links: List[Link]
    # Maps link_id to a list of Jobs routed through it
    link_jobs: Dict[str, List[Job]] = field(default_factory=dict)
