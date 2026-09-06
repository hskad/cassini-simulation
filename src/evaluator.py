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


