#!/usr/bin/env python3
"""
predictions_score_P7.py — score Prediction P7 (GW-memory atomic-clock signature).

Scores whether the predicted permanent atomic-frequency shift (after GW-memory
events, stacked over a registered number of events) is detectable above the
current best clock array sensitivity.

A PASS verdict here means GSC's σ-GW coupling at the registered amplitude
WOULD be detectable with current technology if the coupling is real.
A FAIL verdict means the prediction is sub-threshold — i.e., the framework
cannot be confirmed nor excluded with current data.

Usage:
    python3 scripts/predictions_score_P7.py
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRED_DIR = REPO_ROOT / "predictions_register" / "P7_gw_memory_clocks"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def score_p7(*, pipeline_path: Path, observed_path: Path) -> dict:
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    observed = json.loads(observed_path.read_text(encoding="utf-8"))

    detect = pipeline["detectability_assessment"]
    best_instability = float(observed["best_clock_instability_per_tau_10000s"])
    n_events = observed["estimated_n_relevant_gw_events_2017_2024"]

    stacked = float(detect["stacked_signal_abs"])
    snr_against_best_clock = stacked / best_instability
    detectable = snr_against_best_clock > 3.0

    return {
        "scorecard_schema": "predictions_p7_scorecard_v1",
        "prediction_id": "P7",
        "pipeline_output_hash_at_scoring": sha256_of_file(pipeline_path),
        "observed_source": observed.get("source", "unknown"),
        "observed_data_release_date": observed.get("data_release_date", "unknown"),
        "detectability_check": {
            "stacked_signal_abs": stacked,
            "n_events_stacked_in_pipeline": detect["n_events_stacked"],
            "n_events_estimated_realistic": n_events,
            "best_clock_instability_per_tau_10000s": best_instability,
            "snr_against_best_clock": float(f"{snr_against_best_clock:.3e}"),
            "detectable_at_3sigma_with_current_tech": detectable,
        },
        "overall_outcome": "DETECTABLE" if detectable else "SUB-THRESHOLD",
        "interpretation": (
            "DETECTABLE: at the registered σ-GW coupling, the stacked signal "
            "exceeds the best current clock-array instability by 3σ. The "
            "framework's prediction can in principle be confirmed or refuted "
            "by analysis of existing post-event clock-comparison data."
            if detectable
            else f"SUB-THRESHOLD: stacked signal of {stacked:.2e} is below the "
            f"3× best clock-array instability ({3*best_instability:.2e}). "
            "Either (i) the σ-GW coupling k_GW must be larger than the "
            "registered value (FRG-derived from Paper B), (ii) more events "
            "must be stacked than the registered N, or (iii) clock-array "
            "instability must improve by orders of magnitude. The framework "
            "is NEITHER confirmed NOR refuted by P7 with current technology — "
            "this is itself useful information."
        ),
    }


def render_scorecard(card: dict, scored_at_utc: str) -> str:
    overall = card["overall_outcome"]
    badge = "🔬 DETECTABLE" if overall == "DETECTABLE" else "⏸ SUB-THRESHOLD"
    parts: list[str] = []
    parts.append(f"# Scorecard — Prediction P7 (GW-memory atomic-clock signature)\n")
    parts.append(f"**Outcome:** {badge}\n")
    parts.append(f"**Scored at:** `{scored_at_utc}`\n")
    parts.append(
        f"**Pipeline output hash:** `{card['pipeline_output_hash_at_scoring']}`\n"
    )
    parts.append(
        f"**Observed source:** {card['observed_source']} "
        f"(released {card['observed_data_release_date']})\n"
    )

    d = card["detectability_check"]
    parts.append("\n## Detectability check (current technology)\n")
    parts.append(
        f"| Quantity | Value |\n|---|---|\n"
        f"| Stacked predicted signal | {d['stacked_signal_abs']:.3e} |\n"
        f"| N events (pipeline) | {d['n_events_stacked_in_pipeline']} |\n"
        f"| N events (realistic estimate) | {d['n_events_estimated_realistic']} |\n"
        f"| Best clock instability (10⁴ s) | {d['best_clock_instability_per_tau_10000s']:.0e} |\n"
        f"| SNR vs best clock | {d['snr_against_best_clock']} |\n"
        f"| Detectable at 3σ | {'✓' if d['detectable_at_3sigma_with_current_tech'] else '✗'} |\n"
    )

    parts.append("\n## Interpretation\n")
    parts.append(card["interpretation"] + "\n")
    parts.append(
        "\n## Reproduce\n\n"
        "```bash\n"
        "python3 scripts/predictions_compute_P7.py\n"
        "python3 scripts/predictions_score_P7.py\n"
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

    card = score_p7(pipeline_path=args.pipeline, observed_path=args.observed)
    timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rendered = render_scorecard(card, timestamp)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(f"wrote {args.output}\n")
    sys.stdout.write(f"  outcome: {card['overall_outcome']}\n")

    if args.print:
        sys.stdout.write("\n" + rendered)
    # Return 0 for either DETECTABLE or SUB-THRESHOLD (both are valid outcomes
    # for this prediction; only data-consistency failures would error-out).
    return 0


if __name__ == "__main__":
    sys.exit(main())
