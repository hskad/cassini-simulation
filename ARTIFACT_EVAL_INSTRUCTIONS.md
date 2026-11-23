# Artifact Evaluation: Live Demo & Command Guide
**Project:** Cost-Aware Communication Scheduling for Distributed Deep Learning  
**Presenter:** Daksh Agarwal (Roll No: 230101123)  
**Partner:** Aditya Shukla (Roll No: 230101115)  

---

## 1. Primary Option: The Interactive TUI Dashboard

To run the interactive evaluation dashboard that presents all core modules in a formatted terminal interface:

```powershell
python artifact_eval.py
```
* **Menu Options:**
  * Press `[1]` -> Run Unit Test Suite (All 55 modules verified live in ~1.6s).
  * Press `[2]` -> Run Geometric Micro-Test (Slides 3-4 circular phase alignment).
  * Press `[3]` -> Run Shift Policy Showdown (Slides 12-13 Benefit Rule vs. Vanilla on 200 jobs).
  * Press `[4]` -> Run Live LCM Truncation Benchmark across 7 Period Families (Slides 15-16).
  * Press `[5]` -> Run Live Cluster Simulation (30-job queueing simulator in ~1.5s).
  * Press `[6]` -> Run complete automated showcase.

Alternatively, run specific modules directly from the terminal:
```powershell
python artifact_eval.py --test      # Runs 55 unit tests
python artifact_eval.py --micro     # Runs geometric 2-job circle alignment
python artifact_eval.py --policy    # Shows 200-job policy showdown
python artifact_eval.py --lcm       # Computes analytical 7-family LCM ground truth
python artifact_eval.py --sim       # Runs live 30-job cluster simulator
```

---

## 2. Directory Index: Where Every Log, JSON Manifest, and PNG is Located

If a professor says:  
> *"Show me the actual raw output files on disk, not just the terminal dashboard!"*

Here is the exact map of where all generated artifacts live in the repository:

### A. Plots and Graphical Visualizations (`visualizations/`)
Open any plot instantly in Windows photo viewer:

```powershell
# Slide 3-4: Geometric circle interleaving
Start-Process visualizations\micro_test_circular.png

# Slide 11-12: Small cluster JCT CDF
Start-Process visualizations\macro_test_cdf.png

# Slide 11: Real model profiles (ResNet-50 and VGG-16)
Start-Process visualizations\real_workload_cdf.png
Start-Process visualizations\real_workload_model_breakdown.png

# Slide 11-12: 2,000-job enterprise cluster
Start-Process visualizations\large_scale_2000_jobs_cdf.png
Start-Process visualizations\large_scale_2000_jobs_breakdown.png

# Slide 11-12: 10,000-job ultra-scale cluster
Start-Process visualizations\scale_10000_jobs_cdf.png
Start-Process visualizations\scale_10000_jobs_breakdown.png

# Slide 15-16: LCM truncation vs prefix comparison
Start-Process visualizations\lcm_scoring\strided_vs_prefix_comparison.png
Start-Process visualizations\lcm_scoring\lcm_score_error.png
Start-Process visualizations\lcm_scoring\lcm_cost.png
```

---

### B. Raw Simulation Text Logs (`output/shift-wait-fix/`)
To inspect the raw stdout text logs of complete cluster runs:

```powershell
# Geometric Micro-Test (Slide 3 & 4) text log:
Get-Content output\shift-wait-fix\micro.log

# Small Cluster Queueing Simulator (Slide 11 & 12) text log:
Get-Content output\shift-wait-fix\macro.log

# Real Model Profile Workload (ResNet/VGG Philly Trace) text log:
Get-Content output\shift-wait-fix\sample.log -Head 40

# 2,000-job scale run text log:
Get-Content output\shift-wait-fix\2000.log -Head 40

# 10,000-job scale run text log:
Get-Content output\shift-wait-fix\10000.log -Head 40
```

---

### C. Shift Policy Evaluation Manifests (`output/shift-policy-sensitivity/`)
Contains the full per-job completion records across all 5 policies and 3 seeds (`seed7`, `seed19`, `seed42`):

