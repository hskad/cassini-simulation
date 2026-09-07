import json
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.core.models import Phase, Job

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

@dataclass
class ModelProfile:
    """Represents the empirical profile of an ML model on standard GPU clusters."""
    name: str
    domain: str
    architecture: str
    parameters_million: float
    gradient_size_mb: float
    compute_time_ms: float
    default_comm_time_ms: float
    default_bandwidth_gbps: float = 25.0
    description: str = ""

    def get_comm_time(self, bandwidth_gbps: float) -> float:
        """
        Calculates communication time scaled for the specified link bandwidth.
        Based on Ring AllReduce: T_comm is inversely proportional to link line rate.
        """
        if bandwidth_gbps <= 0:
            raise ValueError("Bandwidth must be strictly positive.")
        return float(self.default_comm_time_ms * (self.default_bandwidth_gbps / bandwidth_gbps))

    def to_job(
        self,
        job_id: str,
        arrival_time: float = 0.0,
        total_iterations: int = 10,
        bandwidth_gbps: float = 25.0
    ) -> Job:
        """Instantiates a concrete simulator Job from this profile."""
        comm_time = self.get_comm_time(bandwidth_gbps)
        phases = [
            Phase(type="compute", duration=self.compute_time_ms, bandwidth_demand=0.0),
            Phase(type="communicate", duration=comm_time, bandwidth_demand=bandwidth_gbps)
        ]
        return Job(
            job_id=job_id,
            name=self.name,
            phases=phases,
            arrival_time=arrival_time,
            total_iterations=total_iterations
        )

class TraceLoader:
    """Loads empirical model catalogs and cluster traces."""

    DEFAULT_MODELS_PATH = os.path.join(PROJECT_ROOT, "data", "models", "real_models.json")
    DEFAULT_TRACE_PATH = os.path.join(PROJECT_ROOT, "data", "traces", "philly_cluster_trace.json")

    def __init__(self, models_path: Optional[str] = None):
        path = models_path or self.DEFAULT_MODELS_PATH
        self.models: Dict[str, ModelProfile] = self._load_models_json(path)

    def _load_models_json(self, path: str) -> Dict[str, ModelProfile]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model profiles catalog not found at: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        profiles = {}
        for name, entry in data.get("models", {}).items():
            profiles[name] = ModelProfile(
                name=name,
                domain=entry["domain"],
                architecture=entry["architecture"],
                parameters_million=entry["parameters_million"],
                gradient_size_mb=entry["gradient_size_mb"],
                compute_time_ms=entry["compute_time_ms"],
                default_comm_time_ms=entry["default_comm_time_ms"],
                default_bandwidth_gbps=entry.get("default_bandwidth_gbps", 25.0),
                description=entry.get("description", "")
            )
        return profiles

    def load_trace(
        self,
        trace_path: Optional[str] = None,
        bandwidth_gbps: float = 25.0,
        max_jobs: Optional[int] = None
    ) -> List[Job]:
        """Loads a real cluster trace (e.g. Microsoft Philly) into a list of simulator Jobs."""
        path = trace_path or self.DEFAULT_TRACE_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"Trace file not found at: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_jobs = data.get("jobs", [])
        if max_jobs is not None:
            raw_jobs = raw_jobs[:max_jobs]

        jobs: List[Job] = []
        for item in raw_jobs:
            m_name = item["model_name"]
            if m_name not in self.models:
                raise KeyError(f"Model '{m_name}' referenced in trace not found in model catalog.")
            profile = self.models[m_name]
            job = profile.to_job(
                job_id=item["job_id"],
                arrival_time=float(item["arrival_time_ms"]),
                total_iterations=int(item["total_iterations"]),
                bandwidth_gbps=bandwidth_gbps
            )
            jobs.append(job)
        return jobs

    def generate_synthetic_philly_workload(
        self,
        num_jobs: int = 50,
        arrival_span_ms: float = 1000.0,
        bandwidth_gbps: float = 25.0,
        seed: Optional[int] = 42
    ) -> List[Job]:
        """
        Generates a synthetic workload following the Microsoft Philly production mixture:
        ~38% Vision, ~45% NLP, ~17% Recommendation with heavy-tailed iteration distribution.
        """
        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = random.Random()

        # Model distribution weights matching Philly production logs
        weights = {
            "ResNet-50": 0.22,
            "VGG-16": 0.10,
            "ViT-Base": 0.08,
            "BERT-Base": 0.25,
            "BERT-Large": 0.12,
            "GPT-2-Medium": 0.08,
            "DLRM": 0.15
        }
        model_names = list(weights.keys())
        prob_dist = [weights[m] for m in model_names]

        jobs: List[Job] = []
        current_time = 0.0
        avg_inter_arrival = arrival_span_ms / max(1, num_jobs)

        for i in range(num_jobs):
            # Exponential inter-arrival times (Poisson arrival process)
            inter_arrival = rng.expovariate(1.0 / avg_inter_arrival)
            current_time += inter_arrival

            # Heavy-tailed iteration distribution (log-normal)
            iters = max(5, int(round(rng.lognormvariate(mu=3.0, sigma=0.6))))
            iters = min(iters, 80) # Cap for simulation tractability

            chosen_model_name = rng.choices(model_names, weights=prob_dist, k=1)[0]
            profile = self.models[chosen_model_name]

            job = profile.to_job(
                job_id=f"job_{i+1:03d}",
                arrival_time=round(current_time, 2),
                total_iterations=iters,
                bandwidth_gbps=bandwidth_gbps
            )
            jobs.append(job)

        return jobs

    def generate_large_scale_trace(
        self,
        num_jobs: int = 2000,
        timeline_hours: float = 2.5,
        bandwidth_gbps: float = 50.0,
        seed: int = 42
    ) -> List[Job]:
        """
        Generates an unscaled large-scale production trace (e.g. 2,000 jobs)
        with empirical model profiles and realistic full training iterations (1,000 - 10,000 iters)
        calibrated for realistic multi-tenant cluster concurrency (~80-120 concurrent jobs).
        """
        rng = random.Random(seed)

        # Philly empirical proportions
        weights = {
            "ResNet-50": 0.22,
            "VGG-16": 0.10,
            "ViT-Base": 0.08,
            "BERT-Base": 0.25,
            "BERT-Large": 0.12,
            "GPT-2-Medium": 0.08,
            "DLRM": 0.15
        }
        model_names = list(weights.keys())
        prob_dist = [weights[m] for m in model_names]

        total_time_ms = timeline_hours * 3600.0 * 1000.0
        avg_inter_arrival = total_time_ms / max(1, num_jobs)

        jobs: List[Job] = []
        current_time = 0.0

        for i in range(num_jobs):
            inter_arrival = rng.expovariate(1.0 / avg_inter_arrival)
            current_time += inter_arrival

            # Unscaled real iterations (median ~3,000, range 1,000 to 10,000 iterations)
            # Log-normal distribution reflecting heavy-tailed convergence requirements
            iters = int(round(rng.lognormvariate(mu=7.8, sigma=0.5)))
            iters = max(1000, min(iters, 12000))

            chosen_model = rng.choices(model_names, weights=prob_dist, k=1)[0]
            profile = self.models[chosen_model]

            job = profile.to_job(
                job_id=f"job_{i+1:04d}",
                arrival_time=round(current_time, 2),
                total_iterations=iters,
                bandwidth_gbps=bandwidth_gbps
            )
            jobs.append(job)

        return jobs

