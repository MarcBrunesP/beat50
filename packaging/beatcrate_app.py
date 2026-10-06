"""Entry point of the packaged app: a double-click runs `beatcrate app`.

A packaged app has no terminal, so its output goes to ~/Library/Logs/beatcrate.log: it is the only place
a startup failure (for example, port 8765 taken by another program) can show up.
"""
import sys
import traceback
from pathlib import Path

from beatcrate.cli import main

if getattr(sys, "frozen", False):
    logs = Path.home() / "Library" / "Logs"
    logs.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = open(logs / "beatcrate.log", "a", buffering=1)

args = [a for a in sys.argv[1:] if not a.startswith("-psn_")]  # older macOS versions pass -psn_*
try:
    sys.exit(main(args or ["app"]))
except Exception:
    traceback.print_exc()
    sys.exit(1)
