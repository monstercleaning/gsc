#!/usr/bin/env python3
"""Deterministic Phase-3 SigmaTensor-v1 background report (stdlib-only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import H0_to_SI  # noqa: E402
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1History,
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


TOOL_NAME = "phase3_st_sigmatensor_background_report"
SCHEMA_NAME = "phase3_sigmatensor_theory_spec_v1"


class ReportError(Exception):
    """Raised for usage/IO/validation errors."""


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise ReportError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise ReportError(f"{name} must be a finite float")
    return float(out)


def _fmt_e(value: float) -> str:
    return f"{float(value):.12e}"


def _as_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _stable_digest_rows(*, z: Sequence[float], E: Sequence[float], wphi: Sequence[float], omphi: Sequence[float]) -> str:
    lines: List[str] = []
    for i in range(len(z)):
        lines.append(f"{z[i]:.12e},{E[i]:.12e},{wphi[i]:.12e},{omphi[i]:.12e}\n")
    payload = "".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _grid_min_max(values: Iterable[float]) -> Tuple[float, float]:
    vals = [float(v) for v in values]
    return float(min(vals)), float(max(vals))


def _summary_markdown(*, args: argparse.Namespace, payload: Mapping[str, Any]) -> str:
    derived = payload.get("derived") if isinstance(payload.get("derived"), Mapping) else {}
    lines: List[str] = [
        "# SigmaTensor-v1 background report",
        "",
        "This artifact summarizes a deterministic Phase-3 background-only solve",
        "for SigmaTensor-v1 (canonical scalar + Einstein gravity + standard",
        "QFT matter/radiation sectors).",
        "",
        "Scope boundary:",
        "- background dynamics only",
        "- no perturbations/Boltzmann hierarchy",
        "- no full CMB TT/TE/EE likelihood claims",
        "",
        "## Parameters",
        f"- H0_km_s_Mpc: `{float(args.H0_km_s_Mpc):.12g}`",
        f"- Omega_m0: `{float(args.Omega_m):.12g}`",
        f"- w_phi0: `{float(args.w0):.12g}`",
        f"- lambda: `{float(args.lambda_):.12g}`",
        f"- z_max: `{float(args.z_max):.12g}`",
        f"- n_steps: `{int(args.n_steps)}`",
        f"- Omega_r0: `{float(derived.get('Omega_r0')):.12g}`",
        f"- p_action=lambda^2/2: `{float(derived.get('p_action')):.12g}`",
        "",
        "## Files",
        "- `THEORY_SPEC.json`",
        "- `H_GRID.csv`",
        "- `SUMMARY.md`",
        "",
        "## Reproduce",
        "```bash",
        "python3 v11.0.0/scripts/phase3_st_sigmatensor_background_report.py "
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
    if args.Omega_r0_override is not None:
        lines.insert(
            -3,
            "# Omega_r0 override used: " + f"{float(args.Omega_r0_override):.12g}",
        )
    return "\n".join(lines)


def _render_text_table(*, hist: SigmaTensorV1History, z_max: float) -> str:
    probes = [0.0, 0.5, 1.0, 2.0, 5.0]
    zs = [z for z in probes if z <= float(z_max) + 1.0e-12]
    if 0.0 not in zs:
        zs = [0.0] + zs
    lines: List[str] = []
    lines.append("SigmaTensor-v1 background summary")
    lines.append("z,H_over_H0,w_phi,Omega_phi")
    for z in zs:
        E = hist.E(z)
        w = hist.w_phi(z)
        om = hist.Omega_phi(z)
        lines.append(f"{z:.6g},{E:.12g},{w:.12g},{om:.12g}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Phase-3 SigmaTensor-v1 deterministic background report.")
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, required=True)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, required=True)
    ap.add_argument("--w0", type=float, required=True)
    ap.add_argument("--lambda", dest="lambda_", type=float, required=True)
    ap.add_argument("--z-max", dest="z_max", type=float, default=5.0)
    ap.add_argument("--n-steps", dest="n_steps", type=int, default=2048)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--format", choices=("text", "json"), default="text")
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
        if int(args.n_steps) < 2:
            raise ReportError("--n-steps must be >= 2")

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
            sign_u0=+1,
        )
        bg = solve_sigmatensor_v1_background(params, z_max=float(z_max), n_steps=int(args.n_steps))
        hist = SigmaTensorV1History(bg)

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        E_grid = [float(h) / float(params.H0_si) for h in bg.H_grid_si]
        digest = _stable_digest_rows(z=bg.z_grid, E=E_grid, wphi=bg.wphi_grid, omphi=bg.Omphi_grid)

        E_min, E_max = _grid_min_max(E_grid)
        w_min, w_max = _grid_min_max(bg.wphi_grid)
        om_min, om_max = _grid_min_max(bg.Omphi_grid)

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
            "derived": {
                "Omega_r0": float(bg.meta["Omega_r0"]),
                "Omega_phi0": float(bg.meta["Omega_phi0"]),
                "u0": float(bg.meta["u0"]),
                "Vhat0": float(bg.meta["Vhat0"]),
                "p_action": float(bg.meta["p_action"]),
            },
            "grid_summary": {
                "z_max": float(z_max),
                "n_steps": int(args.n_steps),
                "n_grid": int(len(bg.z_grid)),
                "E_min": float(E_min),
                "E_max": float(E_max),
                "w_phi_min": float(w_min),
                "w_phi_max": float(w_max),
                "Omega_phi_min": float(om_min),
                "Omega_phi_max": float(om_max),
            },
            "grid_digest_sha256": str(digest),
        }

        spec_path = outdir / "THEORY_SPEC.json"
        spec_text = _as_json(payload)
        spec_path.write_text(spec_text, encoding="utf-8")

        csv_path = outdir / "H_GRID.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            fh.write("z,H_over_H0,w_phi,Omega_phi\n")
            for i in range(len(bg.z_grid)):
                fh.write(
                    ",".join(
                        [
                            _fmt_e(bg.z_grid[i]),
                            _fmt_e(E_grid[i]),
                            _fmt_e(bg.wphi_grid[i]),
                            _fmt_e(bg.Omphi_grid[i]),
                        ]
                    )
                    + "\n"
                )

        md_path = outdir / "SUMMARY.md"
        md_path.write_text(_summary_markdown(args=args, payload=payload), encoding="utf-8")

    except ReportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if str(args.format) == "json":
        sys.stdout.write(spec_text)
    else:
        sys.stdout.write(_render_text_table(hist=hist, z_max=float(z_max)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