```powershell
# Short workload (200 jobs) - Benefit Rule vs Vanilla Cassini:
Get-Content output\shift-policy-sensitivity\short-seed42-benefit.json -Head 25
Get-Content output\shift-policy-sensitivity\short-seed42-compatibility.json -Head 25

# Real Model Profile Workload (Philly Sample 60 jobs) JSON records:
Get-Content output\shift-policy-sensitivity\sample-seed42-benefit.json -Head 25
Get-Content output\shift-policy-sensitivity\sample-seed42-compatibility.json -Head 25

# Small Cluster Macro Workload (50 jobs) JSON records:
Get-Content output\shift-policy-sensitivity\macro-seed42-benefit.json -Head 25
Get-Content output\shift-policy-sensitivity\macro-seed42-compatibility.json -Head 25

# View the shift statistics summary from JSON:
python -c "import json; d=json.load(open('output/shift-policy-sensitivity/short-seed42-benefit.json')); print('Benefit Rule: Mean JCT =', round(d['mean_jct_ms'],2), 'ms, Mean Wait =', round(d['mean_wait_ms'],2), 'ms, Shifts Accepted =', d['shift_stats']['accepted'])"
python -c "import json; d=json.load(open('output/shift-policy-sensitivity/short-seed42-compatibility.json')); print('Vanilla:      Mean JCT =', round(d['mean_jct_ms'],2), 'ms, Mean Wait =', round(d['mean_wait_ms'],2), 'ms, Shifts Accepted =', d['shift_stats']['accepted'])"
```

---

### D. Remaining-Work Estimation Error Sweep (`output/remaining-work/`)
Contains the complete dataset for Slide 14 ($\pm 50\%$ estimation noise):

* `-50% Error:` `output/remaining-work/scale-0.5/`
* `-25% Error:` `output/remaining-work/scale-0.75/`
* `  0% Error:` `output/remaining-work/scale-1/`
* `+25% Error:` `output/remaining-work/scale-1.25/`
* `+50% Error:` `output/remaining-work/scale-1.5/`

---

## 3. Fallback: Running Individual Python Scripts Live

If the professors ask you to execute the source scripts from scratch:

### A. Automated Unit Test Suite (Sanity Check)
```powershell
python -m unittest discover tests -v
```
* **Runtime:** ~1.6s (Verifies all 55 modules).

---

### B. Geometric Micro-Test (Slide 3 & 4 Demo)
Calculates circular phase assignments for two periodic jobs sharing a 50 Gbps link.
```powershell
python experiments/micro_test.py
```
* **Runtime:** ~0.5s (Calculates circular shift; reaches 100% compatibility).
* **Saved Visual Plot:** `visualizations/micro_test_circular.png`
* **Saved Text Log:** `output/shift-wait-fix/micro.log` (also `output/fixed-placement/micro.log`)

---

### C. Analytical LCM Truncation Experiment (Slide 15 & 16 Demo)
Evaluates 600 ms window truncation versus full LCM ground truth across all 7 period families.
```powershell
python experiments/strided_lcm_experiment.py
```
* **Runtime:** ~1.8s (Evaluates all 7 period families; proves $\le 0.08$ pp gap).
* **Saved Visual Plots:** `visualizations/lcm_scoring/strided_vs_prefix_comparison.png`, `lcm_cost.png`
* **Saved Data Manifests:** `visualizations/lcm_scoring/strided_sampling_results.json`, `lcm_results.json`

---

### D. Real Model Profile Workload (ResNet & VGG Philly Trace - Slide 11 Demo)
Evaluates real deep learning vision models derived from the Microsoft Philly cluster trace.
```powershell
python experiments/real_workload_experiment.py --num-jobs 20
```
* **Runtime:** ~1.5s (Evaluates vision model turnaround times).
* **Saved Visual Plots:** `visualizations/real_workload_cdf.png`, `real_workload_model_breakdown.png`
* **Saved Text Log:** `output/shift-wait-fix/sample.log`
* **Saved JSON Manifests:** `output/shift-policy-sensitivity/sample-seed42-benefit.json` (and `sample-seed42-compatibility.json`)

