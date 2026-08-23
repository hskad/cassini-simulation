# CASSINI Simulator

A purely algorithmic and mathematical Python simulation of the CASSINI scheduler. 

*CASSINI* is a network-aware job scheduler for machine learning (ML) clusters, introduced in the paper: **"CASSINI: Network-Aware Job Scheduling in Machine Learning Clusters"**. This repository aims to validate the core mathematical concepts and geometric abstractions proposed in the paper through a lightweight Python simulation, completely isolated from heavy frameworks like PyTorch or real GPU hardware constraints.

## Core Concepts Modeled

### 1. Geometric Bandwidth Abstraction
In distributed ML training, compute (Up phase) and communication (Down phase) cycle continuously. CASSINI represents these cycles as geometric circles where the perimeter is proportional to the training iteration time. By perfectly "rotating" these circles (applying mathematical time-shifts), we can interleave the communication phases of different jobs sharing the same network link, drastically reducing network traffic jams.

### 2. Bipartite Affinity Graph Traversal
When a cluster runs dozens of jobs across multiple interconnected links, shifting a job to optimize one link might accidentally cause a collision on another. CASSINI solves this by mapping the entire topology as a **Bipartite Affinity Graph** (where Jobs are one set of nodes, and Links are the other). A Breadth-First Search (Algorithm 1) safely propagates time-shifts globally, resolving multi-link placement conflicts without mathematical contradictions.

## Features
- **Pure Math Simulation**: No reliance on physical GPUs. Everything is simulated using precise time arrays.
- **Aesthetic Visualizations**: Built-in visualizers using `matplotlib` and `networkx` to generate stunning proofs of the math. Generates overlapping bandwidth charts and bipartite affinity graph network plots.
- **Unit Tested**: The core logic is backed by strict unit tests confirming mathematical alignment with the paper's properties.

## Roadmap & Progress

- [x] **1. Data Structures**: Modeled the datacenter network, jobs, links, servers, and repeating "compute"/"communicate" phases.
- [x] **2. Link-Level Optimizer**: Built a mathematical array-shifting optimizer to calculate optimal time-delays and interleave bandwidth on a single bottleneck link.
- [x] **3. Cluster-Wide Traversal**: Built the bipartite Affinity Graph to resolve multi-link placement conflicts without contradictions using BFS (Algorithm 1).
- [ ] **4. Placement Evaluator**: Will evaluate different candidate placement configurations and mathematically rank them based on our custom compatibility score.
- [ ] **5. Time-Based Simulator**: A master timeline loop to simulate jobs arriving and departing dynamically over time.

## Running the Demo Scripts

This project includes visualizations for the implemented steps. To run them, you will need `matplotlib` and `networkx`.

```bash
pip install matplotlib numpy networkx
```

### Step 2 Demo: Link-Level Overlap
```bash
python demo_step2.py
```
*Generates visual charts showing network collision vs. mathematically optimized interleaved traffic.*

### Step 3 Demo: Affinity Graph
```bash
python demo_step3.py
```
*Generates a visual network topology graph of a complex multi-link setup and prints the globally safe time-shifts.*

---
*All logic is strictly backed by unit tests to prove mathematical correctness.*
