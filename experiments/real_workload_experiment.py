"""Legacy entry point. Use cassini.py experiment for current options."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cassini import main


if __name__ == "__main__":
    sys.exit(main(["experiment", "--trace", "data/traces/philly_cluster_trace.json", "--jobs", "60", "--links", "16", "--score-horizon", "2000", "--out", "output/sample"] + sys.argv[1:]))
