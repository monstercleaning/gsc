#!/usr/bin/env python3
"""Deterministic Phase-3 SigmaTensor-v1 consistency checkpoint report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import H0_to_SI  # noqa: E402
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1History,
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


TOOL_NAME = "phase3_st_sigmatensor_consistency_report"
SCHEMA_NAME = "phase3_sigmatensor_consistency_report_v1"
FAIL_MARKER = "PHASE3_SIGMATENSOR_CONSISTENCY_FAILED"


class ConsistencyUsageError(Exception):
    """Usage/configuration error (exit 1)."""


class ConsistencyGateError(Exception):
    """Consistency gate failure (exit 2)."""


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise ConsistencyUsageError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise ConsistencyUsageError(f"{name} must be a finite float")
    return float(out)


def _fmt_e(value: float) -> str:
    return f"{float(value):.12e}"


def _as_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _stable_digest_rows(*, z: Sequence[float], E: Sequence[float], wphi: Sequence[float], omphi: Sequence[float]) -> str:
    lines: List[str] = []
    for i in range(len(z)):
        lines.append(f"{z[i]:.12e},{E[i]:.12e},{wphi[i]:.12e},{omphi[i]:.12e}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _min_max(values: Sequence[float]) -> Tuple[float, float]:
    return float(min(values)), float(max(values))


def _nearest_index(z_grid: Sequence[float], z: float) -> int:
    target = float(z)
    best = 0
    best_dist = abs(float(z_grid[0]) - target)
    for i in range(1, len(z_grid)):
        dist = abs(float(z_grid[i]) - target)
        if dist < best_dist:
            best = i
            best_dist = dist
    return int(best)


def _render_markdown(*, args: argparse.Namespace, payload: Mapping[str, Any]) -> str:
    derived = payload.get("derived_today") if isinstance(payload.get("derived_today"), Mapping) else {}
    summary = payload.get("summary_over_grid") if isinstance(payload.get("summary_over_grid"), Mapping) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), list) else []
    sample_rows = payload.get("sample_rows") if isinstance(payload.get("sample_rows"), list) else []

    lines: List[str] = [
        "# SigmaTensor-v1 consistency report",
        "",
        "Claim-safe scope: background-only consistency diagnostics.",
        "No perturbation/Boltzmann closure is asserted in this report.",
        "",
        "## Inputs",
        f"- H0_km_s_Mpc: `{float(args.H0_km_s_Mpc):.12g}`",
        f"- Omega_m0: `{float(args.Omega_m):.12g}`",
        f"- w_phi0: `{float(args.w0):.12g}`",
        f"- lambda: `{float(args.lambda_):.12g}`",
        f"- z_max: `{float(args.z_max):.12g}`",
        f"- n_steps: `{int(args.n_steps)}`",
        "",
        "## Today-derived summary",
        f"- Omega_r0: `{float(derived.get('Omega_r0')):.12g}`",
        f"- Omega_phi0: `{float(derived.get('Omega_phi0')):.12g}`",
        f"- w_eff0: `{float(derived.get('w_eff0')):.12g}`",
        f"- q0: `{float(derived.get('q0')):.12g}`",
        f"- p_action: `{float(derived.get('p_action')):.12g}`",
        "",
        "## Grid summary",
        f"- denom_min: `{float(summary.get('denom_min')):.12g}`",
        f"- E range: `[{float(summary.get('E_min')):.12g}, {float(summary.get('E_max')):.12g}]`",
        f"- w_phi range: `[{float(summary.get('w_phi_min')):.12g}, {float(summary.get('w_phi_max')):.12g}]`",
        f"- Omega_phi(z_ref): `{float(summary.get('Omega_phi_at_zref')):.12g}` at z_ref=`{float(summary.get('z_ref')):.12g}`",
        "",
        "## Sample points",
        "",
        "| z | H/H0 | w_phi | Omega_phi |",
        "|---:|---:|---:|---:|",
    ]
    for row in sample_rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| "
            + f"{float(row.get('z')):.6g} | {float(row.get('H_over_H0')):.12g} | {float(row.get('w_phi')):.12g} | {float(row.get('Omega_phi')):.12g} |"
        )
    lines.extend(
        [
            "",
        "## Gate status",
        ]
    )
    for row in gates:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- {row.get('name')}: enabled={bool(row.get('enabled'))} passed={bool(row.get('passed'))} detail=`{row.get('detail')}`"
        )

    lines.extend(
        [
            "",
            "## Reproduce",
            "```bash",
            "python3 v11.0.0/scripts/phase3_st_sigmatensor_consistency_report.py "
            + f"--H0-km-s-Mpc {float(args.H0_km_s_Mpc):.12g} "
            + f"--Omega-m {float(args.Omega_m):.12g} "
            + f"--w0 {float(args.w0):.12g} "
            + f"--lambda {float(args.lambda_):.12g} "
            + f"--z-max {float(args.z_max):.12g} "
            + f"--n-steps {int(args.n_steps)} "
            + "--outdir <outdir> --format text",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def _render_text(*, hist: SigmaTensorV1History, payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary_over_grid") if isinstance(payload.get("summary_over_grid"), Mapping) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), list) else []

    probes = [0.0, 0.5, 1.0, 2.0, 10.0, 1100.0]
    z_max = float(summary.get("z_max", 0.0))
    rows = [z for z in probes if z <= z_max + 1.0e-12]
    if 0.0 not in rows:
        rows = [0.0] + rows

    lines: List[str] = []
    lines.append("SigmaTensor-v1 consistency summary")
    lines.append("z,H_over_H0,w_phi,Omega_phi")
    for z in rows:
        lines.append(f"{z:.6g},{hist.E(z):.12g},{hist.w_phi(z):.12g},{hist.Omega_phi(z):.12g}")
    lines.append("")
    lines.append("gates:")
    for row in gates:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- {row.get('name')}: enabled={bool(row.get('enabled'))} passed={bool(row.get('passed'))} detail={row.get('detail')}"
        )
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Phase-3 SigmaTensor-v1 deterministic consistency checkpoint.")
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, required=True)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, required=True)
    ap.add_argument("--w0", type=float, required=True)
    ap.add_argument("--lambda", dest="lambda_", type=float, required=True)
    ap.add_argument("--z-max", dest="z_max", type=float, default=1100.0)
    ap.add_argument("--n-steps", dest="n_steps", type=int, default=4096)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--format", choices=("text", "json"), default="text")

    ap.add_argument("--require-accelerating-today", action="store_true")
    ap.add_argument("--early-omega-phi-zref", dest="early_omega_phi_zref", type=float, default=1100.0)
    ap.add_argument("--require-early-omega-phi-lt", dest="require_early_omega_phi_lt", type=float, default=None)
    ap.add_argument("--require-denom-min-gt", dest="require_denom_min_gt", type=float, default=None)
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        H0_km = _finite_float(args.H0_km_s_Mpc, name="--H0-km-s-Mpc")
        H0_si = float(H0_to_SI(H0_km))
        omega_m0 = _finite_float(args.Omega_m, name="--Omega-m")
        w0 = _finite_float(args.w0, name="--w0")
        lambda_ = _finite_float(args.lambda_, name="--lambda")
        z_max = _finite_float(args.z_max, name="--z-max")
        if z_max <= 0.0:
            raise ConsistencyUsageError("--z-max must be > 0")
        if int(args.n_steps) < 2:
            raise ConsistencyUsageError("--n-steps must be >= 2")

        early_zref = _finite_float(args.early_omega_phi_zref, name="--early-omega-phi-zref")
        if early_zref < 0.0:
            raise ConsistencyUsageError("--early-omega-phi-zref must be >= 0")

        require_early_omega_phi_lt: Optional[float] = None
        if args.require_early_omega_phi_lt is not None:
            require_early_omega_phi_lt = _finite_float(
                args.require_early_omega_phi_lt,
                name="--require-early-omega-phi-lt",
            )

        require_denom_min_gt: Optional[float] = None
        if args.require_denom_min_gt is not None:
            require_denom_min_gt = _finite_float(args.require_denom_min_gt, name="--require-denom-min-gt")

        omega_r_override = None
        if args.Omega_r0_override is not None:
            omega_r_override = _finite_float(args.Omega_r0_override, name="--Omega-r0-override")

        params = SigmaTensorV1Params(
            H0_si=H0_si,
            Omega_m0=omega_m0,
            w_phi0=w0,
            lambda_=lambda_,
            Tcmb_K=_finite_float(args.Tcmb_K, name="--Tcmb-K"),
            N_eff=_finite_float(args.N_eff, name="--N-eff"),
            Omega_r0_override=omega_r_override,
            sign_u0=int(args.sign_u0),
        )

        try:
            bg = solve_sigmatensor_v1_background(params, z_max=float(z_max), n_steps=int(args.n_steps))
        except ValueError as exc:
            raise ConsistencyGateError(str(exc)) from exc

        hist = SigmaTensorV1History(bg)

        E_grid = [float(h) / float(params.H0_si) for h in bg.H_grid_si]
        denom_grid = [1.0 - (float(u) * float(u)) / 6.0 for u in bg.u_grid]

        z_ref_idx = _nearest_index(bg.z_grid, early_zref)
        z_ref_used = float(bg.z_grid[z_ref_idx])
        Omega_phi_at_zref = float(bg.Omphi_grid[z_ref_idx])

        denom_min, denom_max = _min_max(denom_grid)
        E_min, E_max = _min_max(E_grid)
        wphi_min, wphi_max = _min_max(bg.wphi_grid)
        om_min, om_max = _min_max(bg.Omphi_grid)

        Omega_r0 = float(bg.meta["Omega_r0"])
        Omega_phi0 = float(bg.meta["Omega_phi0"])
        u0 = float(bg.meta["u0"])
        Vhat0 = float(bg.meta["Vhat0"])
        p_action = float(bg.meta["p_action"])

        # At z=0, E0=1 by construction.
        w_eff0 = (Omega_r0 / 3.0) + (u0 * u0) / 6.0 - Vhat0
        q0 = 0.5 * (1.0 + 3.0 * w_eff0)

        gates: List[Dict[str, Any]] = []

        gate_acc_enabled = bool(args.require_accelerating_today)
        gate_acc_passed = (q0 < 0.0) if gate_acc_enabled else True
        gates.append(
            {
                "name": "require_accelerating_today",
                "enabled": gate_acc_enabled,
                "passed": bool(gate_acc_passed),
                "detail": f"q0={q0:.12e}",
            }
        )

        gate_early_enabled = require_early_omega_phi_lt is not None
        gate_early_passed = (Omega_phi_at_zref < float(require_early_omega_phi_lt)) if gate_early_enabled else True
        gates.append(
            {
                "name": "require_early_omega_phi_lt",
                "enabled": gate_early_enabled,
                "passed": bool(gate_early_passed),
                "detail": f"Omega_phi(z_ref={z_ref_used:.12e})={Omega_phi_at_zref:.12e}",
            }
        )

        gate_denom_enabled = require_denom_min_gt is not None
        gate_denom_passed = (denom_min > float(require_denom_min_gt)) if gate_denom_enabled else True
        gates.append(
            {
                "name": "require_denom_min_gt",
                "enabled": gate_denom_enabled,
                "passed": bool(gate_denom_passed),
                "detail": f"denom_min={denom_min:.12e}",
            }
        )

        probe_rows: List[Dict[str, float]] = []
        for z in (0.0, 0.5, 1.0, 2.0, 10.0, 1100.0):
            if z > float(z_max) + 1.0e-12:
                continue
            probe_rows.append(
                {
                    "z": float(z),
                    "H_over_H0": float(hist.E(z)),
                    "w_phi": float(hist.w_phi(z)),
                    "Omega_phi": float(hist.Omega_phi(z)),
                }
            )
        if not probe_rows:
            probe_rows.append(
                {
                    "z": 0.0,
                    "H_over_H0": float(hist.E(0.0)),
                    "w_phi": float(hist.w_phi(0.0)),
                    "Omega_phi": float(hist.Omega_phi(0.0)),
                }
            )

        payload: Dict[str, Any] = {
            "schema": SCHEMA_NAME,
            "tool": TOOL_NAME,
            "params": {
                "H0_km_s_Mpc": float(H0_km),
                "H0_si": float(H0_si),
                "Omega_m0": float(params.Omega_m0),
                "w_phi0": float(params.w_phi0),
                "lambda": float(params.lambda_),
                "Tcmb_K": float(params.Tcmb_K),
                "N_eff": float(params.N_eff),
                "Omega_r0_override": None if params.Omega_r0_override is None else float(params.Omega_r0_override),
                "sign_u0": int(params.sign_u0),
            },
            "derived_today": {
                "Omega_r0": float(Omega_r0),
                "Omega_phi0": float(Omega_phi0),
                "u0": float(u0),
                "Vhat0": float(Vhat0),
                "p_action": float(p_action),
                "w_phi0": float(params.w_phi0),
                "E0": 1.0,
                "w_eff0": float(w_eff0),
                "q0": float(q0),
            },
            "summary_over_grid": {
                "z_max": float(z_max),
                "n_steps": int(args.n_steps),
                "n_grid": int(len(bg.z_grid)),
                "denom_min": float(denom_min),
                "denom_max": float(denom_max),
                "E_min": float(E_min),
                "E_max": float(E_max),
                "w_phi_min": float(wphi_min),
                "w_phi_max": float(wphi_max),
                "Omega_phi_min": float(om_min),
                "Omega_phi_max": float(om_max),
                "z_ref": float(z_ref_used),
                "Omega_phi_at_zref": float(Omega_phi_at_zref),
            },
            "gates": gates,
            "sample_rows": probe_rows,
            "digests": {
                "z_E_wphi_Omphi_sha256": _stable_digest_rows(
                    z=bg.z_grid,
                    E=E_grid,
                    wphi=bg.wphi_grid,
                    omphi=bg.Omphi_grid,
                )
            },
        }

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        json_text = _as_json(payload)
        (outdir / "THEORY_CONSISTENCY_REPORT.json").write_text(json_text, encoding="utf-8")
        (outdir / "THEORY_CONSISTENCY_REPORT.md").write_text(
            _render_markdown(args=args, payload=payload),
            encoding="utf-8",
        )

        failed_enabled_gates = [g for g in gates if bool(g.get("enabled")) and not bool(g.get("passed"))]
        if failed_enabled_gates:
            details = ", ".join(str(g.get("name")) for g in failed_enabled_gates)
            raise ConsistencyGateError(f"enabled gate(s) failed: {details}")

    except ConsistencyUsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ConsistencyGateError as exc:
        print(FAIL_MARKER, file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if str(args.format) == "json":
        sys.stdout.write(json_text)
    else:
        sys.stdout.write(_render_text(hist=hist, payload=payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
