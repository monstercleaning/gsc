#!/usr/bin/env python3
"""
predictions_score_P9.py — score Prediction P9 against current μ̇/μ bounds.

Under universal scaling, GSC predicts μ̇/μ = 0. This is a null prediction:
the test is whether observed bounds are consistent with 0. Currently both
laboratory (HD+) and cosmological (H2 absorbers) bounds are consistent
with μ̇/μ = 0, so the framework's universal-scaling assumption survives.

Usage:
    python3 scripts/predictions_score_P9.py
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRED_DIR = REPO_ROOT / "predictions_register" / "P9_proton_electron_mass_ratio"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def score_p9(*, pipeline_path: Path, observed_path: Path) -> dict:
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    observed = json.loads(observed_path.read_text(encoding="utf-8"))

    mu_dot_pred = pipeline["prediction"]["mu_dot_over_mu_z0_per_yr"]
    bound = float(observed["mu_dot_over_mu_bound_per_yr"])

    # Predicted is 0 under universal scaling. Bound is upper limit.
    # PASS if |predicted| < bound at registered confidence level.
    abs_pred = abs(mu_dot_pred)
    pass_check = abs_pred < bound

    # Cosmological check
    delta_mu_bound = float(observed.get("delta_mu_over_mu_bound_at_z2_to_3", 1e-6))
    delta_mu_pred_at_z2 = abs(
        next(
            (r for r in pipeline["prediction"]["trajectory"] if r["z"] == 2.0),
            {"delta_mu_over_mu_predicted": 0.0},
        )["delta_mu_over_mu_predicted"]
    )
    pass_cosmological = delta_mu_pred_at_z2 < delta_mu_bound

    overall_pass = pass_check and pass_cosmological

    return {
        "scorecard_schema": "predictions_p9_scorecard_v1",
        "prediction_id": "P9",
        "pipeline_output_hash_at_scoring": sha256_of_file(pipeline_path),
        "observed_source": observed.get("source", "unknown"),
        "observed_data_release_date": observed.get("data_release_date", "unknown"),
        "lab_check": {
            "predicted_abs_mu_dot_per_yr": float(f"{abs_pred:.3e}"),
            "observed_bound_per_yr": float(f"{bound:.3e}"),
            "pass": pass_check,
        },
        "cosmological_check": {
            "predicted_abs_delta_mu_at_z2": float(f"{delta_mu_pred_at_z2:.3e}"),
            "observed_bound_delta_mu_at_z2_to_3": float(f"{delta_mu_bound:.3e}"),
            "pass": pass_cosmological,
        },
        "overall_outcome": "PASS" if overall_pass else "FAIL",
        "interpretation": (
            "PASS: μ̇/μ and Δμ/μ predictions (both 0 under universal coherent "
            "scaling) are consistent with current laboratory (HD+) and "
            "cosmological (H2 absorbers) bounds. The geometric-lock condition "
            "(T1) is not falsified by current data on the proton-electron mass "
            "ratio."
            if overall_pass
            else "FAIL: a non-zero prediction is in tension with observed bounds. "
            "If running in non-universal mode, this constrains the differential "
            "coupling η_QCD - η_Higgs."
        ),
    }


def render_scorecard(card: dict, scored_at_utc: str) -> str:
    badge = "✅ PASS" if card["overall_outcome"] == "PASS" else "❌ FAIL"
    parts: list[str] = []
    parts.append(f"# Scorecard — Prediction P9 (μ = m_p/m_e constancy)\n")
    parts.append(f"**Outcome:** {badge}\n")
    parts.append(f"**Scored at:** `{scored_at_utc}`\n")
    parts.append(
        f"**Pipeline output hash:** `{card['pipeline_output_hash_at_scoring']}`\n"
    )
    parts.append(
        f"**Observed source:** {card['observed_source']} (released {card['observed_data_release_date']})\n"
    )
    lab = card["lab_check"]
    parts.append("\n## Laboratory check (HD+ ion trap)\n")
    parts.append(
        f"| Quantity | Value |\n|---|---|\n"
        f"| |μ̇/μ| predicted | {lab['predicted_abs_mu_dot_per_yr']} /yr |\n"
        f"| Observed bound | {lab['observed_bound_per_yr']} /yr |\n"
        f"| Pass | {'✓' if lab['pass'] else '✗'} |\n"
    )
    cos = card["cosmological_check"]
    parts.append("\n## Cosmological check (H2 absorbers at z~2-3)\n")
    parts.append(
        f"| Quantity | Value |\n|---|---|\n"
        f"| |Δμ/μ| predicted at z=2 | {cos['predicted_abs_delta_mu_at_z2']} |\n"
        f"| Observed bound at z=2-3 | {cos['observed_bound_delta_mu_at_z2_to_3']} |\n"
        f"| Pass | {'✓' if cos['pass'] else '✗'} |\n"
    )
    parts.append("\n## Interpretation\n")
    parts.append(card["interpretation"] + "\n")
    parts.append(
        "\n## Reproduce\n\n"
        "```bash\n"
        "python3 scripts/predictions_compute_P9.py\n"
        "python3 scripts/predictions_score_P9.py\n"
        "```\n"
    )
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pipeline", type=Path, default=PRED_DIR / "pipeline_output.json")
    parser.add_argument("--observed", type=Path, default=PRED_DIR / "observed_data.json")
    parser.add_argument("--output", type=Path, default=PRED_DIR / "scorecard.md")
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    if not args.pipeline.is_file():
        sys.stderr.write(f"error: pipeline output missing: {args.pipeline}\n")
        return 2
    if not args.observed.is_file():
        sys.stderr.write(f"error: observed data missing: {args.observed}\n")
        return 2

    card = score_p9(pipeline_path=args.pipeline, observed_path=args.observed)
    timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rendered = render_scorecard(card, timestamp)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(f"wrote {args.output}\n")
    sys.stdout.write(f"  outcome: {card['overall_outcome']}\n")
    if args.print:
        sys.stdout.write("\n" + rendered)
    return 0 if card["overall_outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
