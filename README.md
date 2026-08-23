# CASSINI Simulator

A purely algorithmic and mathematical Python simulation of the CASSINI scheduler (a system designed to schedule Machine Learning jobs while avoiding network traffic jams).

## Roadmap & Progress

- [x] **1. Data Structures**: Modeled the datacenter network, jobs, and repeating "compute"/"communicate" phases.
- [x] **2. Link-Level Optimizer**: Built a mathematical array-shifting optimizer to calculate optimal time-delays and interleave bandwidth.
- [x] **3. Cluster-Wide Traversal**: Built the bipartite Affinity Graph to resolve multi-link placement conflicts without contradictions (Algorithm 1).
- [ ] **4. Placement Evaluator**: Will evaluate and rank the best GPU placements.
- [ ] **5. Time-Based Simulator**: Master timeline loop.

*All mathematical logic is strictly backed by unit tests and visualized to prove correctness.*
