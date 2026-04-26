#!/usr/bin/env python3
"""
predictions_score_P6.py — score Prediction P6 against PTA stochastic GW bounds.

Scores the GSC-predicted Ω_GW from KZ defect-formation against the current
stochastic background upper bound from PTAs (NANOGrav 15-yr + EPTA DR2).

Usage:
    python3 scripts/predictions_score_P6.py
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRED_DIR = REPO_ROOT / "predictions_register" / "P6_kz_defect_spectrum"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def score_p6(*, pipeline_path: Path, observed_path: Path) -> dict:
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    observed = json.loads(observed_path.read_text(encoding="utf-8"))

    omega_gw_pred = pipeline["gw_background_prediction"]["Omega_GW_typical"]
    omega_gw_bound = float(observed["stochastic_omega_gw_upper_bound"])
    G_mu = pipeline["gw_background_prediction"]["G_mu_dimensionless"]
    M_star = pipeline["gw_background_prediction"]["M_star_GeV"]

    ratio = omega_gw_pred / omega_gw_bound
    overall_pass = omega_gw_pred < omega_gw_bound

    return {
        "scorecard_schema": "predictions_p6_scorecard_v1",
        "prediction_id": "P6",
        "pipeline_output_hash_at_scoring": sha256_of_file(pipeline_path),
        "observed_source": observed.get("source", "unknown"),
        "observed_data_release_date": observed.get("data_release_date", "unknown"),
        "pta_check": {
            "predicted_Omega_GW": float(f"{omega_gw_pred:.3e}"),
            "PTA_upper_bound_Omega_GW": float(f"{omega_gw_bound:.3e}"),
            "predicted_to_bound_ratio": float(f"{ratio:.3e}"),
            "G_mu_dimensionless": float(f"{G_mu:.3e}"),
            "M_star_GeV": float(f"{M_star:.3e}"),
            "pass": overall_pass,
        },
        "overall_outcome": "PASS" if overall_pass else "FAIL",
        "interpretation": (
            "PASS: predicted stochastic GW background from KZ defect formation "
            "is below the current PTA upper bound."
            if overall_pass
            else f"FAIL: predicted Ω_GW = {omega_gw_pred:.2e} exceeds the PTA "
            f"upper bound {omega_gw_bound:.2e} by a factor of {ratio:.2e}. "
            f"Default M_* = {M_star:.0e} GeV is excluded; reduce M_* (or modify "
            "ν, z critical exponents) until the prediction is below the PTA "
            "bound. As a rough rule of thumb, M_* ≲ TeV-scale is required."
        ),
    }


def render_scorecard(card: dict, scored_at_utc: str) -> str:
    overall = card["overall_outcome"]
    badge = "✅ PASS" if overall == "PASS" else "❌ FAIL"
    parts: list[str] = []
    parts.append(f"# Scorecard — Prediction P6 (Kibble-Zurek defect spectrum)\n")
    parts.append(f"**Outcome:** {badge}\n")
    parts.append(f"**Scored at:** `{scored_at_utc}`\n")
    parts.append(
        f"**Pipeline output hash:** `{card['pipeline_output_hash_at_scoring']}`\n"
    )
    parts.append(
        f"**Observed source:** {card['observed_source']} "
        f"(released {card['observed_data_release_date']})\n"
    )

    p = card["pta_check"]
    parts.append("\n## PTA stochastic-bound check\n")
    parts.append(
        f"| Quantity | Value |\n|---|---|\n"
        f"| Predicted Ω_GW | {p['predicted_Omega_GW']} |\n"
        f"| PTA upper bound | {p['PTA_upper_bound_Omega_GW']} |\n"
        f"| Ratio (pred/bound) | {p['predicted_to_bound_ratio']} |\n"
        f"| G μ (string tension) | {p['G_mu_dimensionless']} |\n"
        f"| M_* (registered) | {p['M_star_GeV']} GeV |\n"
        f"| Pass | {'✓' if p['pass'] else '✗'} |\n"
    )
    parts.append("\n## Interpretation\n")
    parts.append(card["interpretation"] + "\n")
    parts.append(
        "\n## Reproduce\n\n"
        "```bash\n"
        "python3 scripts/predictions_compute_P6.py\n"
        "python3 scripts/predictions_score_P6.py\n"
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

    card = score_p6(pipeline_path=args.pipeline, observed_path=args.observed)
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
