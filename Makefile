PYTHON ?= python

.PHONY: help test demo experiment micro-test macro-test real-workload large-scale scale-10k demo-link demo-affinity demo-evaluator demo-simulator demo-all validate-baseline

help:
	@echo Run cassini.bat from Windows CMD, or use these make targets.
	@echo test demo experiment micro-test macro-test real-workload large-scale scale-10k

test:
	$(PYTHON) cassini.py test

demo:
	$(PYTHON) cassini.py demo

experiment:
	$(PYTHON) cassini.py experiment

micro-test:
	$(PYTHON) experiments/micro_test.py

macro-test:
	$(PYTHON) experiments/macro_test.py

real-workload:
	$(PYTHON) experiments/real_workload_experiment.py

large-scale:
	$(PYTHON) experiments/large_scale_2000_jobs.py

scale-10k:
	$(PYTHON) experiments/scale_10000_jobs.py

demo-link:
	$(PYTHON) examples/demo_link_optimizer.py

demo-affinity:
	$(PYTHON) examples/demo_affinity_graph.py

demo-evaluator:
	$(PYTHON) examples/demo_evaluator.py

demo-simulator:
	$(PYTHON) examples/demo_simulator.py

demo-all: demo-link demo-affinity demo-evaluator demo-simulator

validate-baseline: test demo

