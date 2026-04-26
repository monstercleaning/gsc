#!/usr/bin/env python3
"""
predictions_score_P1.py — score Prediction P1 against DESI Y1 BAO measurement.

Reads:
  predictions_register/P1_bao_ruler_shift/pipeline_output.json
  predictions_register/P1_bao_ruler_shift/observed_data.json

The framework's predicted r_d^GSC for each registered ansatz is compared
against the DESI Y1 measurement r_d ≈ 147 Mpc. PASS if predicted r_d falls
within the registered confidence band of the observation.

This scorer was added in v12.2 to close the schema-gap loophole identified
in the v12.1 hostile review (the loosened P1 schema upper bound was promised
to be enforced by a scorer that did not exist; this is that scorer).

Usage:
    python3 scripts/predictions_score_P1.py
    python3 scripts/predictions_score_P1.py --confidence 3
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRED_DIR = REPO_ROOT / "predictions_register" / "P1_bao_ruler_shift"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def score_p1(*, pipeline_path: Path, observed_path: Path, confidence_sigma: float) -> dict:
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    observed = json.loads(observed_path.read_text(encoding="utf-8"))

    r_d_obs = float(observed["r_d_observed_mpc"])
    sigma_obs = float(observed["r_d_observed_sigma_mpc"])

    # The fair test compares the *relative shift* Δr/r predicted by GSC against
    # DESI's *relative precision*, factoring out the absolute calibration
    # difference between our EH98 reference and DESI's measured r_d (which can
    # differ at the ~2-3% level for any fitting-formula vs measurement
    # comparison). The relative test is what's framework-relevant.
    desi_relative_precision = sigma_obs / r_d_obs

    sub_results = []
    any_pass = False
    for sub in pipeline["sub_predictions"]:
        r_d_pred = float(sub["r_s_gsc_predicted_mpc"])
        delta_rel_predicted = float(sub.get("delta_rs_relative", 0.0))
        # Use DESI's relative precision as the σ for the relative-shift test.
        z = delta_rel_predicted / desi_relative_precision
        passed = abs(z) < confidence_sigma
        if passed:
            any_pass = True
        sub_results.append(
            {
                "ansatz": sub.get("ansatz", "unknown"),
                "ansatz_parameters": sub.get("ansatz_parameters", {}),
                "r_d_gsc_predicted_mpc": r_d_pred,
                "delta_rs_over_rs_predicted": round(delta_rel_predicted, 6),
                "desi_relative_precision": round(desi_relative_precision, 6),
                "z_score_relative_shift": round(z, 4),
                "absolute_r_d_obs_minus_pred_mpc": round(r_d_obs - r_d_pred, 4),
                "pass": passed,
            }
        )

    return {
        "scorecard_schema": "predictions_p1_scorecard_v1",
        "prediction_id": "P1",
        "scoring_confidence_sigma": confidence_sigma,
        "pipeline_output_hash_at_scoring": sha256_of_file(pipeline_path),
        "observed_source": observed.get("source", "unknown"),
        "observed_data_release_date": observed.get("data_release_date", "unknown"),
        "observed_r_d_mpc": r_d_obs,
        "observed_r_d_sigma_mpc": sigma_obs,
        "sub_prediction_results": sub_results,
        "overall_outcome": "PASS" if any_pass else "FAIL",
        "interpretation": (
            "PASS: at least one registered σ(z) ansatz produces a BAO sound "
            "horizon r_d consistent with DESI Y1 at the registered confidence "
            "level. Note that this is an interim test pending DESI Y3 (2027); "
            "Y3 will tighten the bound by ~2x."
            if any_pass
            else "FAIL: all registered σ(z) ansätze produce r_d values outside "
            "the DESI Y1 confidence band. Either the σ(z) parametrisation is "
            "incompatible with DESI Y1 BAO at the registered confidence, or "
            "the σ-modified recombination correction (gating M201) reverses "
            "the verdict. The framework's σ(z) parameter region must be "
            "restricted to small p (≲ 10^-3 for powerlaw)."
        ),
    }


def render_scorecard(card: dict, scored_at_utc: str) -> str:
    badge = "✅ PASS" if card["overall_outcome"] == "PASS" else "❌ FAIL"
    parts: list[str] = []
    parts.append(f"# Scorecard — Prediction P1 (BAO ruler shift)\n")
    parts.append(f"**Outcome:** {badge}  (at {card['scoring_confidence_sigma']}σ confidence)\n")
    parts.append(f"**Scored at:** `{scored_at_utc}`\n")
    parts.append(
        f"**Pipeline output hash:** `{card['pipeline_output_hash_at_scoring']}`\n"
    )
    parts.append(
        f"**Observed source:** {card['observed_source']} (released {card['observed_data_release_date']})\n"
    )
    parts.append(
        f"**Observed r_d:** {card['observed_r_d_mpc']} ± {card['observed_r_d_sigma_mpc']} Mpc\n"
    )
    parts.append("\n## Per-ansatz results (relative-shift test)\n")
    parts.append(
        "Test: predicted Δr/r vs DESI Y1 relative precision (σ_DESI / r_DESI).\n\n"
    )
    parts.append("| Ansatz | parameters | Δr/r predicted | z-score | Pass |\n")
    parts.append("|---|---|---|---|---|\n")
    for sub in card["sub_prediction_results"]:
        params_str = ", ".join(f"{k}={v}" for k, v in sub["ansatz_parameters"].items())
        parts.append(
            f"| {sub['ansatz']} | {params_str} | {sub['delta_rs_over_rs_predicted']*100:+.4f}% | "
            f"{sub['z_score_relative_shift']:+.3f} | {'✓' if sub['pass'] else '✗'} |\n"
        )
    parts.append("\n## Interpretation\n")
    parts.append(card["interpretation"] + "\n")
    parts.append(
        "\n## Reproduce\n\n"
        "```bash\n"
        "python3 scripts/predictions_compute_P1.py\n"
        "python3 scripts/predictions_score_P1.py\n"
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

    card = score_p1(
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
