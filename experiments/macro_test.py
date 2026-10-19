"""Legacy entry point. Use cassini.py experiment for current options."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cassini import main


if __name__ == "__main__":
    sys.exit(main(["experiment", "--jobs", "50", "--links", "16", "--out", "output/macro"] + sys.argv[1:]))
