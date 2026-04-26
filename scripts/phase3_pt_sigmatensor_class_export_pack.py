#!/usr/bin/env python3
"""Deterministic Phase-3 SigmaTensor-v1 -> CLASS export pack bridge.

Scope:
- background-derived export scaffold only
- no perturbation solver in this tool
- no data-fit claims
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence

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


TOOL_NAME = "phase3_pt_sigmatensor_class_export_pack"
SUMMARY_SCHEMA = "phase3_sigmatensor_class_export_pack_v1"
CANDIDATE_SCHEMA = "phase3_sigmatensor_candidate_record_v1"
FAIL_MARKER = "PHASE3_SIGMATENSOR_CLASS_EXPORT_FAILED"
OMEGA_CDM_MARKER = "NONPOSITIVE_OMEGA_CDM_H2_DERIVED"

_CSV_FMT = "{:.12e}"
_TINY = 1.0e-12


class UsageError(Exception):
    """Usage/IO/configuration error (exit 1)."""


class GateError(Exception):
    """Deterministic physical-precondition gate failure (exit 2)."""


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise UsageError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise UsageError(f"{name} must be a finite float")
    return float(out)


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fmt(v: float) -> str:
    return _CSV_FMT.format(float(v))


def _canonical_params_hash(payload: Mapping[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _sha256_text(text)


def _fit_wa(*, z_grid: Sequence[float], w_grid: Sequence[float], w0: float, zmax_fit: float) -> float:
    rows: List[tuple[float, float]] = []
    z_limit = max(0.0, float(zmax_fit))
    for z, w in zip(z_grid, w_grid):
        zz = float(z)
        if zz < 0.0:
            continue
        if zz > z_limit + 1.0e-12:
            continue
        rows.append((zz, float(w)))
    if not rows:
        return 0.0

    num = 0.0
    den = 0.0
    for zz, ww in rows:
        a = 1.0 / (1.0 + zz)
        x = 1.0 - a
        y = ww - float(w0)
        num += x * y
        den += x * x
    if den <= 0.0:
        return 0.0
    wa = num / den
    if not math.isfinite(wa):
        return 0.0
    return float(wa)


def _write_class_ini(
    *,
    path: Path,
    h: float,
    Tcmb_K: float,
    N_eff: float,
    omega_b_h2: float,
    omega_cdm_h2: float,
    As: float,
    ns: float,
    tau_reio: float,
    Omega_phi0: float,
    w0: float,
    wa: float,
    class_output: str,
    l_max_scalars: int,
    YHe: Optional[float],
) -> None:
    lines: List[str] = []
    lines.append("# BOLTZMANN_INPUT_TEMPLATE_CLASS.ini")
    lines.append(f"# generated_by={TOOL_NAME}")
    lines.append("# claim-safe scope: Phase-3 background-derived DE-fluid approximation")
    lines.append("# for external CLASS runs; no in-repo perturbation closure")
    lines.append("")
    lines.append(f"h = {_fmt(h)}")
    lines.append(f"T_cmb = {_fmt(Tcmb_K)}")
    lines.append(f"N_eff = {_fmt(N_eff)}")
    lines.append(f"omega_b = {_fmt(omega_b_h2)}")
    lines.append(f"omega_cdm = {_fmt(omega_cdm_h2)}")
    lines.append(f"A_s = {_fmt(As)}")
    lines.append(f"n_s = {_fmt(ns)}")
    lines.append(f"tau_reio = {_fmt(tau_reio)}")
    if YHe is not None:
        lines.append(f"YHe = {_fmt(YHe)}")
    lines.append("Omega_k = 0")
    lines.append(f"output = {class_output}")
    lines.append(f"l_max_scalars = {int(l_max_scalars)}")
    lines.append(f"Omega_fld = {_fmt(Omega_phi0)}")
    lines.append(f"w0_fld = {_fmt(w0)}")
    lines.append(f"wa_fld = {_fmt(wa)}")
    lines.append("cs2_fld = 1")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(path: Path) -> None:
    lines = [
        "# SigmaTensor-v1 CLASS export pack",
        "",
        "This export pack provides a deterministic Phase-3 background-derived",
        "bridge to external CLASS execution.",
        "",
        "Scope boundary:",
        "- background-derived DE-fluid approximation",
        "- no perturbation derivation in this repo",
        "- no full Planck likelihood claim in this step",
        "",
        "## Run CLASS via existing harness",
        "```bash",
        "python3 v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py \\",
        "  --export-pack <outdir> \\",
        "  --code class \\",
        "  --runner docker \\",
        "  --run-dir <run_dir> \\",
        "  --overwrite \\",
        "  --created-utc 2000-01-01T00:00:00Z \\",
        "  --require-pinned-image",
        "```",
        "",
        "Recommended image pinning example:",
        "- `GSC_CLASS_DOCKER_IMAGE=gsc/class_public:v3.2.0`",
        "",
        "## Package run outputs",
        "```bash",
        "python3 v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py \\",
        "  --export-pack <outdir> \\",
        "  --run-dir <run_dir> \\",
        "  --outdir <results_outdir> \\",
        "  --overwrite \\",
        "  --format text",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_grid(
    *,
    path: Path,
    z: Sequence[float],
    E: Sequence[float],
    wphi: Sequence[float],
    omphi: Sequence[float],
    alpha_k: Sequence[float],
    wa_used: float,
) -> str:
    rows: List[str] = ["z,H_over_H0,w_phi,Omega_phi,alpha_K,wa_fit_used\n"]
    for i in range(len(z)):
        rows.append(
            ",".join(
                [
                    _fmt(z[i]),
                    _fmt(E[i]),
                    _fmt(wphi[i]),
                    _fmt(omphi[i]),
                    _fmt(alpha_k[i]),
                    _fmt(wa_used),
                ]
            )
            + "\n"
        )
    text = "".join(rows)
    path.write_text(text, encoding="utf-8")
    return _sha256_text("".join(rows[1:]))


def _text_probe_rows(hist: SigmaTensorV1History, z_max: float, alpha_k_at_z: Mapping[float, float]) -> str:
    probes = [0.0, 0.5, 1.0, 2.0, 10.0, float(z_max)]
    rows: List[float] = []
    for z in probes:
        if z > float(z_max) + 1.0e-12:
            continue
        if not rows or abs(rows[-1] - z) > 1.0e-15:
            rows.append(float(z))
    lines = ["SigmaTensor-v1 CLASS export summary", "z,H_over_H0,w_phi,Omega_phi,alpha_K"]
    for z in rows:
        alpha = float(alpha_k_at_z.get(float(z), hist.u(z) ** 2))
        lines.append(f"{z:.6g},{hist.E(z):.12g},{hist.w_phi(z):.12g},{hist.Omega_phi(z):.12g},{alpha:.12g}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Phase-3 SigmaTensor-v1 deterministic CLASS export pack.")
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, required=True)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, required=True)
    ap.add_argument("--w0", type=float, required=True)
    ap.add_argument("--lambda", dest="lambda_", type=float, required=True)
    ap.add_argument("--z-max", dest="z_max", type=float, default=5.0)
    ap.add_argument("--n-steps", dest="n_steps", type=int, default=512)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)

    ap.add_argument("--n-s", dest="n_s", type=float, default=0.965)
    ap.add_argument("--A-s", dest="A_s", type=float, default=2.1e-9)
    ap.add_argument("--tau-reio", dest="tau_reio", type=float, default=0.054)
    ap.add_argument("--YHe", dest="YHe", type=float, default=None)
    ap.add_argument("--omega-b-h2", dest="omega_b_h2", type=float, default=0.02237)
    ap.add_argument("--omega-cdm-h2", dest="omega_cdm_h2", type=float, default=None)

    ap.add_argument("--de-model", dest="de_model", choices=("fld_w0wa",), default="fld_w0wa")
    ap.add_argument("--wa-mode", dest="wa_mode", choices=("zero", "fit"), default="fit")
    ap.add_argument("--wa-fit-zmax", dest="wa_fit_zmax", type=float, default=5.0)

    ap.add_argument("--class-output", dest="class_output", default="tCl")
    ap.add_argument("--l-max-scalars", dest="l_max_scalars", type=int, default=2500)

    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        H0_km = _finite_float(args.H0_km_s_Mpc, name="--H0-km-s-Mpc")
        H0_si = float(H0_to_SI(H0_km))
        Omega_m0 = _finite_float(args.Omega_m, name="--Omega-m")
        w0 = _finite_float(args.w0, name="--w0")
        lambda_ = _finite_float(args.lambda_, name="--lambda")
        z_max = _finite_float(args.z_max, name="--z-max")
        if z_max <= 0.0:
            raise UsageError("--z-max must be > 0")
        n_steps = int(args.n_steps)
        if n_steps < 2:
            raise UsageError("--n-steps must be >= 2")

        Tcmb_K = _finite_float(args.Tcmb_K, name="--Tcmb-K")
        N_eff = _finite_float(args.N_eff, name="--N-eff")
        omega_r0_override = None
        if args.Omega_r0_override is not None:
            omega_r0_override = _finite_float(args.Omega_r0_override, name="--Omega-r0-override")

        n_s = _finite_float(args.n_s, name="--n-s")
        A_s = _finite_float(args.A_s, name="--A-s")
        tau_reio = _finite_float(args.tau_reio, name="--tau-reio")
        YHe = None if args.YHe is None else _finite_float(args.YHe, name="--YHe")
        omega_b_h2 = _finite_float(args.omega_b_h2, name="--omega-b-h2")
        wa_fit_zmax = _finite_float(args.wa_fit_zmax, name="--wa-fit-zmax")
        if wa_fit_zmax < 0.0:
            raise UsageError("--wa-fit-zmax must be >= 0")
        if int(args.l_max_scalars) < 2:
            raise UsageError("--l-max-scalars must be >= 2")
        class_output = str(args.class_output).strip()
        if not class_output:
            raise UsageError("--class-output must be non-empty")

        st_params = SigmaTensorV1Params(
            H0_si=H0_si,
            Omega_m0=Omega_m0,
            w_phi0=w0,
            lambda_=lambda_,
            Tcmb_K=Tcmb_K,
            N_eff=N_eff,
            Omega_r0_override=omega_r0_override,
            sign_u0=int(args.sign_u0),
        )
        try:
            bg = solve_sigmatensor_v1_background(st_params, z_max=z_max, n_steps=n_steps)
        except ValueError as exc:
            raise GateError(str(exc)) from exc

        hist = SigmaTensorV1History(bg)
        alphas = sigmatensor_v1_eft_alphas(bg)
        alpha_k = [float(x) for x in alphas["alpha_K"]]
        E_grid = [float(h) / H0_si for h in bg.H_grid_si]

        h = H0_km / 100.0
        omega_m_h2 = Omega_m0 * h * h
        if args.omega_cdm_h2 is None:
            diff = omega_m_h2 - omega_b_h2
            if diff <= _TINY:
                raise GateError(
                    f"{OMEGA_CDM_MARKER}: omega_m_h2={omega_m_h2:.12e} <= omega_b_h2={omega_b_h2:.12e}"
                )
            omega_cdm_h2 = float(diff)
        else:
            omega_cdm_h2 = _finite_float(args.omega_cdm_h2, name="--omega-cdm-h2")
            if omega_cdm_h2 <= 0.0:
                raise GateError("omega_cdm_h2 must be > 0")

        if str(args.wa_mode) == "zero":
            wa = 0.0
        else:
            wa = _fit_wa(
                z_grid=bg.z_grid,
                w_grid=bg.wphi_grid,
                w0=w0,
                zmax_fit=min(float(wa_fit_zmax), float(z_max)),
            )

        outdir = Path(args.outdir).expanduser().resolve()
        if outdir.exists():
            if not outdir.is_dir():
                raise UsageError(f"--outdir exists and is not a directory: {outdir}")
            if any(outdir.iterdir()) and not bool(args.overwrite):
                raise UsageError(f"--outdir is not empty (use --overwrite): {outdir}")
        outdir.mkdir(parents=True, exist_ok=True)

        grid_sha = _write_grid(
            path=outdir / "SIGMATENSOR_DIAGNOSTIC_GRID.csv",
            z=bg.z_grid,
            E=E_grid,
            wphi=bg.wphi_grid,
            omphi=bg.Omphi_grid,
            alpha_k=alpha_k,
            wa_used=wa,
        )
        _write_readme(outdir / "README.md")
        _write_class_ini(
            path=outdir / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini",
            h=h,
            Tcmb_K=Tcmb_K,
            N_eff=N_eff,
            omega_b_h2=omega_b_h2,
            omega_cdm_h2=omega_cdm_h2,
            As=A_s,
            ns=n_s,
            tau_reio=tau_reio,
            Omega_phi0=float(bg.meta["Omega_phi0"]),
            w0=w0,
            wa=wa,
            class_output=class_output,
            l_max_scalars=int(args.l_max_scalars),
            YHe=YHe,
        )

        canonical_for_hash = {
            "H0_km_s_Mpc": H0_km,
            "H0_si": H0_si,
            "Omega_m0": Omega_m0,
            "w_phi0": w0,
            "lambda": lambda_,
            "Tcmb_K": Tcmb_K,
            "N_eff": N_eff,
            "Omega_r0_override": omega_r0_override,
            "sign_u0": int(args.sign_u0),
            "n_s": n_s,
            "A_s": A_s,
            "tau_reio": tau_reio,
            "YHe": YHe,
            "omega_b_h2": omega_b_h2,
            "omega_cdm_h2": omega_cdm_h2,
            "de_model": str(args.de_model),
            "wa_mode": str(args.wa_mode),
            "wa_fit_zmax": float(wa_fit_zmax),
            "wa_value": float(wa),
            "class_output": class_output,
            "l_max_scalars": int(args.l_max_scalars),
            "Omega_r0": float(bg.meta["Omega_r0"]),
            "Omega_phi0": float(bg.meta["Omega_phi0"]),
            "u0": float(bg.meta["u0"]),
            "Vhat0": float(bg.meta["Vhat0"]),
        }
        params_hash = _canonical_params_hash(canonical_for_hash)

        summary_payload: Dict[str, Any] = {
            "schema": SUMMARY_SCHEMA,
            "tool": TOOL_NAME,
            "params": {
                "H0_km_s_Mpc": float(H0_km),
                "H0_si": float(H0_si),
                "Omega_m0": float(Omega_m0),
                "w_phi0": float(w0),
                "lambda": float(lambda_),
                "Tcmb_K": float(Tcmb_K),
                "N_eff": float(N_eff),
                "Omega_r0_override": None if omega_r0_override is None else float(omega_r0_override),
                "sign_u0": int(args.sign_u0),
                "n_s": float(n_s),
                "A_s": float(A_s),
                "tau_reio": float(tau_reio),
                "YHe": None if YHe is None else float(YHe),
                "omega_b_h2": float(omega_b_h2),
                "omega_cdm_h2": float(omega_cdm_h2),
                "class_output": class_output,
                "l_max_scalars": int(args.l_max_scalars),
            },
            "derived_today": {
                "Omega_r0": float(bg.meta["Omega_r0"]),
                "Omega_phi0": float(bg.meta["Omega_phi0"]),
                "u0": float(bg.meta["u0"]),
                "Vhat0": float(bg.meta["Vhat0"]),
                "p_action": float(bg.meta["p_action"]),
            },
            "mapping": {
                "de_model": str(args.de_model),
                "wa_mode": str(args.wa_mode),
                "wa_fit_zmax": float(wa_fit_zmax),
                "wa_value": float(wa),
            },
            "grid_summary": {
                "z_max": float(z_max),
                "n_steps": int(n_steps),
                "n_grid": int(len(bg.z_grid)),
                "E_min": float(min(E_grid)),
                "E_max": float(max(E_grid)),
                "w_phi_min": float(min(bg.wphi_grid)),
                "w_phi_max": float(max(bg.wphi_grid)),
                "Omega_phi_min": float(min(bg.Omphi_grid)),
                "Omega_phi_max": float(max(bg.Omphi_grid)),
                "alpha_K_min": float(min(alpha_k)),
                "alpha_K_max": float(max(alpha_k)),
            },
            "digests": {
                "sha256_grid": str(grid_sha),
                "params_hash": str(params_hash),
                "class_template_sha256": _sha256_path(outdir / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini"),
            },
            "notes": [
                "Phase-3 background-derived CLASS export scaffold",
                "No perturbation/Boltzmann derivation is implemented in-repo",
            ],
        }

        candidate_payload: Dict[str, Any] = {
            "schema": CANDIDATE_SCHEMA,
            "tool": TOOL_NAME,
            "selection": {
                "rank_by": "phase3_background_bridge",
                "eligible_status": "ok_only",
                "rsd_chi2_field_used": None,
                "used_precomputed_joint": False,
                "best_metric_value": None,
                "best_metric_components": {},
            },
            "best": {
                "best_params_hash": str(params_hash),
                "best_plan_point_id": "phase3_sigmatensor_v1",
            },
            "record": {
                "status": "ok",
                "params_hash": str(params_hash),
                "params_hash_source": "phase3_sigmatensor_class_export_pack",
                "plan_point_id": "phase3_sigmatensor_v1",
                "scan_config_sha256": str(params_hash),
                "plan_source_sha256": _sha256_path(outdir / "SIGMATENSOR_DIAGNOSTIC_GRID.csv"),
                "chi2_total": None,
                "chi2_joint_total": None,
                "mapping": {
                    "de_model": str(args.de_model),
                    "wa_mode": str(args.wa_mode),
                    "wa_value": float(wa),
                },
            },
        }

        summary_text = _json_text(summary_payload)
        candidate_text = _json_text(candidate_payload)
        (outdir / "EXPORT_SUMMARY.json").write_text(summary_text, encoding="utf-8")
        (outdir / "CANDIDATE_RECORD.json").write_text(candidate_text, encoding="utf-8")

        alpha_k_at_z = {
            float(bg.z_grid[i]): float(alpha_k[i])
            for i in range(len(bg.z_grid))
        }

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
        sys.stdout.write(_text_probe_rows(hist, float(z_max), alpha_k_at_z))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

