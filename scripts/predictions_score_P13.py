#!/usr/bin/env python3
"""predictions_score_P13.py — score Prediction P13 (GW-EM duality null).

Compares the registered exact-null prediction (Xi_0 = 1) against the current
best standard-siren constraint recorded in observed_data.json.

Registered rule (prediction.md): PASS if |z| < 3 where
    z = (Xi_0_observed - 1) / sigma_toward_null.

For asymmetric credible intervals, sigma_toward_null is the error bar on the
side facing the null value — the conservative choice that maximizes |z|.

Sudden-death clause: a robust (>= 3 sigma, systematics-stable, independently
reproduced) Xi_0 != 1 falsifies T1 outright (GSC_Framework.md §12.2.1a,
tensor-sector extension). This scorer only evaluates the parametrized check;
the robustness qualifiers are assessed at framework level, not here.

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
REGISTER = REPO_ROOT / "predictions_register" / "P13_gw_em_duality"


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

    xi0_pred = float(pipeline["prediction"]["xi0"])
    xi0_obs = float(observed["xi0_observed"])
    sigma = float(observed["sigma_toward_null"])
    z = (xi0_obs - xi0_pred) / sigma
    passed = abs(z) < args.confidence
    outcome = "PASS" if passed else "FAIL"

    scored_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    badge = "✅ PASS" if passed else "❌ FAIL"
    interp = (
        "PASS (retrodictive current-bounds check): the exact GSC null Xi_0 = 1 is "
        "consistent with the GWTC-4.0 dark-siren constraint at the registered "
        "|z| < 3 rule. Shared with ΛCDM+GR — this check does not discriminate GSC "
        "from the standard model; its value is the standing sudden-death clause: "
        "any future robust (systematics-stable, independently reproduced) Xi_0 != 1 "
        "at ≥ 3σ falsifies T1 outright, and no correction may be invoked to rescue "
        "it (GSC_Framework.md §12.2.1/§12.2.1a). The constraint tightens every "
        "observing run with no involvement from this project."
        if passed
        else "FAIL: the current standard-siren constraint deviates from the exact "
        "GSC null at ≥ the registered confidence. If this deviation is "
        "systematics-stable and independently reproduced, T1 is falsified outright "
        "(GSC_Framework.md §12.2.1a, tensor-sector extension); no correction may "
        "be invoked to rescue it."
    )

    card = "\n".join([
        "# Scorecard — Prediction P13 (GW-EM duality Xi_0 = 1 null)",
        "",
        "> **RETRODICTIVE CURRENT-BOUNDS CHECK + STANDING FALSIFICATION CHANNEL.**",
        "> Scored against the already-public GWTC-4.0 dark-siren constraint. The",
        "> forward content is the sudden-death clause: any future robust Xi_0 != 1",
        "> at ≥ 3σ falsifies T1 — a single confirmed violation suffices.",
        "",
        f"**Outcome:** {badge}  (at the registered |z| < {args.confidence:g} rule)",
        f"**Scored at:** `{scored_at}`",
        f"**Pipeline output hash:** `{output_hash}`",
        f"**Observed source:** {observed['data_source']}",
        "",
        "## Prediction vs observation",
        "| Quantity | Predicted | Observed | σ (toward null) | z-score |",
        "|---|---|---|---|---|",
        f"| Ξ₀ (modified GW propagation) | {xi0_pred:g} | {xi0_obs:g} (+{observed['xi0_sigma_upper']:g}/−{observed['xi0_sigma_lower']:g}) | {sigma:g} | {z:+.3f} |",
        "",
        "## Interpretation",
        interp,
        "",
        "## Reproduce",
        "",
        "```bash",
        "python3 scripts/predictions_compute_P13.py",
        "python3 scripts/predictions_score_P13.py",
        "```",
        "",
    ])
    (reg / "scorecard.md").write_text(card, encoding="utf-8")
    print(f"P13 scorecard written; outcome: {outcome} (z = {z:+.3f}, rule |z| < {args.confidence:g})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
