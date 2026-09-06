# CASSINI Simulator

A purely algorithmic and mathematical Python simulation of the CASSINI scheduler. 

*CASSINI* is a network-aware job scheduler for machine learning (ML) clusters, introduced in the paper: **"CASSINI: Network-Aware Job Scheduling in Machine Learning Clusters"**. This repository aims to validate the core mathematical concepts and geometric abstractions proposed in the paper through a lightweight Python simulation, completely isolated from heavy frameworks like PyTorch or real GPU hardware constraints.

## Core Concepts Modeled

### 1. Geometric Bandwidth Abstraction
In distributed ML training, compute (Up phase) and communication (Down phase) cycle continuously. CASSINI represents these cycles as geometric circles where the perimeter is proportional to the training iteration time. By perfectly "rotating" these circles (applying mathematical time-shifts), we can interleave the communication phases of different jobs sharing the same network link, drastically reducing network traffic jams.

<p align="center">
  <img src="visualizations/optimization_animation.gif" alt="Geometric Optimization Animation" width="600"/>
</p>

### 2. Bipartite Affinity Graph Traversal
When a cluster runs dozens of jobs across multiple interconnected links, shifting a job to optimize one link might accidentally cause a collision on another. CASSINI solves this by mapping the entire topology as a **Bipartite Affinity Graph** (where Jobs are one set of nodes, and Links are the other). A Breadth-First Search (Algorithm 1) safely propagates time-shifts globally, resolving multi-link placement conflicts without mathematical contradictions.

<p align="center">
  <img src="visualizations/affinity_bfs_animation.gif" alt="Affinity Graph BFS Traversal" width="600"/>
</p>

## Features
- **Pure Math Simulation**: No reliance on physical GPUs. Everything is simulated using precise time arrays.
- **Aesthetic Visualizations**: Built-in visualizers using `matplotlib` and `networkx` to generate stunning proofs of the math. Generates overlapping bandwidth charts and bipartite affinity graph network plots.
- **Unit Tested**: The core logic is backed by strict unit tests confirming mathematical alignment with the paper's properties.

## Roadmap & Progress

- [x] **1. Data Structures**: Modeled the datacenter network, jobs, links, servers, and repeating "compute"/"communicate" phases.
- [x] **2. Link-Level Optimizer**: Built a mathematical array-shifting optimizer to calculate optimal time-delays and interleave bandwidth on a single bottleneck link.
- [x] **3. Cluster-Wide Traversal**: Built the bipartite Affinity Graph to resolve multi-link placement conflicts without contradictions using BFS (Algorithm 1).
- [x] **4. Placement Evaluator**: Evaluates different candidate placement configurations and mathematically ranks them based on our custom compatibility score.
- [x] **5. Time-Based Simulator**: A master timeline loop to simulate jobs arriving and departing dynamically over time, complete with mathematical slowdown calculation for network congestion.

## Directory Structure

```text
cassini-simulation/
├── src/                  # Core engine
│   ├── core/             # Fundamental data structures
│   ├── math_engine/      # Theoretical algorithms from the paper
│   ├── scheduler/        # High-level scheduling and time loop
│   └── utils/            # Helper tools (visualizer, animator)
├── tests/                # Unit tests for CI/CD
├── examples/             # Demo scripts 
├── experiments/          # Benchmarks and evaluation scripts
├── visualizations/       # Generated plots and charts
└── README.md
```

## Running the Demo Scripts

This project includes visualizations for the implemented steps. To run them, you will need to install `matplotlib` and `networkx`.

```bash
pip install matplotlib numpy networkx
```

### Link-Level Overlap Demo
```bash
python examples/demo_link_optimizer.py
```
*Generates visual charts showing network collision vs. mathematically optimized interleaved traffic.*

### Affinity Graph Demo
```bash
python examples/demo_affinity_graph.py
```
*Generates a visual network topology graph of a complex multi-link setup and prints the globally safe time-shifts.*

### Placement Evaluator Demo
```bash
python examples/demo_evaluator.py
```
*Generates mock placement candidates, tests them for cyclic conditions, calculates their network compatibility, and selects the optimal layout.*

### Time-Based Simulator Demo
```bash
python examples/demo_simulator.py
```
*Fires up a master event loop simulating jobs arriving over time, dynamically re-routing them, calculating iteration slowdowns based on mathematical collisions, and tracking total turnaround time.*

---
*All logic is strictly backed by unit tests to prove mathematical correctness.*
