#!/usr/bin/env python3
"""
predictions_joint_constraint_scan.py — scan the σ(z) ansatz parameter space
and report joint pass/fail outcomes across all data-bearing predictions.

For each value of the σ(z) powerlaw exponent p in a log-spaced grid, the
script recomputes the parameter-dependent predictions (P1, P4, P5, P8) and
scores them against their registered observed data. p-independent predictions
(P3, P6, P7) are scored once from their registered outputs.

This is a *joint constraint analysis*: it identifies the parameter region of
σ(z) that simultaneously satisfies all currently-scored predictions. It is a
diagnostic, not a registered result.

Everything runs in a temporary folder: registered outputs and scorecards are
never touched. A prediction without a scorer or observed data is reported as
UNSCORED, which is not an exclusion. Any failed computation or scorer crash
stops the scan with exit status 2, so an unavailable result can never be read
as an empty window. (Until v20.2 the script looked in a folder that no longer
existed, scored nothing, and still reported an empty window.)

Output:
- text or json table of (p, outcome_per_prediction, joint_outcome) rows
- the joint allowed window over the scored predictions, if non-empty

Usage:
    python3 pipelines/predictions_joint_constraint_scan.py
    python3 pipelines/predictions_joint_constraint_scan.py --p-min 1e-5 --p-max 1e-1 --n-points 21
    python3 pipelines/predictions_joint_constraint_scan.py --format json > scan.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINES = REPO_ROOT / "pipelines"
REGISTER = REPO_ROOT / "predictions"

# Predictions whose default outcome depends on the σ(z) powerlaw exponent p.
P_DEPENDENT_PREDICTIONS = ["P1", "P4", "P5", "P8"]

# Predictions whose outcome is set by other parameters (independent of p).
P_INDEPENDENT_PREDICTIONS = ["P3", "P6", "P7"]

UNSCORED = "UNSCORED"


class ScanError(RuntimeError):
    """A computation or scorer that should have run did not."""


def entry_dir(prediction_id: str) -> Path:
    number = int(prediction_id.lstrip("P"))
    for d in sorted(REGISTER.iterdir()):
        m = re.match(r"P0*(\d+)_", d.name)
        if d.is_dir() and m and int(m.group(1)) == number:
            return d
    raise ScanError(f"{prediction_id}: no register entry")


def run_compute(prediction_id: str, p: float, workdir: Path) -> Path:
    """Recompute a prediction at exponent p into the work folder; return the output path."""
    script = PIPELINES / f"predictions_compute_{prediction_id}.py"
    if not script.is_file():
        raise ScanError(f"{prediction_id}: no pipeline {script.name}")
    out = workdir / f"{prediction_id}_p{p:.6e}.json"
    result = subprocess.run([sys.executable, str(script), "--p", repr(p), "--output", str(out)],
                            capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0 or not out.is_file():
        raise ScanError(f"{prediction_id} at p = {p:.3e}: pipeline failed\n{result.stderr[-500:]}")
    return out


def run_scorer(prediction_id: str, pipeline_path: Path, workdir: Path) -> str:
    """Score a pipeline output against the registered observed data; return the outcome word."""
    scorer = PIPELINES / f"predictions_score_{prediction_id}.py"
    observed = entry_dir(prediction_id) / "observed_data.json"
    if not scorer.is_file() or not observed.is_file():
        return UNSCORED
    card = workdir / f"{pipeline_path.stem}_scorecard.md"
    result = subprocess.run([sys.executable, str(scorer), "--pipeline", str(pipeline_path),
                             "--observed", str(observed), "--output", str(card)],
                            capture_output=True, text=True, cwd=str(REPO_ROOT))
    m = re.search(r"outcome:\s*([A-Z-]+)", result.stdout)
    # Scorers exit 1 on a FAIL verdict; anything else non-zero, or no outcome, is a crash.
    if m is None or result.returncode > 1 or (result.returncode == 1 and m.group(1) != "FAIL"):
        raise ScanError(f"{prediction_id}: scorer crashed (exit {result.returncode})\n{result.stderr[-500:]}")
    return m.group(1)


def joint_outcome(per_prediction: dict[str, str]) -> str:
    """Reduce per-prediction outcomes to a single joint label.

    PASS-only: every scored prediction passes.
    FAIL-some: at least one scored prediction fails.
    MIXED: no FAILs, but not all PASS.
    UNSCORED: nothing was scored.
    """
    outcomes = [v for v in per_prediction.values() if v != UNSCORED]
    if not outcomes:
        return UNSCORED
    if any(o == "FAIL" for o in outcomes):
        return "FAIL-some"
    if all(o == "PASS" for o in outcomes):
        return "PASS-only"
    return "MIXED"


def scan_p(p_values: list[float], workdir: Path) -> list[dict]:
    """For each p in p_values, recompute the p-dependent predictions and score them."""
    rows: list[dict] = []
    for p in p_values:
        per_pred: dict[str, str] = {}
        for pid in P_DEPENDENT_PREDICTIONS:
            per_pred[pid] = run_scorer(pid, run_compute(pid, p, workdir), workdir)
        rows.append({"p": float(p), "log10_p": round(math.log10(p), 4), "outcomes": per_pred,
                     "joint": joint_outcome(per_pred)})
    return rows


def window(rows: list[dict]) -> str:
    if all(r["joint"] == UNSCORED for r in rows):
        return "## Joint allowed window: not determined (nothing was scored)"
    pass_only = [r["p"] for r in rows if r["joint"] == "PASS-only"]
    if pass_only:
        return f"## Joint allowed window: p ∈ [{min(pass_only):.2e}, {max(pass_only):.2e}] (grid points passing every scored p-dependent prediction)"
    return "## Joint allowed window: empty (no grid point passes every scored p-dependent prediction)"


def render_text(rows: list[dict], independent_outcomes: dict[str, str]) -> str:
    lines: list[str] = []
    lines.append("# Joint constraint scan over σ(z) powerlaw exponent p\n")
    lines.append("p-independent predictions (scored once from their registered outputs):")
    for pid in P_INDEPENDENT_PREDICTIONS:
        lines.append(f"  {pid}: {independent_outcomes[pid]}")
    unscored = [pid for pid in P_DEPENDENT_PREDICTIONS if all(r["outcomes"][pid] == UNSCORED for r in rows)]
    if unscored:
        lines.append(f"Unscored (no scorer or no observed data; not exclusions): {', '.join(unscored)}")
    lines.append("")
    headers = ["log10(p)"] + P_DEPENDENT_PREDICTIONS + ["JOINT"]
    lines.append("  ".join(f"{h:<14s}" for h in headers))
    lines.append("-" * (16 * len(headers)))
    for r in rows:
        cells = [f"{r['log10_p']:>+8.3f}"] + [r["outcomes"][pid] for pid in P_DEPENDENT_PREDICTIONS] + [r["joint"]]
        lines.append("  ".join(c.ljust(14) for c in cells))
    lines.append("")
    lines.append(window(rows))
    lines.append("")
    return "\n".join(lines) + "\n"


def render_json(rows: list[dict], independent_outcomes: dict[str, str]) -> str:
    return json.dumps(
        {
            "p_dependent_scan": rows,
            "p_independent_outcomes": independent_outcomes,
            "joint_pass_only_p_values": [r["p"] for r in rows if r["joint"] == "PASS-only"],
            "window": window(rows).removeprefix("## "),
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
    if args.n_points < 2 or not 0 < args.p_min < args.p_max:
        parser.error("need 0 < p-min < p-max and at least two points")

    log_p_min = math.log10(args.p_min)
    log_p_max = math.log10(args.p_max)
    p_values = [10 ** (log_p_min + (log_p_max - log_p_min) * i / (args.n_points - 1)) for i in range(args.n_points)]

    try:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            independent_outcomes = {pid: run_scorer(pid, entry_dir(pid) / "pipeline_output.json", work)
                                    for pid in P_INDEPENDENT_PREDICTIONS}
            rows = scan_p(p_values, work)
    except ScanError as exc:
        sys.stderr.write(f"joint scan stopped: {exc}\n")
        return 2

    sys.stdout.write(render_json(rows, independent_outcomes) if args.format == "json"
                     else render_text(rows, independent_outcomes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
