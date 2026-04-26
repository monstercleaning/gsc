
"""
Run all Phase 3 v0.2 scripts and regenerate outputs.

Usage:
  python run_all.py
"""
import subprocess, sys, os
from pathlib import Path

SCRIPTS = [
    "phase3_cmb_theta_star_action.py",
    "phase3_bao_fs_scan.py",
    "phase3_growth_curves.py",
]

def main():
    root = Path(__file__).resolve().parent
    os.chdir(root)
    for s in SCRIPTS:
        print(f"[run] {s}")
        subprocess.check_call([sys.executable, s])

if __name__ == "__main__":
    main()
