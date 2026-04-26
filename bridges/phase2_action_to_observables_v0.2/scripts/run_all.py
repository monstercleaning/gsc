"""
Run all Phase 2 scripts and regenerate outputs.

Usage:
    python run_all.py

This will (re)create figures in ../outputs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(script: Path) -> None:
    print(f"[run_all] Running: {script.name}")
    subprocess.run([sys.executable, str(script)], check=True)


def main() -> None:
    here = Path(__file__).resolve().parent
    scripts = [
        here / "phase2_action_solver.py",
        here / "phase2_action_distance_compare.py",
        here / "phase2_distance_drift_tradeoff.py",
        here / "phase2_action_tradeoff_scan.py",
    ]
    for s in scripts:
        run(s)
    print("[run_all] Done.")


if __name__ == "__main__":
    main()
