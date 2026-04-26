#!/usr/bin/env python3
"""
predictions_score_P5.py — score Prediction P5 against current nEDM bound.

A consistency-bound scorer: passes if |θ_eff(z=0)| is within the registered
nEDM bound and (optionally) if the predicted high-z trajectory respects the
order-of-magnitude quasar-absorption bound declared in the pipeline output.

Usage:
    python3 scripts/predictions_score_P5.py
    python3 scripts/predictions_score_P5.py --strict-quasar
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRED_DIR = REPO_ROOT / "predictions_register" / "P5_strong_cp_bound"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def score_p5(*, pipeline_path: Path, observed_path: Path, strict_quasar: bool) -> dict:
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    observed = json.loads(observed_path.read_text(encoding="utf-8"))

    nedm_consistency = pipeline["consistency_with_nedm"]
    quasar_consistency = pipeline.get("consistency_with_quasar_rough", {})

    pass_nedm = bool(nedm_consistency["consistent_with_nedm"])
    pass_quasar = bool(quasar_consistency.get("consistent_with_quasar_rough", True))

    overall_pass = pass_nedm and (pass_quasar if strict_quasar else True)

    return {
        "scorecard_schema": "predictions_p5_scorecard_v1",
        "prediction_id": "P5",
        "scoring_mode": "strict-quasar" if strict_quasar else "nedm-only",
        "pipeline_output_hash_at_scoring": sha256_of_file(pipeline_path),
        "observed_source": observed.get("source", "unknown"),
        "observed_data_release_date": observed.get("data_release_date", "unknown"),
        "nedm_check": {
            "registered_abs_theta_z0": nedm_consistency["registered_abs_theta_z0"],
            "nedm_theta_bound_abs": nedm_consistency["nedm_theta_bound_abs"],
            "fraction_of_current_bound": nedm_consistency[
                "fraction_of_current_bound"
            ],
            "pass": pass_nedm,
        },
        "quasar_check": {
            "predicted_abs_delta_theta_at_z2": quasar_consistency.get(
                "predicted_abs_delta_theta_at_z2"
            ),
            "rough_quasar_bound_abs_delta_theta": quasar_consistency.get(
                "rough_quasar_bound_abs_delta_theta"
            ),
            "pass": pass_quasar,
            "note": (
                "Quasar bound is order-of-magnitude only. Pass/fail used as "
                "soft check unless --strict-quasar is requested."
            ),
        },
        "overall_outcome": "PASS" if overall_pass else "FAIL",
        "interpretation": (
            "PASS: σ-axion-equivalence parameters are consistent with the "
            "current nEDM bound on |θ_eff(z=0)|."
            + (
                ""
                if not strict_quasar
                else " The high-z θ-trajectory also respects the rough "
                "quasar-absorption bound at z=2."
            )
            if overall_pass
            else "FAIL: σ-axion-equivalence parameters are inconsistent with "
            "the current nEDM bound (or, in --strict-quasar mode, with the "
            "rough quasar-absorption bound at z=2). Reduce |θ_eff(z=0)| or "
            "the σ-θ coupling g_θ/f_σ."
        ),
    }


def render_scorecard(card: dict, scored_at_utc: str) -> str:
    overall = card["overall_outcome"]
    badge = "✅ PASS" if overall == "PASS" else "❌ FAIL"
    parts: list[str] = []
    parts.append(f"# Scorecard — Prediction P5 (Strong-CP θ-bound)\n")
    parts.append(f"**Outcome:** {badge}  (mode: {card['scoring_mode']})\n")
    parts.append(f"**Scored at:** `{scored_at_utc}`\n")
    parts.append(
        f"**Pipeline output hash:** `{card['pipeline_output_hash_at_scoring']}`\n"
    )
    parts.append(
        f"**Observed source:** {card['observed_source']} "
        f"(released {card['observed_data_release_date']})\n"
    )

    n = card["nedm_check"]
    parts.append("\n## nEDM bound check\n")
    parts.append(
        f"| Quantity | Value |\n|---|---|\n"
        f"| |θ_eff(z=0)| | {n['registered_abs_theta_z0']} |\n"
        f"| nEDM bound | {n['nedm_theta_bound_abs']} |\n"
        f"| Fraction of bound | {n['fraction_of_current_bound']:.1%} |\n"
        f"| Pass | {'✓' if n['pass'] else '✗'} |\n"
    )

    q = card["quasar_check"]
    if q["predicted_abs_delta_theta_at_z2"] is not None:
        parts.append("\n## Quasar bound check (rough, order-of-magnitude)\n")
        parts.append(
            f"| Quantity | Value |\n|---|---|\n"
            f"| Predicted |Δθ| at z=2 | {q['predicted_abs_delta_theta_at_z2']} |\n"
            f"| Rough bound | {q['rough_quasar_bound_abs_delta_theta']} |\n"
            f"| Pass (soft) | {'✓' if q['pass'] else '✗'} |\n"
        )

    parts.append("\n## Interpretation\n")
    parts.append(card["interpretation"] + "\n")
    parts.append(
        "\n## Reproduce\n\n"
        "```bash\n"
        "python3 scripts/predictions_compute_P5.py\n"
        "python3 scripts/predictions_score_P5.py\n"
        "```\n"
    )
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pipeline", type=Path, default=PRED_DIR / "pipeline_output.json")
    parser.add_argument("--observed", type=Path, default=PRED_DIR / "observed_data.json")
    parser.add_argument(
        "--strict-quasar",
        action="store_true",
        help="require quasar bound to pass; default is soft check",
    )
    parser.add_argument("--output", type=Path, default=PRED_DIR / "scorecard.md")
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    if not args.pipeline.is_file():
        sys.stderr.write(f"error: pipeline output missing: {args.pipeline}\n")
        return 2
    if not args.observed.is_file():
        sys.stderr.write(f"error: observed data missing: {args.observed}\n")
        return 2

    card = score_p5(
        pipeline_path=args.pipeline,
        observed_path=args.observed,
        strict_quasar=args.strict_quasar,
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
