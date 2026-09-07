# Makefile for CASSINI Simulation & Experiments

PYTHON ?= python

.PHONY: help test demo-link demo-affinity demo-evaluator demo-simulator demo-all micro-test macro-test real-workload large-scale validate-baseline clean-png clean

help:
	@echo "CASSINI Simulation - Available Targets:"
	@echo "  make demo-link          - Run link optimizer demo"
	@echo "  make demo-affinity      - Run affinity graph demo"
	@echo "  make demo-evaluator     - Run placement evaluator demo"
	@echo "  make demo-simulator     - Run time-based event simulator demo"
	@echo "  make demo-all           - Run all 4 demo scripts"
	@echo "  make micro-test         - Run Phase 1 Micro-Test (Fig 3 replica)"
	@echo "  make macro-test         - Run Phase 1 Macro-Test (Fig 9 replica)"
	@echo "  make real-workload      - Run real-world Philly trace cluster experiment"
	@echo "  make large-scale        - Run 2,000-job production cluster experiment"
	@echo "  make validate-baseline  - Run both micro and macro baseline tests"
	@echo "  make test               - Run unit tests"
	@echo "  make clean-png          - Delete generated PNG files (Preserves GIF files)"
	@echo "  make clean              - Delete generated PNGs and pycache (Preserves GIF files)"

demo-link:
	$(PYTHON) examples/demo_link_optimizer.py

demo-affinity:
	$(PYTHON) examples/demo_affinity_graph.py

demo-evaluator:
	$(PYTHON) examples/demo_evaluator.py

demo-simulator:
	$(PYTHON) examples/demo_simulator.py

demo-all: demo-link demo-affinity demo-evaluator demo-simulator

micro-test:
	$(PYTHON) experiments/micro_test.py

macro-test:
	$(PYTHON) experiments/macro_test.py

real-workload:
	$(PYTHON) experiments/real_workload_experiment.py

large-scale:
	$(PYTHON) experiments/large_scale_2000_jobs.py

validate-baseline: micro-test macro-test

test:
	$(PYTHON) -m unittest discover tests

clean-png:
	$(PYTHON) -c "import glob, os; [os.remove(f) for f in glob.glob('visualizations/**/*.png', recursive=True) + glob.glob('visualizations/*.png') + glob.glob('*.png') if os.path.exists(f) and not f.endswith('.gif')]; print('Cleaned PNG files. (Preserved all GIF files)')"

clean: clean-png
	$(PYTHON) -c "import shutil, glob, os; [shutil.rmtree(p) for p in glob.glob('**/__pycache__', recursive=True) if os.path.exists(p)]"
