#!/usr/bin/env python3
"""
predictions_score_P3.py — score Prediction P3 against observed neutron-lifetime data.

Reads:
  predictions_register/P3_neutron_lifetime/pipeline_output.json   (predictions)
  predictions_register/P3_neutron_lifetime/observed_data.json     (PDG values)

Computes the z-scores against beam, trap, and the differential beam-trap
measurement, then writes a scorecard.md with pass/fail at the registered
confidence level.

Usage:
    python3 scripts/predictions_score_P3.py
    python3 scripts/predictions_score_P3.py --observed predictions_register/P3_neutron_lifetime/observed_data.json
    python3 scripts/predictions_score_P3.py --confidence 3
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRED_DIR = REPO_ROOT / "predictions_register" / "P3_neutron_lifetime"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def score_p3(*, pipeline_path: Path, observed_path: Path, confidence_sigma: float) -> dict:
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    observed = json.loads(observed_path.read_text(encoding="utf-8"))

    pred = pipeline["prediction"]
    tau_b_pred = pred["tau_n_beam_predicted_s"]
    tau_t_pred = pred["tau_n_trap_predicted_s"]
    delta_pred = pred["delta_tau_beam_minus_trap_s"]

    tau_b_obs = observed["tau_n_beam_s"]
    tau_b_sigma = observed["tau_n_beam_sigma_s"]
    tau_t_obs = observed["tau_n_trap_s"]
    tau_t_sigma = observed["tau_n_trap_sigma_s"]

    delta_obs = tau_b_obs - tau_t_obs
    sigma_delta = (tau_b_sigma ** 2 + tau_t_sigma ** 2) ** 0.5

    z_beam = (tau_b_pred - tau_b_obs) / tau_b_sigma
    z_trap = (tau_t_pred - tau_t_obs) / tau_t_sigma
    z_diff = (delta_pred - delta_obs) / sigma_delta

    pass_beam = abs(z_beam) < confidence_sigma
    pass_trap = abs(z_trap) < confidence_sigma
    pass_diff = abs(z_diff) < confidence_sigma
    overall_pass = pass_beam and pass_trap and pass_diff

    return {
        "scorecard_schema": "predictions_p3_scorecard_v1",
        "prediction_id": "P3",
        "scoring_confidence_sigma": confidence_sigma,
        "pipeline_output_hash_at_scoring": sha256_of_file(pipeline_path),
        "observed_source": observed.get("source", "unknown"),
        "observed_data_release_date": observed.get("data_release_date", "unknown"),
        "predictions": {
            "tau_n_beam_predicted_s": tau_b_pred,
            "tau_n_trap_predicted_s": tau_t_pred,
            "delta_tau_beam_minus_trap_s": delta_pred,
        },
        "observations": {
            "tau_n_beam_s": tau_b_obs,
            "tau_n_beam_sigma_s": tau_b_sigma,
            "tau_n_trap_s": tau_t_obs,
            "tau_n_trap_sigma_s": tau_t_sigma,
            "delta_tau_beam_minus_trap_s": round(delta_obs, 4),
            "delta_tau_sigma_s": round(sigma_delta, 4),
        },
        "z_scores": {
            "tau_beam": round(z_beam, 4),
            "tau_trap": round(z_trap, 4),
            "delta": round(z_diff, 4),
        },
        "pass_components": {
            "tau_beam": pass_beam,
            "tau_trap": pass_trap,
            "delta": pass_diff,
        },
        "overall_outcome": "PASS" if overall_pass else "FAIL",
        "interpretation": (
            "PASS: GSC's σ-environmental dependence of β-decay rate is consistent "
            "with the observed beam-trap discrepancy at the registered confidence level. "
            "This is a positive but non-definitive result; reproduction by independent "
            "trap-geometry-varied experiments would strengthen it."
            if overall_pass
            else "FAIL: predicted τ_n values are inconsistent with PDG world averages "
            "at the registered confidence level. Re-examine σ-environmental coupling "
            "or look for alternative explanations of the discrepancy."
        ),
    }


def render_scorecard(card: dict, scored_at_utc: str) -> str:
    overall = card["overall_outcome"]
    badge = "✅ PASS" if overall == "PASS" else "❌ FAIL"
    parts: list[str] = []
    parts.append(f"# Scorecard — Prediction P3 (Neutron-lifetime beam-trap)\n")
    parts.append(f"**Outcome:** {badge}  (at {card['scoring_confidence_sigma']}σ confidence)\n")
    parts.append(f"**Scored at:** `{scored_at_utc}`\n")
    parts.append(
        f"**Pipeline output hash:** `{card['pipeline_output_hash_at_scoring']}`\n"
    )
    parts.append(
        f"**Observed data source:** {card['observed_source']} "
        f"(released {card['observed_data_release_date']})\n"
    )
    parts.append("\n## Predictions vs observations\n")
    parts.append("| Quantity | Predicted | Observed | σ_obs | z-score | Pass |\n")
    parts.append("|---|---|---|---|---|---|\n")
    p = card["predictions"]
    o = card["observations"]
    z = card["z_scores"]
    pc = card["pass_components"]
    parts.append(
        f"| τ_n^beam (s) | {p['tau_n_beam_predicted_s']:.4f} | {o['tau_n_beam_s']} | "
        f"{o['tau_n_beam_sigma_s']} | {z['tau_beam']:+.4f} | {'✓' if pc['tau_beam'] else '✗'} |\n"
    )
    parts.append(
        f"| τ_n^trap (s) | {p['tau_n_trap_predicted_s']:.4f} | {o['tau_n_trap_s']} | "
        f"{o['tau_n_trap_sigma_s']} | {z['tau_trap']:+.4f} | {'✓' if pc['tau_trap'] else '✗'} |\n"
    )
    parts.append(
        f"| Δ (beam-trap) (s) | {p['delta_tau_beam_minus_trap_s']:.4f} | "
        f"{o['delta_tau_beam_minus_trap_s']} | {o['delta_tau_sigma_s']} | "
        f"{z['delta']:+.4f} | {'✓' if pc['delta'] else '✗'} |\n"
    )
    parts.append("\n## Interpretation\n")
    parts.append(card["interpretation"] + "\n")
    parts.append(
        "\n## Reproduce\n\n"
        "```bash\n"
        "python3 scripts/predictions_compute_P3.py\n"
        "python3 scripts/predictions_score_P3.py\n"
        "```\n"
    )
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--pipeline",
        type=Path,
        default=PRED_DIR / "pipeline_output.json",
    )
    parser.add_argument(
        "--observed",
        type=Path,
        default=PRED_DIR / "observed_data.json",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=2.0,
        help="z-score threshold for pass (default 2σ)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PRED_DIR / "scorecard.md",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    if not args.pipeline.is_file():
        sys.stderr.write(f"error: pipeline output missing: {args.pipeline}\n")
        sys.stderr.write("  run: python3 scripts/predictions_compute_P3.py\n")
        return 2
    if not args.observed.is_file():
        sys.stderr.write(f"error: observed data missing: {args.observed}\n")
        return 2

    card = score_p3(
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
