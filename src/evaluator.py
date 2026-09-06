import random
from dataclasses import dataclass
from typing import Dict, List, Tuple
from src.models import Cluster, Job, Link
from src.graph import AffinityGraph, build_affinity_graph, traverse_affinity_graph
from src.optimizer import optimize_link, calculate_score, discretize_phases, lcm

@dataclass
class PlacementCandidate:
    candidate_id: str
    cluster: Cluster
    compatibility_score: float = 0.0
