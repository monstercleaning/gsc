#!/usr/bin/env python3
"""
predictions_score_P4.py — score Prediction P4 against observed CMB birefringence.

Reads:
  predictions_register/P4_cmb_birefringence/pipeline_output.json
  predictions_register/P4_cmb_birefringence/observed_data.json

Computes the z-score of the GSC-predicted birefringence angle β against the
observed Planck (Minami & Komatsu 2020) hint, and writes scorecard.md with
pass/fail at the registered confidence level.

Usage:
    python3 scripts/predictions_score_P4.py
    python3 scripts/predictions_score_P4.py --confidence 3
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRED_DIR = REPO_ROOT / "predictions_register" / "P4_cmb_birefringence"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def score_p4(*, pipeline_path: Path, observed_path: Path, confidence_sigma: float) -> dict:
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    observed = json.loads(observed_path.read_text(encoding="utf-8"))

    beta_pred = pipeline["prediction"]["beta_deg"]
    beta_obs = observed["beta_observed_deg"]
    sigma_obs = observed["beta_observed_sigma_deg"]
    sigma_pred = 0.0  # parameter-band uncertainty would go here

    diff = beta_pred - beta_obs
    sigma_combined = (sigma_obs ** 2 + sigma_pred ** 2) ** 0.5
    z = diff / sigma_combined

    overall_pass = abs(z) < confidence_sigma

    return {
        "scorecard_schema": "predictions_p4_scorecard_v1",
        "prediction_id": "P4",
        "scoring_confidence_sigma": confidence_sigma,
        "pipeline_output_hash_at_scoring": sha256_of_file(pipeline_path),
        "observed_source": observed.get("source", "unknown"),
        "observed_data_release_date": observed.get("data_release_date", "unknown"),
        "predicted_beta_deg": beta_pred,
        "observed_beta_deg": beta_obs,
        "observed_beta_sigma_deg": sigma_obs,
        "z_score": round(z, 4),
        "overall_outcome": "PASS" if overall_pass else "FAIL",
        "interpretation": (
            "PASS: GSC-predicted CMB birefringence is consistent with the Planck "
            "(Minami & Komatsu 2020) hint at the registered confidence level."
            if overall_pass
            else "FAIL: GSC-predicted birefringence amplitude is in tension with "
            "the Planck (Minami & Komatsu 2020) hint at the registered confidence "
            "level. Either (i) the σ-Chern-Simons coupling g_CS must be larger "
            "than the registered value (requires FRG-derived f_σ from Paper B), "
            "(ii) the σ-evolution amplitude p must be larger (would conflict with "
            "the late-time fit), or (iii) the Planck hint originates from a "
            "different mechanism (e.g., systematic effect; SARAS3 disputes the "
            "EDGES analogue). LiteBIRD (~2030) will sharpen this test."
        ),
    }


def render_scorecard(card: dict, scored_at_utc: str) -> str:
    overall = card["overall_outcome"]
    badge = "✅ PASS" if overall == "PASS" else "❌ FAIL"
    parts: list[str] = []
    parts.append(f"# Scorecard — Prediction P4 (CMB cosmic birefringence)\n")
    parts.append(f"**Outcome:** {badge}  (at {card['scoring_confidence_sigma']}σ confidence)\n")
    parts.append(f"**Scored at:** `{scored_at_utc}`\n")
    parts.append(
        f"**Pipeline output hash:** `{card['pipeline_output_hash_at_scoring']}`\n"
    )
    parts.append(
        f"**Observed data source:** {card['observed_source']} "
        f"(released {card['observed_data_release_date']})\n"
    )
    parts.append("\n## Prediction vs observation\n")
    parts.append(
        f"| Quantity | Predicted | Observed | σ_obs | z-score |\n"
        f"|---|---|---|---|---|\n"
        f"| β (degrees) | {card['predicted_beta_deg']:.4f} | "
        f"{card['observed_beta_deg']} | {card['observed_beta_sigma_deg']} | "
        f"{card['z_score']:+.4f} |\n"
    )
    parts.append("\n## Interpretation\n")
    parts.append(card["interpretation"] + "\n")
    parts.append(
        "\n## Reproduce\n\n"
        "```bash\n"
        "python3 scripts/predictions_compute_P4.py\n"
        "python3 scripts/predictions_score_P4.py\n"
        "```\n"
    )
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pipeline", type=Path, default=PRED_DIR / "pipeline_output.json")
    parser.add_argument("--observed", type=Path, default=PRED_DIR / "observed_data.json")
    parser.add_argument("--confidence", type=float, default=2.0)
    parser.add_argument("--output", type=Path, default=PRED_DIR / "scorecard.md")
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    if not args.pipeline.is_file():
        sys.stderr.write(f"error: pipeline output missing: {args.pipeline}\n")
        return 2
    if not args.observed.is_file():
        sys.stderr.write(f"error: observed data missing: {args.observed}\n")
        return 2

    card = score_p4(
        pipeline_path=args.pipeline,
        observed_path=args.observed,
        confidence_sigma=args.confidence,
    )
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