---

### E. Small Cluster Queueing Simulator (Slide 11 & 12 Demo)
Simulates dynamic packet arrivals, switch buffer queuing, and phase shifts across a 16-link cluster.
```powershell
python experiments/macro_test.py --num-jobs 30
```
* **Runtime:** ~1.5s (Simulates packet contention on 16 links).
* **Saved Visual Plot:** `visualizations/macro_test_cdf.png`
* **Saved Text Log:** `output/shift-wait-fix/macro.log`
* **Saved JSON Manifests:** `output/shift-policy-sensitivity/macro-seed42-benefit.json` (and `macro-seed42-compatibility.json`)

---

### F. Large Cluster Workload (2,000 Jobs over 2.5 Hours - Slide 11 & 12 Demo)
```powershell
python experiments/large_scale_2000_jobs.py
```
* **Runtime:** ~40s (Simulates 2,000 streaming jobs across 32 links).
* **Saved Visual Plots:** `visualizations/large_scale_2000_jobs_cdf.png`, `large_scale_2000_jobs_breakdown.png`
* **Saved Text Log:** `output/shift-wait-fix/2000.log`
* **Saved JSON Manifests:** `output/shift-policy/2000-seed42-benefit.json` (and `2000-seed42-compatibility.json`)

---

### G. Enterprise Scale Stress-Test (10,000 Jobs, 27M Iterations - Slide 11 & 12 Demo)
```powershell
python experiments/scale_10000_jobs.py
```
* **Runtime:** ~2.5 min (Simulates 10,000 jobs over a 12.5-hour trace).
* **Saved Visual Plots:** `visualizations/scale_10000_jobs_cdf.png`, `scale_10000_jobs_breakdown.png`
* **Saved Text Log:** `output/shift-wait-fix/10000.log`
* **Saved JSON Manifests:** `output/shift-policy-scale/10000-seed42-benefit.json` (and `10000-seed42-compatibility.json`)

---

## 4. Master Slide-to-Artifact Mapping

| Slide Topic | Presentation Slide | Where Output is Saved on Disk | Live Run Command |
| :--- | :---: | :--- | :--- |
| **Code Correctness / Tests** | -- | `tests/` | `python -m unittest discover tests` |
| **Geometric Interleaving** | **Slide 3 & 4** | `visualizations/micro_test_circular.png`<br>`output/shift-wait-fix/micro.log` | `python experiments/micro_test.py` |
| **Real Models (ResNet/VGG)**| **Slide 11** | `visualizations/real_workload_cdf.png`<br>`output/shift-wait-fix/sample.log`<br>`output/shift-policy-sensitivity/sample-*.json` | `python experiments/real_workload_experiment.py` |
| **Small Cluster Simulation** | **Slide 11 & 12** | `visualizations/macro_test_cdf.png`<br>`output/shift-wait-fix/macro.log`<br>`output/shift-policy-sensitivity/macro-*.json` | `python experiments/macro_test.py --num-jobs 30` |
| **Policy Showdown (Short)** | **Slide 12 & 13** | `output/shift-policy-sensitivity/short-*.json` | `python artifact_eval.py --policy` |
| **2,000-Job Workload** | **Slide 11 & 12** | `visualizations/large_scale_2000_jobs_cdf.png`<br>`output/shift-wait-fix/2000.log`<br>`output/shift-policy/2000-*.json` | `python experiments/large_scale_2000_jobs.py` |
| **10,000-Job Scale** | **Slide 11 & 12** | `visualizations/scale_10000_jobs_cdf.png`<br>`output/shift-wait-fix/10000.log`<br>`output/shift-policy-scale/10000-*.json` | `python experiments/scale_10000_jobs.py` |
| **Estimation Error (+/-50%)** | **Slide 14** | `output/remaining-work/scale-*/` | See Section 2-D |
| **LCM Window Truncation** | **Slide 15 & 16** | `visualizations/lcm_scoring/strided_vs_prefix_comparison.png`<br>`visualizations/lcm_scoring/strided_sampling_results.json` | `python experiments/strided_lcm_experiment.py` |
