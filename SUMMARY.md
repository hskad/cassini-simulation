# Shift Policies

This document explains why we created the `research/shift-policies` branch, the physical problem we solved, the decision rules we implemented, and our empirical findings.

---

## 1. The Problem: The Cost of Shifting Running Jobs

In the original CASSINI scheduler, jobs are assigned a phase offset ($\tau$) on a shared network link so their communication phases interleave instead of colliding.

In a static cluster where jobs start together and run forever, you compute $\tau$ once. But in a real cluster, jobs constantly arrive and finish. Every time membership changes, the scheduler recomputes the optimal phase alignment.

### The Problem

When the scheduler tells an **already running job** to switch from offset $\tau_{\text{current}}$ to $\tau_{\text{target}}$,It has to **pause execution** until the clock matches the new phase:

$$
\Delta w = (\tau_{\text{target}} - \tau_{\text{current}}) \pmod{T_{\text{iter}}}
$$

* Where $T_{\text{iter}}$ is the iteration time ($T_{\text{comp}} + T_{\text{comm}}$).
* **Example:** If $T_{\text{iter}} = 100\text{ ms}$, current shift is $30\text{ ms}$, and new target is $10\text{ ms}$:

  $$
  \Delta w = (10 - 30) \pmod{100} = \mathbf{80\text{ ms}}
  $$

  The worker sits completely idle for 80 ms just to catch the new phase!

### Why Vanilla CASSINI Failed on Short Jobs

Vanilla CASSINI had a major blind spot: **it only looked at the network compatibility score, totally ignoring this pause penalty.**

If a job had only 1 or 2 iterations left to finish, Vanilla CASSINI would still force it to pause for 80 ms to gain a tiny 2 ms reduction in network congestion. The job ended up finishing **slower** because the scheduler interrupted it. We call this **Shift Churn**.

---

## 2. The Policies We Built (`src/scheduler/policies/`)

To solve this, we built four policies:

1. **`compatibility` (Vanilla CASSINI)**
   The original paper behavior. Blindly accepts every newly proposed shift, regardless of how long workers have to wait.
2. **`score` (Strict Improvement Control)**
   Only accepts a shift if the link compatibility score strictly increases ($S_{\text{new}} > S_{\text{old}}$). Still ignores wait times.
3. **`cooldown` (Rate-Limiting Control)**
   Only allows a shift if at least $100\text{ ms}$ have passed since the last shift on that link.
4. **`benefit` (Cost-Benefit Economic Rule — Our Contribution)**
   Before accepting any shift, it forecasts the average completion time across all affected jobs under two scenarios:

   * **Future A (Keep current offsets):** No pause delay, but keep existing network contention.
   * **Future B (Apply new offsets):** Pay the one-time pause delay ($\Delta w$).

   It accepts the shift **only if** the expected time saved strictly exceeds the added wait:

   $$
   \text{Estimated Time Saved on Remaining Work} > \Delta w
   $$

### How Completion Time is Estimated

For each active job, its estimated completion time is:

$$
t_{\text{finish}} = t_{\text{now}} + w_{\text{pending}} + \underbrace{(1 - q) \cdot I}_{\text{Remaining Iterations}} \times T_{\text{effective}}
$$

* $q \in [0, 1]$ is current progress.
* $I$ is total iterations.
* $T_{\text{effective}} = T_{\text{nominal}} \times [1 + (1 - S) \cdot \text{penalty}]$, which stretches iteration length based on the compatibility score $S$.

If the shift proposal is rejected, the job keeps running at its current offset with **zero added delay**.

---

## 3. Results: How the Policies Performed

We benchmarked all policies across 5 workloads using identical seeded job-to-link placements:

<p align="center">
  <img src="visualizations/shift_policy_comparison.png" alt="Policy Comparison Chart" width="850"/>
</p>

<p align="center">
  <img src="visualizations/shift_policy_cdf.png" alt="Policy CDF Comparison" width="850"/>
</p>

### Summary Table (% Mean JCT Reduction over Vanilla CASSINI)


| Workload     | Scale / Description                        | `score` Control | `cooldown` Control | `benefit` Rule |
| :----------- | :----------------------------------------- | :-------------: | :----------------: | :------------: |
| **`macro`**  | 50 generated jobs (16 links)               |     +0.33%     |       -0.18%       |   **+1.55%**   |
| **`sample`** | 60 Philly jobs (ResNet, BERT, GPT-2, etc.) |     +0.72%     |       -0.46%       |   **+1.98%**   |
| **`short`**  | 200 short synthetic jobs (1–5 iterations) |     +5.23%     |       +3.97%       |   **+9.30%**   |
| **`2000`**   | 2,000 jobs (~5.5M iterations)              |     +0.98%     |       -0.01%       |   **+0.98%**   |
| **`10000`**  | 10,000 jobs (~27.8M iterations)            |     +3.11%     |       -0.00%       |   **+3.11%**   |

###
