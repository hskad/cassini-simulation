"""Legacy entry point. Use cassini.py experiment for current options."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cassini import main


if __name__ == "__main__":
    sys.exit(main(["experiment", "--trace", "data/traces/philly_2000_jobs.json", "--jobs", "2000", "--links", "32", "--score-horizon", "2000", "--no-history", "--out", "output/large-scale"] + sys.argv[1:]))

