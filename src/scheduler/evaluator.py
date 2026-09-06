import random
from dataclasses import dataclass
from typing import Dict, List, Tuple
from src.core.models import Cluster, Job, Link
from src.math_engine.graph import AffinityGraph, build_affinity_graph, traverse_affinity_graph
from src.math_engine.optimizer import optimize_link, calculate_score, discretize_phases, lcm

@dataclass
class PlacementCandidate:
    candidate_id: str
    cluster: Cluster
    compatibility_score: float = 0.0

def has_cycle(graph: AffinityGraph) -> bool:
    """
    Detects if the bipartite Affinity Graph has any cycles using BFS.
    Returns True if a cycle is found, False otherwise.
    """
    visited = set()
    
    for start_node in graph.U:
        if start_node in visited:
            continue
            
        # queue stores tuples of (current_node, parent_node)
        queue = [(start_node, None)]
        visited.add(start_node)
        
        while queue:
            current_node, parent = queue.pop(0)
            
            # get neighbors
            neighbors = []
            if current_node in graph.U:
                neighbors = graph.edges_U_to_V.get(current_node, [])
            else:
                neighbors = graph.edges_V_to_U.get(current_node, [])
                
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, current_node))
                elif neighbor != parent:
                    # Found a cycle!
                    return True
                    
    return False

def generate_mock_candidates(base_cluster: Cluster, jobs: List[Job], num_candidates: int = 5) -> List[PlacementCandidate]:
    """
    Simulates a scheduler (like Themis) by generating N random placement candidates.
    Assigns jobs randomly to the links in the base cluster to create varied network overlaps.
    """
    candidates = []
    
    for i in range(num_candidates):
        # Create a new link_jobs mapping
        new_link_jobs = {link.link_id: [] for link in base_cluster.links}
        
        for job in jobs:
            # Randomly select a number of links this job traverses (e.g., 1 to 3)
            num_links = random.randint(1, min(3, max(1, len(base_cluster.links))))
            chosen_links = random.sample(base_cluster.links, num_links)
            
            for link in chosen_links:
                new_link_jobs[link.link_id].append(job)
                
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

def score_candidate(candidate: PlacementCandidate) -> Tuple[float, Dict[str, Dict[str, float]]]:
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
            
            # optimize_link modifies time_shift in-place for jobs_copy
            optimize_link(jobs_copy, link, resolution=1.0)
            
            # calculate score
            lcm_steps = int(jobs_copy[0].iteration_time)
            for j in jobs_copy[1:]:
                lcm_steps = lcm(lcm_steps, int(j.iteration_time))
                
            arrs = [discretize_phases(j, float(lcm_steps), 1.0) for j in jobs_copy]
            link_score = calculate_score(arrs, link.capacity)
            
            total_score += link_score
            num_links_scored += 1
            
            # Record the optimal shifts for the affinity graph
            link_optimal_shifts[link.link_id] = {j.job_id: j.time_shift for j in jobs_copy}
            
    if num_links_scored == 0:
        return 1.0, {} # Perfect score if no links have >1 job
        
    avg_score = total_score / num_links_scored
    return avg_score, link_optimal_shifts

def evaluate_placements(candidates: List[PlacementCandidate]) -> Tuple[PlacementCandidate, Dict[str, float]]:
    """
    Evaluates all placement candidates and returns the winning candidate 
    along with the globally safe time-shifts.
    """
    valid_candidates = []
    
    for candidate in candidates:
        score, link_shifts = score_candidate(candidate)
        
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



