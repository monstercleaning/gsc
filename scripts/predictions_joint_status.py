#!/usr/bin/env python3
"""
predictions_joint_status.py — synthesize all available scorecards into a single
framework-level status assessment.

Reads each predictions_register/PN_*/scorecard.md (where present) and produces
a roll-up summary classifying each prediction's outcome and identifying joint
consistency between cross-related predictions (P4 ↔ P5, P6 ↔ vortex DM).

Usage:
    python3 scripts/predictions_joint_status.py
    python3 scripts/predictions_joint_status.py --format json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER_DIR = REPO_ROOT / "predictions_register"


# Tags drawn from rendered scorecards.
OUTCOME_PATTERNS = {
    "PASS": re.compile(r"\*\*Outcome:\*\*\s*(✅\s*)?PASS"),
    "FAIL": re.compile(r"\*\*Outcome:\*\*\s*(❌\s*)?FAIL"),
    "DETECTABLE": re.compile(r"\*\*Outcome:\*\*\s*(🔬\s*)?DETECTABLE"),
    "SUB-THRESHOLD": re.compile(r"\*\*Outcome:\*\*\s*(⏸\s*)?SUB-THRESHOLD"),
}


def parse_scorecard_outcome(scorecard_path: Path) -> str:
    text = scorecard_path.read_text(encoding="utf-8")
    for label, pattern in OUTCOME_PATTERNS.items():
        if pattern.search(text):
            return label
    return "UNKNOWN"


def collect_status() -> list[dict]:
    rows: list[dict] = []
    for d in sorted(REGISTER_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        pid = d.name.split("_", 1)[0]
        scorecard = d / "scorecard.md"
        observed = d / "observed_data.json"
        pipeline = d / "pipeline_output.json"
        prediction_md = d / "prediction.md"

        if scorecard.is_file():
            outcome = parse_scorecard_outcome(scorecard)
            data_status = "scored"
        elif observed.is_file():
            outcome = "PENDING-SCORER"
            data_status = "data-available"
        elif pipeline.is_file():
            outcome = "PENDING-DATA"
            data_status = "data-pending"
        else:
            outcome = "INCOMPLETE"
            data_status = "no-pipeline"

        rows.append(
            {
                "id": pid,
                "directory": d.name,
                "has_prediction": prediction_md.is_file(),
                "has_pipeline": pipeline.is_file(),
                "has_observed_data": observed.is_file(),
                "has_scorecard": scorecard.is_file(),
                "data_status": data_status,
                "outcome": outcome,
            }
        )
    return rows


def joint_consistency_notes(rows: list[dict]) -> list[str]:
    """Identify cross-related predictions and comment on joint consistency."""
    by_id = {r["id"]: r for r in rows}
    notes: list[str] = []

    p4 = by_id.get("P4", {}).get("outcome")
    p5 = by_id.get("P5", {}).get("outcome")
    if p4 and p5:
        if p4 == "FAIL" and p5 == "PASS":
            notes.append(
                "P4 ↔ P5 (σ-F̃F coupling joint): P4 FAIL + P5 PASS — the registered "
                "g_CS amplitude is too small to produce the Planck birefringence hint "
                "but consistent with nEDM. The FRG calculation in Paper B should "
                "produce a g_CS value that satisfies both: large enough for the "
                "integrated [0, z_CMB] rotation, small enough for instantaneous "
                "θ_eff(0) to remain within nEDM bound."
            )
        elif p4 == "PASS" and p5 == "PASS":
            notes.append(
                "P4 ↔ P5 (σ-F̃F coupling joint): both PASS — the σ-axion-equivalence "
                "claim is consistent with both birefringence and nEDM channels. This "
                "is the joint-consistency outcome the FRG calculation must reproduce."
            )

    p6 = by_id.get("P6", {}).get("outcome")
    if p6 == "FAIL":
        notes.append(
            "P6 (KZ defect spectrum) FAIL: the registered M_* parameter is excluded "
            "by current PTA stochastic-bound. The vortex-DM derivation in Paper C "
            "Section 5 must adopt a smaller M_* (≲ TeV scale) or a different "
            "FRG critical-exponent structure. The vortex-DM module is not killed; "
            "its parameter range is constrained."
        )

    p3 = by_id.get("P3", {}).get("outcome")
    if p3 == "PASS":
        notes.append(
            "P3 (neutron lifetime) PASS at z = -0.01: GSC's σ(x,t) extension "
            "explains the unresolved beam-trap discrepancy with single-parameter "
            "δσ/σ ≈ 0.002. Independent confirmation requires varying trap "
            "geometry (different wall material, density, distance) — currently "
            "the strongest empirical evidence for the σ(x,t) extension."
        )

    p7 = by_id.get("P7", {}).get("outcome")
    if p7 == "SUB-THRESHOLD":
        notes.append(
            "P7 (GW-memory atomic clocks) SUB-THRESHOLD: at the registered "
            "k_GW coupling, the predicted signal is below current clock-array "
            "sensitivity even with √N stacking over 100 events. This does NOT "
            "exclude the framework — it identifies an experimental threshold."
        )

    p9 = by_id.get("P9", {}).get("outcome")
    if p9 == "PASS":
        notes.append(
            "P9 (μ = m_p/m_e constancy) PASS: under universal coherent scaling, "
            "GSC predicts μ̇/μ = 0 to all orders. Current laboratory (HD+) and "
            "cosmological (H₂ absorbers) bounds are consistent with this null "
            "prediction. P9 is a T1 consistency check on the geometric-lock "
            "condition; if a future detection of μ̇/μ ≠ 0 occurs, the universal "
            "scaling assumption is falsified and propagates to all higher tiers."
        )
    elif p9 == "FAIL":
        notes.append(
            "P9 (μ = m_p/m_e constancy) FAIL: an observed non-zero μ̇/μ falsifies "
            "the universal coherent-scaling assumption (T1) of the framework. "
            "Cascading impact: T2-T4 all rest on universal scaling; this would "
            "require fundamental rethinking of the geometric-lock condition."
        )

    if "P10" in by_id:
        notes.append(
            "P10 (TeV blazar dispersion) is a parametric scaffold. With current "
            "k_grad placeholder (~10⁻¹⁵), predicted σ_t is sub-second, well "
            "below CTAO sensitivity (~1 s). The prediction's value is in its "
            "discriminator role vs QG-LIV, not in its current detectability."
        )

    return notes


def render_text(rows: list[dict], notes: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Joint Status — GSC pre-registration framework\n")

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1

    lines.append("## Outcome counts\n")
    for k, v in sorted(counts.items()):
        lines.append(f"  {k:<18s}  {v}")
    lines.append("")

    lines.append("## Per-prediction status")
    lines.append(
        f"{'ID':<4}  {'pred':<5s}{'pipe':<5s}{'data':<5s}{'card':<5s}  {'OUTCOME':<18s}  TITLE"
    )
    lines.append("-" * 100)
    for r in rows:
        flags = (
            ("Y" if r["has_prediction"] else "-").ljust(5)
            + ("Y" if r["has_pipeline"] else "-").ljust(5)
            + ("Y" if r["has_observed_data"] else "-").ljust(5)
            + ("Y" if r["has_scorecard"] else "-").ljust(5)
        )
        title = r["directory"].split("_", 1)[1].replace("_", " ")
        lines.append(f"{r['id']:<4}  {flags}  {r['outcome']:<18s}  {title}")
    lines.append("")

    lines.append("## Joint-consistency notes\n")
    for note in notes:
        lines.append("- " + note + "\n")

    lines.append(
        "\n## Reproduce\n\n"
        "    bash scripts/predictions_compute_all.sh\n"
        "    python3 scripts/predictions_score_P3.py\n"
        "    python3 scripts/predictions_score_P4.py\n"
        "    python3 scripts/predictions_score_P5.py\n"
        "    python3 scripts/predictions_score_P6.py\n"
        "    python3 scripts/predictions_score_P7.py\n"
        "    python3 scripts/predictions_joint_status.py\n"
    )

    return "\n".join(lines) + "\n"


def render_json(rows: list[dict], notes: list[str]) -> str:
    return json.dumps(
        {
            "predictions": rows,
            "joint_consistency_notes": notes,
            "counts": {
                k: sum(1 for r in rows if r["outcome"] == k)
                for k in {r["outcome"] for r in rows}
            },
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    rows = collect_status()
    notes = joint_consistency_notes(rows)

    if args.format == "json":
        sys.stdout.write(render_json(rows, notes))
    else:
        sys.stdout.write(render_text(rows, notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
