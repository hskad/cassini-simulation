# LCM Scoring Research

This work studies how a bounded traffic-scoring window affects shift selection.
It starts from the stable fast simulator on `main`, independently of
`research/shift-policies`. Development takes place on `research/lcm-scoring`.
The frozen simulator is tagged `baseline/fast-runtime-v1`.

## Research question

Can we select useful shifts with bounded calculation cost when job periods
have a large least common multiple (LCM)? The current optimizer uses at most
600 ms of traffic, so it already avoids expanding the full common period.
The first task is to measure what this limit misses before changing the method.

## Independent traffic check

`src/analysis/periodic_traffic.py` integrates offered bandwidth directly between
phase-boundary events. It does not use the optimizer's samples or runtime formula.
It measures total bandwidth above link capacity, overloaded time, and peak demand.
All real bandwidth demands are added before applying the capacity threshold;
pairwise checks alone can miss overload caused by three or more jobs.

Profiles repeat indefinitely for this diagnostic. Positive shifts delay phases.
The checker supports fractional phase durations, although the initial comparison
will use integer milliseconds to match the baseline's 1 ms sampling exactly.
It does not model packet queues, congestion control, job lifetimes, or JCT.

The benchmark will include short shared periods, longer periods with shared
factors, and nearby coprime periods. Full-LCM evaluation is used only for cases
small enough to calculate. A separate growth illustration will show larger LCMs
without allocating their traffic arrays.

Some period combinations have no long-term score improvement from a fixed shift.
For two discrete profiles with coprime integer periods, every pair of phase
residues occurs once over the full LCM. Integer offsets only change their order.
The resulting full-period offered-load distribution is therefore unchanged.
Short-window improvements must be checked against that reference.

See the [README](README.md) for installation and the baseline simulator.

## Run the diagnostic

```bash
make PYTHON=python3 lcm-scoring
# Short check, with separate output paths:
python3 experiments/lcm_scoring_experiment.py --cases coprime_pair --seeds 42 --repetitions 1 --output-dir output/lcm-smoke --plot-dir output/lcm-smoke/plots
```

The default command tests seven period families and seeds 7, 19, and 42.
Periods range from 40 to 160 ms and full LCMs from 120 to 31,200 ms. Each seed
generates fixed synthetic one- or two-burst profiles with 20–65% communication
time. Two-job demands are 50 Gbps each; three-job demands are selected from
25, 40, and 50 Gbps. Link capacity is 50 Gbps. Job order stays fixed.

Each case uses the unchanged optimizer with window limits of 600, 1,200,
6,000 ms, and the full LCM. Limits longer than the LCM use the complete period.
All selected shifts are checked by phase-event integration on the later interval
`[H, 2H)`, where `H` is the LCM. This interval is disjoint from every selection
interval and covers one complete repeating pattern. It is not an independent
random traffic sample; the profiles are deterministic and stationary.

For two jobs, the baseline searches all integer shifts of the second job with
the first at zero. For three jobs, it retains the baseline's ordered greedy
2 ms search. The full-window result is a reference search, not a global optimum
for three jobs. A bounded-window result can therefore outperform that reference.

The default 100,000 ms exact-reference limit prevents accidental expansion of
huge examples. Larger coprime period sets appear only in the analytical growth
plot; no full arrays are allocated for that illustration.

## Metrics and saved records

- **Score optimism:** selected-window score minus later full-period score,
  in percentage points. Positive values mean an optimistic estimate.
- **Gap to full-window search:** full-window reference score minus the selected
  plan's later score. Positive is worse; negative is better than that reference.
- **Gain over zero shifts:** recorded separately for the selection interval
  and the later interval, to detect benefits which do not persist.
- **Selection time:** median of three untraced optimizer calls, excluding job
  copies, checks, and reference integration. Each timing is also saved.
- **Peak traced allocation:** a separate untimed optimizer call. This includes
  allocations visible to Python/NumPy tracing, not total process memory.

The two PNGs and `lcm_results.json` go to `visualizations/lcm_scoring/`.
Per-case records go to `output/lcm-scoring/`. Both contain profiles and numerical
results; the published manifest also records settings, package versions, figure
hashes, the source commit, working-file hashes, and canonical Git-blob hashes.
Source content is checked against its commit after normalizing checkout line
endings. Existing baseline figures and simulator behaviour are preserved.

## Related work

[GCD+ (ECRTS 2022)](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECRTS.2022.11)
uses period arithmetic to help assign offsets in periodic FIFO systems.
[Methods for Large-Scale Time-Triggered Network Scheduling (2019)](https://www.mdpi.com/2079-9292/8/7/738)
uses segmentation to reduce schedule-synthesis cost. These are related methods
to study, not evidence that a particular new scorer improves Cassini.
