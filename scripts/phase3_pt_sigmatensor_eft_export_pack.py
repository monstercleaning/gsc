#!/usr/bin/env python3
"""Deterministic SigmaTensor-v1 EFT diagnostic export pack (background-only)."""

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
from gsc.pt import sigmatensor_v1_eft_alphas  # noqa: E402
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1History,
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


TOOL_NAME = "phase3_pt_sigmatensor_eft_export_pack"
SCHEMA_NAME = "phase3_sigmatensor_eft_export_pack_v1"
FAIL_MARKER = "PHASE3_SIGMATENSOR_EFT_EXPORT_FAILED"


class UsageError(Exception):
    """Usage / IO error (exit 1)."""


class GateError(Exception):
    """Physical precondition failure (exit 2)."""


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise UsageError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise UsageError(f"{name} must be a finite float")
    return float(out)


def _fmt(value: float) -> str:
    return f"{float(value):.12e}"


def _as_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _stable_digest(
    *,
    z: Sequence[float],
    E: Sequence[float],
    wphi: Sequence[float],
    omphi: Sequence[float],
    alpha_k: Sequence[float],
    alpha_m: Sequence[float],
    alpha_b: Sequence[float],
    alpha_t: Sequence[float],
    cs2: Sequence[float],
) -> str:
    lines: List[str] = []
    for i in range(len(z)):
        lines.append(
            f"{z[i]:.12e},{E[i]:.12e},{wphi[i]:.12e},{omphi[i]:.12e},"
            f"{alpha_k[i]:.12e},{alpha_m[i]:.12e},{alpha_b[i]:.12e},{alpha_t[i]:.12e},{cs2[i]:.12e}\n"
        )
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _min_max(values: Sequence[float]) -> Tuple[float, float]:
    return float(min(values)), float(max(values))


def _render_readme(args: argparse.Namespace) -> str:
    cmd = (
        "python3 v11.0.0/scripts/phase3_pt_sigmatensor_eft_export_pack.py "
        f"--H0-km-s-Mpc {float(args.H0_km_s_Mpc):.12g} "
        f"--Omega-m {float(args.Omega_m):.12g} "
        f"--w0 {float(args.w0):.12g} "
        f"--lambda {float(args.lambda_):.12g} "
        f"--z-max {float(args.z_max):.12g} "
        f"--n-steps {int(args.n_steps)} "
        "--outdir <outdir> --format text"
    )
    if args.Omega_r0_override is not None:
        cmd += f" --Omega-r0-override {float(args.Omega_r0_override):.12g}"
    if int(args.sign_u0) == -1:
        cmd += " --sign-u0 -1"
    return "\n".join(
        [
            "# SigmaTensor-v1 EFT diagnostic export",
            "",
            "This pack is a deterministic background-only EFT diagnostic export",
            "for canonical quintessence in GR.",
            "",
            "Scope boundary:",
            "- background-only scaffold",
            "- no perturbation/Boltzmann closure here",
            "- intended as an export bridge for future integration steps",
            "",
            "## Files",
            "- `EFT_EXPORT_SUMMARY.json`",
            "- `EFT_ALPHAS.csv`",
            "- `README.md`",
            "",
            "## Reproduce",
            "```bash",
            cmd,
            "```",
            "",
        ]
    )


