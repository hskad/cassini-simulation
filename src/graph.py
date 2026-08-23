from collections import deque
from typing import Dict, List, Set, Tuple
from src.models import Cluster, Job, Link

class AffinityGraph:
    """
    Represents the bipartite Affinity graph G = (U, V, E)
    U: Set of Jobs
    V: Set of Links
    """
    def __init__(self):
        self.U: Set[str] = set() # job_ids
        self.V: Set[str] = set() # link_ids
        # adjacency list for jobs -> links and links -> jobs
        self.edges_U_to_V: Dict[str, List[str]] = {} 
        self.edges_V_to_U: Dict[str, List[str]] = {}
        # edge weights (optimal time shifts calculated per link)
        # weight(j, l) is the relative time shift of job j on link l
        self.weights: Dict[Tuple[str, str], float] = {}

    def add_edge(self, job_id: str, link_id: str, weight: float = 0.0):
        self.U.add(job_id)
        self.V.add(link_id)
        
        if job_id not in self.edges_U_to_V:
            self.edges_U_to_V[job_id] = []
        if link_id not in self.edges_V_to_U:
            self.edges_V_to_U[link_id] = []
            
        self.edges_U_to_V[job_id].append(link_id)
        self.edges_V_to_U[link_id].append(job_id)
        
        self.weights[(job_id, link_id)] = weight
        self.weights[(link_id, job_id)] = weight

def build_affinity_graph(cluster: Cluster, link_optimal_shifts: Dict[str, Dict[str, float]]) -> AffinityGraph:
    """
    Builds the Affinity graph from a Cluster topology and the optimal link-level time shifts.
    link_optimal_shifts maps link_id -> {job_id: optimal_relative_shift}
    """
    graph = AffinityGraph()
    for link_id, jobs in cluster.link_jobs.items():
        if len(jobs) > 1: # Only include links with > 1 job competing
            for job in jobs:
                # Add edge. Weight is the local optimal shift from optimizer.
                weight = link_optimal_shifts.get(link_id, {}).get(job.job_id, 0.0)
                graph.add_edge(job.job_id, link_id, weight)
    return graph

def traverse_affinity_graph(graph: AffinityGraph, jobs_map: Dict[str, Job]) -> Dict[str, float]:
    """
    Algorithm 1 from the paper: BFS Affinity Graph Traversal to find unique global time shifts.
    """
    global_time_shifts: Dict[str, float] = {}
    visited_U: Set[str] = set()
    
    # Process each connected component
    for u in graph.U:
        if u in visited_U:
            continue
            
        # Start BFS
        queue = deque([u])
        global_time_shifts[u] = 0.0 # Reference point
        visited_U.add(u)
        
        while queue:
            current_job_id = queue.popleft()
            
            # Find neighbors of current job (which are links)
            for link_id in graph.edges_U_to_V.get(current_job_id, []):
                # Traversing U -> V incurs a negative sign (as per paper Eq 7, 8, 9)
                w_u_to_v = graph.weights[(current_job_id, link_id)]
                
                # Find neighbor jobs of this link
                for neighbor_job_id in graph.edges_V_to_U.get(link_id, []):
                    if neighbor_job_id not in visited_U:
                        # Traversing V -> U incurs a positive sign
                        w_v_to_u = graph.weights[(link_id, neighbor_job_id)]
                        
                        # Calculate final shift (Eq 17 in paper algorithm)
                        # tk = (tj - we1 + we2) % iter_timek
                        iter_time = jobs_map[neighbor_job_id].iteration_time
                        
                        tk = (global_time_shifts[current_job_id] - w_u_to_v + w_v_to_u) % iter_time
                        
                        global_time_shifts[neighbor_job_id] = tk
                        visited_U.add(neighbor_job_id)
                        queue.append(neighbor_job_id)
                        
    return global_time_shifts
