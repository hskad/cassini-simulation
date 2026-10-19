# Cassini simulation

This project tests Cassini's phase scheduling in a Python fluid network model.
It does not require GPUs, switches, or a packet simulator.

The corrected engine executes each phase. It applies time-shifts as waits and
shares bandwidth when transfers overlap. Job completion time (JCT) includes
compute, communication, and all waits.

## Start from Windows CMD

Open CMD in this folder. Install the packages once:

```bat
python -m pip install -r requirements.txt
```

Run the checks, then run the small demo:

```bat
cassini.bat test
cassini.bat demo
```

The Python commands work on Windows, Linux, and macOS:

```text
python cassini.py test
python cassini.py demo
python cassini.py experiment --jobs 20 --links 4 --seed 42
```

Use `python3` if your system uses that command name.
Use `cassini.bat --help` or `cassini.bat demo --help` to see the options.

## Demos and plots

```bat
cassini.bat demo --scenario aligned --iterations 10
cassini.bat demo --scenario partial --out output/partial
cassini.bat demo --scenario multi-link --out output/multi-link
cassini.bat demo --scenario dynamic --out output/dynamic
cassini.bat demo --jitter 0.04 --include-static --iterations 100 --out output/jitter
```

| Scenario | What it checks |
| --- | --- |
| aligned | Two jobs can alternate communication on one link. |
| partial | Communication demand prevents complete alignment. |
| multi-link | Three jobs share two links. The affinity graph is a chain. |
| dynamic | Jobs arrive while other jobs are running. |

The jitter value `0.04` gives uniform compute variation between -4% and +4%.
Each job receives the same compute samples under every policy.

Each run saves these plots:

| File | Content |
| --- | --- |
| `timeline.png` | Executed compute, communication, and waiting intervals. |
| `bandwidth.png` | Requested bandwidth, served bandwidth, and link capacity. |
| `jct.png` | Completion time distribution and mean waiting time. |
| `drift.png` | Communication start error as a percentage of iteration time. |

Timeline, bandwidth, and drift plots show the first 600 ms by default.
Use `--plot-window 3000` to show more time. Use `--plot-jobs 12` to show more jobs.
These display limits do not change the simulation or the saved event data.
The bandwidth plot uses the same link under every policy.

## Experiments and saved data

```bat
cassini.bat experiment --jobs 20 --links 4 --iterations 20 --seed 42
cassini.bat experiment --catalog --jobs 12 --score-horizon 2000 --out output/catalog
cassini.bat experiment --trace data/traces/philly_cluster_trace.json --jobs 10 --score-horizon 2000 --out output/sample
```

The default experiment uses synthetic jobs with simple periodic profiles.
The catalog command uses model parameters with the source limits listed below.
The trace command reads the selected workload file.

`--jobs` limits the number of loaded records. Trace iteration counts stay intact
unless `--iterations` is set. That option overrides the count for every loaded job.

The output folder contains:

- `status.json`: whether the run completed or failed.
- `summary.csv` and `summary.json`: mean, P50, and P95 JCT; waits; adjustment counts.
- `parameters.json`: run options, units, source details, and a workload hash.
- `workload.json`: the exact job inputs.
- One folder per policy: completions, phase events, link events, drift observations,
  corrections, applied schedule targets, routes, and link totals.

Use a separate `--out` folder to retain each experiment. A repeated run replaces
its generated result files. Output files are excluded from Git.

Use `--no-history` for large runs. It saves aggregate data and the JCT plot.
The detailed event files and the other plots are omitted.
The engine executes all iterations; it no longer skips them through a score model.
Large workloads can therefore take substantially longer than the old scripts.

## Policies and fair comparison

The comparison uses the same jobs, arrivals, routes, capacities, and noise samples.

- `uncoordinated`: no calculated phase shifts.
- `cassini`: geometric shifts, affinity-graph traversal, and the drift trigger.
- `static-shifts`: the same schedule with drift correction disabled.
  Add `--include-static` to include this comparison.

Routes stay fixed after a job arrives. Unspecified routes use the least occupied
link, with a stable tie rule. Explicit routes can span several links.
This setup isolates phase scheduling. It does not reproduce Themis or Pollux
resource allocation, placement search, or migration.

