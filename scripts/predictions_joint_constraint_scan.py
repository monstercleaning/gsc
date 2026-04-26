#!/usr/bin/env python3
"""
predictions_joint_constraint_scan.py — scan the σ(z) ansatz parameter space
and report joint pass/fail outcomes across all data-bearing predictions.

For each value of the σ(z) powerlaw exponent p in a log-spaced grid, the
script regenerates the parameter-dependent predictions (P1, P4, P5, P8) and
reports the joint outcome. p-independent predictions (P3, P6, P7) are run
once and noted.

This is a *joint constraint analysis*: it identifies the parameter region of
σ(z) that simultaneously satisfies all currently-scored predictions.

Output:
- text or json table of (p, outcome_per_prediction, joint_outcome) rows
- annotation of "joint allowed" parameter window if non-empty

Usage:
    python3 scripts/predictions_joint_constraint_scan.py
    python3 scripts/predictions_joint_constraint_scan.py --p-min 1e-5 --p-max 1e-1 --n-points 21
    python3 scripts/predictions_joint_constraint_scan.py --format json > scan.json
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Predictions whose default outcome depends on the σ(z) powerlaw exponent p.
P_DEPENDENT_PREDICTIONS = ["P1", "P4", "P5", "P8"]

# Predictions whose outcome is set by other parameters (independent of p).
P_INDEPENDENT_PREDICTIONS = ["P3", "P6", "P7"]


def run_compute(prediction_id: str, p: float) -> dict | None:
    """Recompute a prediction with a specific p, return the pipeline output."""
    script = REPO_ROOT / "scripts" / f"predictions_compute_{prediction_id}.py"
    if not script.is_file():
        return None
    cmd = ["python3", str(script), "--p", str(p)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=str(REPO_ROOT)
        )
    except subprocess.CalledProcessError:
        return None
    out_path = (
        REPO_ROOT
        / "predictions_register"
        / f"{prediction_id}_*"
    )
    # Find matching directory.
    pid_dir = next(
        (d for d in (REPO_ROOT / "predictions_register").iterdir()
         if d.is_dir() and d.name.startswith(prediction_id + "_")),
        None,
    )
    if pid_dir is None:
        return None
    pipeline = pid_dir / "pipeline_output.json"
    if not pipeline.is_file():
        return None
    return json.loads(pipeline.read_text(encoding="utf-8"))


def run_scorer(prediction_id: str) -> str:
    """Run the scorer for a prediction; return the outcome label."""
    scorer = REPO_ROOT / "scripts" / f"predictions_score_{prediction_id}.py"
    if not scorer.is_file():
        return "NO-SCORER"
    try:
        result = subprocess.run(
            ["python3", str(scorer)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
    except subprocess.CalledProcessError:
        return "ERROR"
    for line in result.stdout.splitlines():
        if line.strip().startswith("outcome:"):
            return line.split(":", 1)[1].strip()
    return "UNKNOWN"


def joint_outcome(per_prediction: dict[str, str]) -> str:
    """Reduce per-prediction outcomes to a single joint label.

    PASS-only: every scored data-bearing prediction passes.
    FAIL-some: at least one prediction fails.
    SUB-only: every prediction is SUB-THRESHOLD or PASS (no FAILs but not all PASS).
    PENDING: no scored predictions (data still pending).
    """
    outcomes = [v for v in per_prediction.values() if v not in ("NO-SCORER", "PENDING-DATA", "PENDING-SCORER")]
    if not outcomes:
        return "PENDING"
    if any(o == "FAIL" for o in outcomes):
        return "FAIL-some"
    if all(o == "PASS" for o in outcomes):
        return "PASS-only"
    return "MIXED"


def scan_p(p_values: list[float]) -> list[dict]:
    """For each p in p_values, recompute the p-dependent predictions and score them."""
    rows: list[dict] = []
    for p in p_values:
        per_pred: dict[str, str] = {}
        for pid in P_DEPENDENT_PREDICTIONS:
            run_compute(pid, p)
            per_pred[pid] = run_scorer(pid)
        rows.append(
            {
                "p": float(p),
                "log10_p": round(math.log10(p), 4),
                "outcomes": per_pred,
                "joint": joint_outcome(per_pred),
            }
        )
    return rows


def render_text(rows: list[dict], independent_outcomes: dict[str, str]) -> str:
    lines: list[str] = []
    lines.append("# Joint constraint scan over σ(z) powerlaw exponent p\n")
    lines.append("p-independent predictions (held fixed across the scan):")
    for pid in P_INDEPENDENT_PREDICTIONS:
        lines.append(f"  {pid}: {independent_outcomes.get(pid, 'NO-SCORER')}")
    lines.append("")
    headers = ["log10(p)"] + P_DEPENDENT_PREDICTIONS + ["JOINT"]
    lines.append("  ".join(f"{h:<14s}" for h in headers))
    lines.append("-" * (16 * len(headers)))
    for r in rows:
        cells = [f"{r['log10_p']:>+8.3f}"]
        for pid in P_DEPENDENT_PREDICTIONS:
            cells.append(f"{r['outcomes'].get(pid, '-'):<14s}")
        cells.append(f"{r['joint']:<14s}")
        lines.append("  ".join(c.ljust(14) for c in cells))
    lines.append("")

    pass_only = [r for r in rows if r["joint"] == "PASS-only"]
    if pass_only:
        ps = [r["p"] for r in pass_only]
        lines.append(
            f"## Joint allowed window: p ∈ [{min(ps):.2e}, {max(ps):.2e}]"
        )
    else:
        lines.append("## Joint allowed window: empty (no p value passes all scored predictions)")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_json(rows: list[dict], independent_outcomes: dict[str, str]) -> str:
    return json.dumps(
        {
            "p_dependent_scan": rows,
            "p_independent_outcomes": independent_outcomes,
            "joint_pass_only_p_values": [
                r["p"] for r in rows if r["joint"] == "PASS-only"
            ],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--p-min", type=float, default=1e-5)
    parser.add_argument("--p-max", type=float, default=1e-1)
    parser.add_argument("--n-points", type=int, default=11)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    log_p_min = math.log10(args.p_min)
    log_p_max = math.log10(args.p_max)
    p_values = [
        10 ** (log_p_min + (log_p_max - log_p_min) * i / (args.n_points - 1))
        for i in range(args.n_points)
    ]

    # Run p-independent predictions once (they don't depend on the scan parameter).
    independent_outcomes: dict[str, str] = {}
    for pid in P_INDEPENDENT_PREDICTIONS:
        # Recompute (use defaults) before scoring so pipeline_output.json is fresh.
        compute_script = REPO_ROOT / "scripts" / f"predictions_compute_{pid}.py"
        if compute_script.is_file():
            try:
                subprocess.run(
                    ["python3", str(compute_script)],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=str(REPO_ROOT),
                )
            except subprocess.CalledProcessError:
                pass
        independent_outcomes[pid] = run_scorer(pid)

    rows = scan_p(p_values)

    if args.format == "json":
        sys.stdout.write(render_json(rows, independent_outcomes))
    else:
        sys.stdout.write(render_text(rows, independent_outcomes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
