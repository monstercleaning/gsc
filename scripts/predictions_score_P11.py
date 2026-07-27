#!/usr/bin/env python3
"""predictions_score_P11.py — score Prediction P11 (distance-duality null).

Compares the registered exact-null prediction (eta1 = 0) against the current
best linear-parametrization DDR constraint recorded in observed_data.json.

Registered rule (prediction.md): PASS if |z| < 3 where
    z = (eta1_observed - eta1_predicted) / eta1_sigma.

Sudden-death clause: a robust, calibration-robust, model-independent DDR
violation at >= 3 sigma falsifies T1 outright (GSC_Framework.md §12.2.1a).
This scorer only evaluates the linear-parametrization check; the robustness
qualifiers are assessed at framework level, not here.

Exit codes: 0 = PASS, 1 = FAIL, 2 = error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "predictions_register" / "P11_distance_duality"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--confidence", type=float, default=3.0,
        help="pass threshold in sigma; 3.0 is the REGISTERED rule (prediction.md: |z| < 3)",
    )
    parser.add_argument("--register-dir", default=str(REGISTER))
    args = parser.parse_args(argv)

    reg = Path(args.register_dir)
    pipeline_path = reg / "pipeline_output.json"
    observed_path = reg / "observed_data.json"
    if not pipeline_path.is_file() or not observed_path.is_file():
        sys.stderr.write("error: missing pipeline_output.json or observed_data.json\n")
        return 2

    payload = pipeline_path.read_text(encoding="utf-8")
    pipeline = json.loads(payload)
    observed = json.loads(observed_path.read_text(encoding="utf-8"))
    output_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    eta1_pred = float(pipeline["prediction"]["eta1_linear_coefficient"])
    eta1_obs = float(observed["eta1_observed"])
    sigma = float(observed["eta1_sigma"])
    z = (eta1_obs - eta1_pred) / sigma
    passed = abs(z) < args.confidence
    outcome = "PASS" if passed else "FAIL"

    scored_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    badge = "✅ PASS" if passed else "❌ FAIL"
    interp = (
        "PASS (retrodictive current-bounds check): the exact GSC null eta1 = 0 is "
        "consistent with the DESI-DR2-era linear-parametrization constraint at the "
        "registered |z| < 3 rule. Shared with ΛCDM — this check does not discriminate "
        "GSC from the standard model; its value is the standing sudden-death clause: "
        "any future robust (calibration-robust, model-independent) DDR violation at "
        "≥ 3σ falsifies T1 outright, and no correction may be invoked to rescue it "
        "(GSC_Framework.md §12.2.1/§12.2.1a)."
        if passed
        else "FAIL: the current linear-parametrization DDR constraint deviates from "
        "the exact GSC null at ≥ the registered confidence. If this deviation is "
        "calibration-robust and model-independent, T1 is falsified outright "
        "(GSC_Framework.md §12.2.1a); no correction may be invoked to rescue it."
    )

    card = "\n".join([
        "# Scorecard — Prediction P11 (distance-duality eta(z) = 1 null)",
        "",
        "> **RETRODICTIVE CURRENT-BOUNDS CHECK + STANDING FALSIFICATION CHANNEL.**",
        "> Scored against already-public DESI-DR2-era DDR constraints. The forward",
        "> content is the sudden-death clause: any future robust DDR violation at",
        "> ≥ 3σ falsifies T1 — a single confirmed violation suffices (no majority rule).",
        "",
        f"**Outcome:** {badge}  (at the registered |z| < {args.confidence:g} rule)",
        f"**Scored at:** `{scored_at}`",
        f"**Pipeline output hash:** `{output_hash}`",
        f"**Observed source:** {observed['data_source']}",
        "",
        "## Prediction vs observation",
        "| Quantity | Predicted | Observed | σ_obs | z-score |",
        "|---|---|---|---|---|",
        f"| η₁ (linear DDR deviation) | {eta1_pred:g} | {eta1_obs:g} | {sigma:g} | {z:+.3f} |",
        "",
        "## Interpretation",
        interp,
        "",
        "## Reproduce",
        "",
        "```bash",
        "python3 scripts/predictions_compute_P11.py",
        "python3 scripts/predictions_score_P11.py",
        "```",
        "",
    ])
    (reg / "scorecard.md").write_text(card, encoding="utf-8")
    print(f"P11 scorecard written; outcome: {outcome} (z = {z:+.3f}, rule |z| < {args.confidence:g})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
