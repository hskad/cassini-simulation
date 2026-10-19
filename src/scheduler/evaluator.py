import random
from dataclasses import dataclass
from typing import Dict, List, Tuple
from src.core.models import Cluster, Job, Link
from src.math_engine.graph import build_affinity_graph, has_cycle, traverse_affinity_graph
from src.math_engine.optimizer import DEFAULT_SCORE_WINDOW_MS, optimize_link, score_link

@dataclass
class PlacementCandidate:
    candidate_id: str
    cluster: Cluster
    compatibility_score: float = 0.0

def make_fixed_placement(jobs: List[Job], links: List[Link], seed: int = 42) -> Dict[str, str]:
    """Choose each job's link once, without consulting runtime or shift policy."""
    link_ids = sorted(link.link_id for link in links)
    if not link_ids or len(link_ids) != len(set(link_ids)):
        raise ValueError("Fixed placement requires nonempty, uniquely named links.")
    ordered = sorted(jobs, key=lambda job: (job.arrival_time, job.job_id))
    if len({job.job_id for job in ordered}) != len(ordered):
        raise ValueError("Fixed placement requires unique job IDs.")
    rng = random.Random(seed)
    return {job.job_id: rng.choice(link_ids) for job in ordered}


def generate_mock_candidates(base_cluster: Cluster, jobs: List[Job], num_candidates: int = 5) -> List[PlacementCandidate]:
    """
    Simulates a scheduler (like Themis) by generating N placement candidates.
    Assigns jobs randomly to cluster links (representing their primary network path/bottleneck)
    to explore varied network placements while ensuring loop-free Affinity subgraphs.
    """
    candidates = []
    
    for i in range(num_candidates):
        # Create a new link_jobs mapping
        new_link_jobs = {link.link_id: [] for link in base_cluster.links}
        
        for job in jobs:
            # Assign job to a bottleneck link in the cluster
            chosen_link = random.choice(base_cluster.links)
            new_link_jobs[chosen_link.link_id].append(job)
                
        # Clone the cluster with the new placement
        new_cluster = Cluster(
            servers=base_cluster.servers,
            links=base_cluster.links,
            link_jobs=new_link_jobs
        )
        
        candidates.append(PlacementCandidate(
            candidate_id=f"candidate_{i+1}",
            cluster=new_cluster
        ))
        
    return candidates

def score_candidate(candidate: PlacementCandidate, optimize: bool = True, *,
                    score_window_ms: float = DEFAULT_SCORE_WINDOW_MS) -> Tuple[float, Dict[str, Dict[str, float]]]:
    """
    Evaluates a single placement candidate by running the link optimizer on all its links.
    Returns a tuple of (overall_compatibility_score, link_optimal_shifts).
    """
    total_score = 0.0
    num_links_scored = 0
    link_optimal_shifts: Dict[str, Dict[str, float]] = {}
    
    for link in candidate.cluster.links:
        jobs_on_link = candidate.cluster.link_jobs.get(link.link_id, [])
        if len(jobs_on_link) > 1:
            # Copy jobs to avoid mutating original objects globally
            jobs_copy = [Job(j.job_id, j.name, j.phases, j.time_shift) for j in jobs_on_link]
            
            if optimize:
                # optimize_link modifies time_shift in-place for jobs_copy
                optimize_link(jobs_copy, link, score_window_ms=score_window_ms)
            
            link_score = score_link(jobs_copy, link, score_window_ms=score_window_ms)
            
            total_score += link_score
            num_links_scored += 1
            
            # Record the optimal shifts for the affinity graph
            link_optimal_shifts[link.link_id] = {j.job_id: j.time_shift for j in jobs_copy}
            
    if num_links_scored == 0:
        return 1.0, {} # Perfect score if no links have >1 job
        
    avg_score = total_score / num_links_scored
    return avg_score, link_optimal_shifts

def evaluate_placements(candidates: List[PlacementCandidate], *,
                        score_window_ms: float = DEFAULT_SCORE_WINDOW_MS) -> Tuple[PlacementCandidate, Dict[str, float]]:
    """
    Evaluates all placement candidates and returns the winning candidate 
    along with the globally safe time-shifts.
    """
    valid_candidates = []
    
    for candidate in candidates:
        score, link_shifts = score_candidate(candidate, score_window_ms=score_window_ms)
        
        # Build graph to check for cycles
        graph = build_affinity_graph(candidate.cluster, link_shifts)
        
        if not has_cycle(graph):
            candidate.compatibility_score = score
            valid_candidates.append((candidate, graph))
            
    if not valid_candidates:
        raise ValueError("No valid loop-free placement candidates found.")
        
    # Sort candidates by compatibility score (descending)
    valid_candidates.sort(key=lambda x: x[0].compatibility_score, reverse=True)
    
    winning_candidate, winning_graph = valid_candidates[0]
    
    # Reconstruct jobs map for traversal
    jobs_map = {}
    for link_jobs in winning_candidate.cluster.link_jobs.values():
        for job in link_jobs:
            jobs_map[job.job_id] = job
            
    # Compute global time-shifts
    global_time_shifts = traverse_affinity_graph(winning_graph, jobs_map)
    
    return winning_candidate, global_time_shifts



