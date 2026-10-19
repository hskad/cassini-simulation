PYTHON ?= python3

.PHONY: help test demo docs experiment micro-test macro-test sample-trace large-scale scale-10k demo-link demo-affinity demo-evaluator demo-simulator demo-all validate-baseline

help:
	@echo Use python3 cassini.py, or use these make targets.
	@echo test demo docs experiment micro-test macro-test sample-trace large-scale scale-10k

test:
	$(PYTHON) cassini.py test

demo:
	$(PYTHON) cassini.py demo

docs:
	$(PYTHON) cassini.py docs

experiment:
	$(PYTHON) cassini.py experiment

micro-test:
	$(PYTHON) examples/demo_geometric.py

macro-test:
	$(PYTHON) cassini.py experiment --jobs 50 --links 16 --out output/macro

sample-trace:
	$(PYTHON) cassini.py experiment --trace data/traces/philly_cluster_trace.json --jobs 60 --links 16 --score-horizon 2000 --out output/sample

large-scale:
	$(PYTHON) cassini.py experiment --trace data/traces/philly_2000_jobs.json --jobs 2000 --links 32 --score-horizon 2000 --no-history --out output/large-scale

scale-10k:
	$(PYTHON) cassini.py experiment --trace data/traces/philly_10000_jobs.json --jobs 10000 --links 32 --score-horizon 2000 --no-history --out output/scale-10000

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
