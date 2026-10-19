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
