# CASSINI: Fast Scheduling Model

A Python testbed inspired by [CASSINI (NSDI 2024)](https://www.usenix.org/conference/nsdi24/presentation/rajasekaran). It explores periodic traffic alignment, placement scores, and estimated job completion times. It is a simplified model, not a reproduction of the paper's full system or measured results.

The simulator keeps the fast runtime: it jumps between job arrivals and completions. It does not execute individual training iterations, packets, or transfers.

## Run in WSL

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make PYTHON=python3 test
make PYTHON=python3 demo-affinity
```

Dependencies are NumPy, Matplotlib, NetworkX, and Pillow. Plots use a noninteractive backend and do not require a desktop display.

## Current calculations

### Periodic traffic and compatibility

A job's nominal iteration time is the sum of its phase durations:

$$T_j = \sum_p d_{jp}.$$

Each phase has a bandwidth demand in Gbps. The sampler uses that demand, including any positive demand on a phase named `compute`. At resolution $\Delta$, it rounds the cycle length and individual phase durations to samples. It rotates one sampled cycle by the job's shift, then repeats and truncates it to the scoring window. Fractional durations are therefore approximated.

For $N$ samples on a link with capacity $C$, the implemented compatibility score is:

$$S = 1 - \frac{\sum_{n=0}^{N-1}\max(0,\sum_j b_j[n]-C)}{N C}.$$

The denominator is **sample count times link capacity**. It is not total requested communication area. Equivalently, this is one minus average excess demand divided by capacity. No sampled excess gives $S=1$; heavy overload can give negative scores, including scores below $-1$. The placement search accepts these scores.

The optimizer and evaluator share one window rule: the sampled common period, capped at **600 ms** by default and rounded down to the sampling grid. The default resolution is **1 ms**. A capped window estimates compatibility; it need not cover the full common period. All five experiment scripts accept `--score-window-ms`:

```bash
python3 experiments/large_scale_2000_jobs.py --score-window-ms 1200
```

The optimizer holds the first job at zero offset and adds the other jobs greedily. With two jobs it searches shifts on the sampling grid; with more jobs it uses a coarser step, normally 2 ms. This is a greedy compatibility search, not a guarantee of the best completion time or zero overlap.

### Work rate, progress, and completion time

For penalty parameter $p$, the runtime uses:

$$F = 1 + p(1-S), \qquad T_{j,\mathrm{effective}} = T_j F.$$

**The factor multiplies the whole iteration**, including compute time. It does not multiply only the communication phase. For a job with $I_j$ iterations and completed fraction $q_j$, the next completion estimate is:

$$t_{j,\mathrm{finish}} = t_{\mathrm{now}} + w_j + (1-q_j) I_j T_{j,\mathrm{effective}},$$

where $w_j$ is its pending shift wait. When a scheduling event changes the score, the simulator keeps the progress already made and updates the remaining-time estimate. Over elapsed time $\delta t$, it consumes $\min(\delta t,w_j)$ of waiting first; only the rest advances progress.

For example, four simultaneous jobs each requesting 50 Gbps continuously for a nominal 100 ms on one 50 Gbps link give $S=-2$. With $p=1$, one iteration takes **400 ms** per job under either policy. A former search placeholder of $-1$ incorrectly gave 300 ms in incremental mode; this is fixed.

### Shift waiting time

Only selected plans change running jobs. Candidate evaluation itself does not add waits. Both runtime modes apply the full selected shift plan, including changes to existing jobs. For nominal period $T_j$:

```text
additional_wait = (new_shift - previous_shift) % T_j
pending_wait += additional_wait
```

An unchanged target adds zero wait. A lower target wraps forward through the cycle; a job cannot move backward in time. Pending waits survive subsequent arrivals and replans. A job makes no progress while it waits. Completion records include `shift_wait_ms`, the total charged wait.

A fixed 10 ms shift adds 10 ms once, whether the job has one iteration or 100. A later change can add another wait. Isolated jobs retain their current offsets. The uncoordinated policy uses zero shifts and adds no shift wait.

This remains a fast estimate: periodic scores include waiting jobs and do not model their temporary absence from the network. The optimizer maximizes compatibility without comparing the expected benefit against the wait cost. Repeated replanning can therefore increase completion times.

### Placement rules

Both modes assign each job to one primary bottleneck link. They do not model GPU admission, resource queues, or a full network route.

| Mode | Cassini policy | Uncoordinated policy | Runtime score |
| --- | --- | --- | --- |
| Global, used by the 50- and 60-job scripts | Generate five random placements, optimize shifts, select the best valid score | Generate one random placement, use zero shifts | Unweighted mean over links with more than one job; the same factor is applied to all active jobs |
| Incremental, used by the 2,000- and 10,000-job scripts | Evaluate up to four least-loaded links with optimized shifts | Evaluate the same candidate-link rule with zero shifts | Per-link score; existing routes remain fixed |

In either runtime mode, links with zero or one job are treated as having score 1. Direct `score_link` calls can still detect overload from a single job. A global placement with no contended links also gets score 1.

These are two different placement policies, not a controlled timing-only comparison. In the 50-job script, both runs share the random stream, so a change in Cassini's event order can also change the later baseline placements. The uncoordinated policy is not an implementation of Kubernetes, Slurm, Themis, or Tiresias.

## Graph example and animation

The graph example propagates supplied relative offsets through an **acyclic** bipartite graph. Its jobs all have 100 ms periods and zero traffic demand. It demonstrates graph arithmetic, not optimized traffic or a measured scheduling gain.

```bash
python3 examples/demo_affinity_graph.py
```

The command calculates offsets and regenerates `visualizations/affinity_bfs_animation.gif` from the same shared scenario. Expected offsets, with j1 as the reference:

| Job | Offset (ms) |
| --- | ---: |
| j1 | 0 |
| j2 | 10 |
| j3 | 20 |
| j4 | 40 |
| j5 | 60 |

<p align="center">
  <img src="visualizations/affinity_bfs_animation.gif" alt="Acyclic example with edge offsets and calculated job offsets" width="650"/>
</p>

The CLI and animation use the same traversal result. The traversal chooses reference jobs in placement order, rejects cyclic inputs, and checks that every graph job exists in the supplied job map. Duplicate edges are rejected. Job and link identifiers have separate identities, even when their text matches; weights are stored by `(job_id, link_id)`.

The former example contained cycles and reported spanning-tree assignments as resolved global shifts. It has been replaced. A forest alone does not prove that arbitrary traffic patterns, especially across different periods and multiple links, are collision-free. The runtime experiments use one bottleneck link per job; this multi-link example is separate.

## CLI experiments and visual output

Run any script with `--help` for its options. The commands below use the current fast runtime and overwrite their corresponding PNGs in `visualizations/`.

| Command | Workload or purpose |
| --- | --- |
| `python3 experiments/micro_test.py` | Two periodic profiles: 40 and 60 ms periods, 120 ms common period |
| `python3 experiments/macro_test.py` | 50 generated jobs, global placement mode |
| `python3 experiments/real_workload_experiment.py` | 60-job illustrative trace; `--synthetic` generates another workload |
| `python3 experiments/large_scale_2000_jobs.py` | Stored 2,000-job synthetic trace, incremental mode |
| `python3 experiments/scale_10000_jobs.py` | Stored 10,000-job synthetic trace; the two policies run in separate worker processes |

```bash
make PYTHON=python3 micro-test macro-test real-workload large-scale scale-10k
```

The micro example finds a 10 ms offset for Job B with no sampled over-capacity traffic. On the 120 ms common circle, that is 30 degrees. This is a local model example, not validation of all results in the paper.

<p align="center">
  <img src="visualizations/micro_test_circular.png" alt="Two-job circular alignment example" width="500"/>
</p>

The separate link animation illustrates sampled profile alignment. Regenerate it with `python3 -m src.utils.animator`.

<p align="center">
  <img src="visualizations/optimization_animation.gif" alt="Illustration of periodic profile alignment" width="600"/>
</p>

## Retained workload plots: before shift-wait charges

**The following workload figures and numbers are historical, not results of the current runtime.** They come from source commit `38764ed`, before shifts added waiting time. They remain here after the requested rollback of the later figure update. The [saved results manifest](visualizations/readme_results.json) records that earlier source commit, `shift_waits_charged: false`, settings, numerical results, and figure hashes.

| Historical workload | Baseline mean JCT | Cassini mean JCT | Mean JCT reduction |
| --- | ---: | ---: | ---: |
| 50 jobs | 1335.87 ms | 1122.49 ms | 16.0% |
| 60 jobs | 4430.71 ms | 3918.65 ms | 11.6% |
| 2,000 jobs | 12.06 min | 7.70 min | 36.1% |
| 10,000 jobs | 13.02 min | 7.61 min | 41.6% |

Reduction is `100 * (baseline - cassini) / baseline`. Negative values mean Cassini takes longer. Completion time means turnaround from arrival to completion. A leftward CDF indicates lower completion times.

The commands above produce new local plots with shift waits included; they do not automatically update this historical table or its manifest. New published results need a matching table and manifest. The retained plots cannot establish a gain for the current code or for a production deployment.

### Historical 50-job CDF

<p align="center">
  <img src="visualizations/macro_test_cdf.png" alt="Historical 50-job CDF, excluding shift waits" width="650"/>
</p>

### Historical 60-job workload

<p align="center">
  <img src="visualizations/real_workload_cdf.png" alt="Historical 60-job CDF, excluding shift waits" width="48%"/>
  <img src="visualizations/real_workload_model_breakdown.png" alt="Historical 60-job model breakdown, excluding shift waits" width="48%"/>
</p>

### Historical 2,000-job workload

<p align="center">
  <img src="visualizations/large_scale_2000_jobs_cdf.png" alt="Historical 2000-job CDF, excluding shift waits" width="48%"/>
  <img src="visualizations/large_scale_2000_jobs_breakdown.png" alt="Historical 2000-job model breakdown, excluding shift waits" width="48%"/>
</p>

### Historical 10,000-job workload

<p align="center">
  <img src="visualizations/scale_10000_jobs_cdf.png" alt="Historical 10000-job CDF, excluding shift waits" width="600"/>
  <img src="visualizations/scale_10000_jobs_breakdown.png" alt="Historical 10000-job model breakdown, excluding shift waits" width="600"/>
</p>

Some retained figure titles and older script banners use terms such as "production", "empirical", or "replica". Those labels do not establish provenance. The workload status is described below.

## Workload data and model profiles

| File | Status |
| --- | --- |
| `data/traces/philly_2000_jobs.json` | Locally generated synthetic jobs, seed 42, 2.5-hour arrival parameter; 5,565,953 total iterations |
| `data/traces/philly_10000_jobs.json` | Locally generated synthetic jobs, seed 42, 12.5-hour arrival parameter; 27,791,391 total iterations |
| `data/traces/philly_cluster_trace.json` | Illustrative 60-job input; no verified mapping to original production records |
| `data/models/real_models.json` | Illustrative profile parameters; VGG-16 is described as paper-related, but the catalog does not document a reproducible measurement source for every value |

The arrival parameter controls the expected sum of exponentially distributed inter-arrival times, not a hard trace endpoint. Stored arrival spans are approximately 2.52 and 12.52 hours, not weeks or months. A trace's arrival span and a job's completion time are different quantities.

The loader scales communication duration as:

$$T_{\mathrm{comm}}(B) = T_{\mathrm{comm,default}}\frac{B_{\mathrm{default}}}{B}.$$

The 60-job script loads profiles at half the configured link capacity by default; the larger scripts use the configured capacity. Model names, parameter counts, and gradient sizes do not by themselves establish measured compute or communication performance. Some JSON descriptions claim production provenance; treat those descriptions as unverified.

Stored large traces are reused when present. Changing `--seed` does not regenerate an existing trace; `--num-jobs` limits how many stored records are loaded. Do not interpret a new command seed as a new production dataset.

## Repository map

```text
data/models/          Model profile inputs
data/traces/          Stored workload inputs
src/core/             Dataclasses and trace loading
src/math_engine/      Sampled optimization and affinity graph calculations
src/scheduler/        Placement evaluation and fast event runtime
src/utils/            Static plots and GIF generation
examples/             CLI demos and their shared graph scenario
experiments/          Workload comparisons with CLI options
tests/                Regression tests
visualizations/       Committed PNGs, GIFs, and historical results manifest
Makefile              Command shortcuts
requirements.txt      Python dependencies
```

## Other demos and tests

```bash
python3 examples/demo_link_optimizer.py
python3 examples/demo_evaluator.py
python3 examples/demo_simulator.py
python3 -m unittest discover tests -v
```

The evaluator demo uses seed 42 and prints proposed shifts; it does not execute jobs. The simulator demo reports estimated turnaround times. Tests cover sampled shifts, shared windows, negative scores, shift waits, graph constraints, cycle rejection, and overlapping job/link names.

Use `make PYTHON=python3 help` to list shortcuts. `make clean-png` removes generated PNGs; `make clean` also removes Python caches. Both retain GIFs.