At an arrival or departure, Cassini calculates a schedule for the active routes.
A new job waits for its target start. An existing job applies the new target at
its next iteration boundary. It can finish its current phase first.
Every applied wait counts towards JCT. A new schedule need not take effect
immediately across all jobs.

The network uses max-min bandwidth sharing with a demand cap for each phase.
A transfer must fit the capacity of every link on its path. Compute with no
network demand proceeds independently. Transfer work equals nominal bandwidth
times nominal phase duration, in Gbps ms. Divide that value by eight to obtain MB.

## Drift correction assumption

The supplied paper states that agents measure drift. Section 5.7 gives a trigger:
communication starts differ by more than 5% of the ideal iteration time.

The paper does not give a complete correction procedure. This simulation uses
the following explicit assumption: for a compatible group, an agent delays a
communication phase to its next nominal start when the trigger is exceeded.
It checks phase error modulo the nominal iteration period. The threshold can be
set with `--drift-threshold`. Corrections can cost almost one iteration.
Their cost can exceed the gain from alignment.

This is a model of the existing mechanism, with a stated action rule.
It is not a new research contribution or an exact reproduction of the original agents.

## Scoring and solver limits

The score follows Table 1: one minus integrated excess bandwidth, divided by
link capacity and the measurement duration. Scores can be negative.

By default, scoring covers the full least common multiple of the job periods.
Fractional phase times are retained. Phase boundaries are integrated directly.
Sampled arrays are used for legacy plots only.

Large common periods can exceed the event budget. The program then stops with
an error. Set `--score-horizon` to request a finite window explicitly.
A score of one in that window does not establish compatibility for all time.

`--resolution` sets the time grid for shift search. The first job is held fixed.
The search is exhaustive on that grid for two jobs. For more jobs it is greedy.
It does not guarantee the global optimum of the paper's joint formulation.
The affinity graph must have no cycles. Unsupported cyclic routes are rejected
before optimization. Job IDs and link IDs use separate namespaces. Graph demo
inputs also use a graph with no cycles.

## Data sources

The file names are retained for compatibility. They do not establish a source.

| File | Status |
| --- | --- |
| `philly_2000_jobs.json` | Synthetic; generated locally with seed 42 and a 2.5-hour arrival parameter. |
| `philly_10000_jobs.json` | Synthetic; generated locally with seed 42 and a 12.5-hour arrival parameter. |
| `philly_cluster_trace.json` | Illustrative; no verified mapping to original production records. |
| `real_models.json` | Illustrative parameters, except the source specified for VGG-16. |

The VGG-16 profile uses the 141 ms low-demand phase and 114 ms high-demand phase
from Figure 16 of the supplied paper. Its testbed link rate is 50 Gbps.
Scaling communication time inversely with bandwidth is a simulation assumption.
Other model values lack verified benchmark sources.

Historical plots in `visualizations/` came from the previous runtime model.
They are retained as old artifacts. Their speedup values are not validated
results from the corrected simulator.

## Model boundaries

This is a mathematical testbed. It does not model GPU admission, GPU memory,
training accuracy, switch buffers, packet loss, ECN, PFC, or NCCL internals.
Communication volume is derived from phase time and bandwidth.
The catalog's gradient size and the workload's GPU count do not control execution.

Existing examples show individual geometric and graph concepts.
Use the main utility for current comparisons and plots.

## Reference

Rajasekaran, Ghobadi, and Akella,
*CASSINI: Network-Aware Job Scheduling in Machine Learning Clusters*.
The local reference is arXiv:2308.00852v1, dated 1 August 2023.


## Older entry points

The four cluster experiment scripts now call the main utility. They use the
corrected phase engine and save results under `output/`. Their old penalty and
parallel execution options have been removed. Run a script with `--help` for
current options. Large scripts keep the original iteration counts and can take
considerable time. Use `--jobs 10 --iterations 5` for a quick check.

`experiments/micro_test.py` still shows the circular geometric example.
It now scores phase boundaries and saves its plot under `output/micro/`.
It illustrates Figure 3's method; it does not reproduce a hardware experiment.
