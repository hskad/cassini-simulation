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