def _render_text_rows(hist: SigmaTensorV1History, z_max: float) -> str:
    probes = [0.0, 0.5, 1.0, 2.0, 10.0, float(z_max)]
    rows: List[float] = []
    for z in probes:
        if z > float(z_max) + 1.0e-12:
            continue
        if not rows or abs(rows[-1] - z) > 1.0e-15:
            rows.append(float(z))
    if not rows:
        rows = [0.0]
    lines: List[str] = []
    lines.append("SigmaTensor-v1 EFT diagnostic summary")
    lines.append("z,H_over_H0,w_phi,Omega_phi,alpha_K")
    for z in rows:
        u = hist.u(z)
        lines.append(
            f"{z:.6g},{hist.E(z):.12g},{hist.w_phi(z):.12g},{hist.Omega_phi(z):.12g},{(u*u):.12g}"
        )
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Phase-3 SigmaTensor-v1 EFT diagnostic export pack.")
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, required=True)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, required=True)
    ap.add_argument("--w0", type=float, required=True)
    ap.add_argument("--lambda", dest="lambda_", type=float, required=True)
    ap.add_argument("--z-max", dest="z_max", type=float, default=30.0)
    ap.add_argument("--n-steps", dest="n_steps", type=int, default=2048)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)
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
        if z_max <= 0.0:
            raise UsageError("--z-max must be > 0")
        if int(args.n_steps) < 2:
            raise UsageError("--n-steps must be >= 2")

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
            bg = solve_sigmatensor_v1_background(
                params,
                z_max=float(z_max),
                n_steps=int(args.n_steps),
            )
        except ValueError as exc:
            raise GateError(str(exc)) from exc

        hist = SigmaTensorV1History(bg)
        alphas = sigmatensor_v1_eft_alphas(bg)
        alpha_k = [float(x) for x in alphas["alpha_K"]]
        alpha_m = [float(x) for x in alphas["alpha_M"]]
        alpha_b = [float(x) for x in alphas["alpha_B"]]
        alpha_t = [float(x) for x in alphas["alpha_T"]]
        cs2 = [float(x) for x in alphas["c_s2"]]

        E_grid = [float(h) / float(params.H0_si) for h in bg.H_grid_si]

        E_min, E_max = _min_max(E_grid)
        w_min, w_max = _min_max(bg.wphi_grid)
        om_min, om_max = _min_max(bg.Omphi_grid)
        ak_min, ak_max = _min_max(alpha_k)

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
                "alpha_K_min": float(ak_min),
                "alpha_K_max": float(ak_max),
            },
            "alpha_defs": {
                "alpha_K": "u^2",
                "alpha_M": "0",
                "alpha_B": "0",
                "alpha_T": "0",
                "c_s2": "1",
            },
            "digests": {
                "z_E_wphi_Omphi_alphaK_alphaM_alphaB_alphaT_cs2_sha256": _stable_digest(
                    z=bg.z_grid,
                    E=E_grid,
                    wphi=bg.wphi_grid,
                    omphi=bg.Omphi_grid,
                    alpha_k=alpha_k,
                    alpha_m=alpha_m,
                    alpha_b=alpha_b,
                    alpha_t=alpha_t,
                    cs2=cs2,
                )
            },
        }

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        summary_text = _as_json(payload)
        (outdir / "EFT_EXPORT_SUMMARY.json").write_text(summary_text, encoding="utf-8")
        (outdir / "README.md").write_text(_render_readme(args), encoding="utf-8")

        with (outdir / "EFT_ALPHAS.csv").open("w", encoding="utf-8", newline="") as fh:
            fh.write("z,H_over_H0,w_phi,Omega_phi,alpha_K,alpha_M,alpha_B,alpha_T,c_s2\n")
            for i in range(len(bg.z_grid)):
                fh.write(
                    ",".join(
                        [
                            _fmt(bg.z_grid[i]),
                            _fmt(E_grid[i]),
                            _fmt(bg.wphi_grid[i]),
                            _fmt(bg.Omphi_grid[i]),
                            _fmt(alpha_k[i]),
                            _fmt(alpha_m[i]),
                            _fmt(alpha_b[i]),
                            _fmt(alpha_t[i]),
                            _fmt(cs2[i]),
                        ]
                    )
                    + "\n"
                )

    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except GateError as exc:
        print(FAIL_MARKER, file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if str(args.format) == "json":
        sys.stdout.write(summary_text)
    else:
        sys.stdout.write(_render_text_rows(hist, float(z_max)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

