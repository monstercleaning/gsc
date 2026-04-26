#!/usr/bin/env python3
"""Deterministic Phase-4 M163 Five-Problems diagnostic report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time import compute_lcdm_distance_priors, omega_r_h2  # noqa: E402
from gsc.numerics_adaptive_quad import adaptive_simpson, adaptive_simpson_log1p_z  # noqa: E402


TOOL = "phase4_m163_five_problems_report"
TOOL_VERSION = "m163-v1"
SCHEMA = "phase4_m163_five_problems_report_v1"
FAIL_MARKER = "PHASE4_M163_FIVE_PROBLEMS_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z

CMB_PRIORS_CSV = Path("v11.0.0/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv")
CMB_PRIORS_COV = Path("v11.0.0/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov")

C_KM_S = 2.99792458e5


class UsageError(Exception):
    """Invalid CLI usage."""


class DiagnosticError(Exception):
    """Non-usage runtime failure."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _fmt_e(value: float) -> str:
    return f"{float(value):.12e}"


def _to_iso_utc(epoch_seconds: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    except Exception as exc:
        raise UsageError("--created-utc must be a valid integer epoch-seconds value") from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot_fingerprint() -> Dict[str, Any]:
    return {
        "snapshot_fingerprint": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        }
    }


def _build_sigma_model(*, sigma_star_ratio: float, omega0: float):
    sigma0 = 1.0
    sigma_star = float(sigma_star_ratio) * sigma0

    if not (0.0 < sigma_star < sigma0):
        raise UsageError("--sigma-star-ratio must be in (0,1)")
    if not (math.isfinite(float(omega0)) and float(omega0) > 0.0):
        raise UsageError("--omega0 must be finite and > 0")

    def F_sigma(sigma: float) -> float:
        s = float(sigma)
        return 1.0 - (sigma_star / s) ** 2

    def dlnF_dsigma(sigma: float) -> float:
        s = float(sigma)
        return 2.0 * sigma_star * sigma_star / (s * (s * s - sigma_star * sigma_star))

    def dphi_dsigma(sigma: float) -> float:
        f = F_sigma(float(sigma))
        if not (math.isfinite(f) and f > 0.0):
            raise DiagnosticError("F(sigma) became non-positive while canonicalizing scalar field")
        dln = dlnF_dsigma(float(sigma))
        sq = 1.5 * dln * dln + float(omega0) / f
        if not (math.isfinite(sq) and sq > 0.0):
            raise DiagnosticError("(dphi/dsigma)^2 became non-positive")
        return math.sqrt(sq)

    return sigma0, sigma_star, F_sigma, dphi_dsigma


def _integrate_phi_from_sigma0(*, sigma0: float, sigma_target: float, dphi_dsigma) -> float:
    a = float(sigma0)
    b = float(sigma_target)
    if a == b:
        return 0.0

    lo = min(a, b)
    hi = max(a, b)
    value = adaptive_simpson(dphi_dsigma, lo, hi, eps_abs=1e-12, eps_rel=1e-12, max_depth=24)
    return float(value)


def _kinetic_barrier_check(*, sigma_star_ratio: float, omega0: float) -> Dict[str, Any]:
    sigma0, sigma_star, F_sigma, dphi_dsigma = _build_sigma_model(sigma_star_ratio=sigma_star_ratio, omega0=omega0)

    sigma_far = 1.5
    sigma_near = sigma_star * (1.0 + 1.0e-6)

    if not (sigma_near > sigma_star and sigma_near < sigma0):
        raise DiagnosticError("constructed sigma_near is invalid")

    phi_near = _integrate_phi_from_sigma0(sigma0=sigma0, sigma_target=sigma_near, dphi_dsigma=dphi_dsigma)
    phi_far = _integrate_phi_from_sigma0(sigma0=sigma0, sigma_target=sigma_far, dphi_dsigma=dphi_dsigma)

    # With sigma_near=sigma_star*(1+1e-6), divergence is only partially resolved;
    # use monotonic growth as the barrier indicator in this deterministic check.
    ratio = float(phi_near / phi_far) if phi_far > 0.0 else float("inf")

    return {
        "sigma0": float(sigma0),
        "sigma_star": float(sigma_star),
        "sigma_far": float(sigma_far),
        "sigma_near": float(sigma_near),
        "F_sigma0": float(F_sigma(sigma0)),
        "F_sigma_far": float(F_sigma(sigma_far)),
        "F_sigma_near": float(F_sigma(sigma_near)),
        "phi_far": float(phi_far),
        "phi_near": float(phi_near),
        "phi_near_over_phi_far": float(ratio),
        "barrier_present": bool(phi_near > phi_far),
        "note": "Toy canonicalization check for F(sigma)=1-(sigma*/sigma)^2; not a full cosmological solution.",
    }


def _scale_separation_check(*, lambda_qcd_gev: float) -> Dict[str, Any]:
    if not (math.isfinite(float(lambda_qcd_gev)) and float(lambda_qcd_gev) > 0.0):
        raise UsageError("--lambda-qcd-gev must be finite and > 0")

    hbar_c_gev_fm = 0.1973269804
    fm_to_cm = 1.0e-13
    mpc_to_cm = 3.085677581e24

    sigma_star_fm = hbar_c_gev_fm / float(lambda_qcd_gev)
    sigma_star_mpc = sigma_star_fm * fm_to_cm / mpc_to_cm
    k_star_mpc_inv = 1.0 / sigma_star_mpc

    scales = [
        ("k_H0", 1.0e-3),
        ("k_CMB", 2.0e-2),
        ("k_BAO", 6.0e-2),
        ("k_gal", 1.0),
    ]

    rows = []
    for label, k_val in scales:
        ratio = float(k_val) / float(k_star_mpc_inv)
        rows.append(
            {
                "label": str(label),
                "k_Mpc_inv": float(k_val),
                "k_over_k_star": float(ratio),
                "log10_k_over_k_star_sq": float(math.log10(ratio * ratio)),
            }
        )

    return {
        "lambda_qcd_gev": float(lambda_qcd_gev),
        "hbar_c_gev_fm": float(hbar_c_gev_fm),
        "sigma_star_fm": float(sigma_star_fm),
        "sigma_star_mpc": float(sigma_star_mpc),
        "k_star_mpc_inv": float(k_star_mpc_inv),
        "scales": rows,
    }


def _dm_mpc_to_z(*, z: float, H_func_km_s_mpc) -> float:
    if not (math.isfinite(float(z)) and float(z) >= 0.0):
        raise DiagnosticError("z for comoving distance must be finite and >= 0")

    def inv_h(zz: float) -> float:
        hz = float(H_func_km_s_mpc(float(zz)))
        if not (math.isfinite(hz) and hz > 0.0):
            raise DiagnosticError("H(z) must be finite and >0 in distance integral")
        return 1.0 / hz

    val = adaptive_simpson_log1p_z(inv_h, 0.0, float(z), eps_abs=1e-10, eps_rel=1e-10, max_depth=24)
    return float(C_KM_S) * float(val)


def _load_priors(*, csv_path: Path, cov_path: Path, use_cov_requested: bool) -> Tuple[CMBPriorsDataset, str, bool, Optional[str]]:
    if not csv_path.is_file():
        raise DiagnosticError(f"CMB priors CSV not found: {csv_path.name}")

    if use_cov_requested:
        if not cov_path.is_file():
            return CMBPriorsDataset.from_csv(csv_path, cov_path=None, name="chw2018_diag"), "diag", False, "covariance file missing"
        try:
            ds_cov = CMBPriorsDataset.from_csv(csv_path, cov_path=cov_path, name="chw2018_cov")
            return ds_cov, "cov", True, None
        except RuntimeError as exc:
            # numpy missing or covariance backend unavailable
            return CMBPriorsDataset.from_csv(csv_path, cov_path=None, name="chw2018_diag"), "diag", False, str(exc)
        except Exception as exc:
            return CMBPriorsDataset.from_csv(csv_path, cov_path=None, name="chw2018_diag"), "diag", False, str(exc)

    return CMBPriorsDataset.from_csv(csv_path, cov_path=None, name="chw2018_diag"), "diag", False, None


def _find_prior(priors_ds: CMBPriorsDataset, key: str) -> Tuple[float, float]:
    for p in priors_ds.priors:
        if str(p.name) == str(key):
            return float(p.value), float(p.sigma)
    raise DiagnosticError(f"missing key in priors dataset: {key}")


def _drift_vs_cmb_check(
    *,
    drift_eps: float,
    z_drift_min: float,
    z_drift_max: float,
    use_cov_requested: bool,
    priors_csv_path: Path,
    priors_cov_path: Path,
) -> Dict[str, Any]:
    if not (math.isfinite(float(drift_eps)) and 0.0 < float(drift_eps) < 0.5):
        raise UsageError("--drift-eps must be finite and in (0, 0.5)")
    if not (math.isfinite(float(z_drift_min)) and math.isfinite(float(z_drift_max)) and 0.0 <= float(z_drift_min) < float(z_drift_max)):
        raise UsageError("--z-drift-min/--z-drift-max must satisfy 0 <= min < max")

    H0 = 67.4
    Omega_m = 0.315
    omega_b_h2 = 0.02237
    omega_c_h2 = 0.1200
    N_eff = 3.046
    Tcmb = 2.7255

    baseline = compute_lcdm_distance_priors(
        H0_km_s_Mpc=H0,
        Omega_m=Omega_m,
        omega_b_h2=omega_b_h2,
        omega_c_h2=omega_c_h2,
        N_eff=N_eff,
        Tcmb_K=Tcmb,
        integrator="adaptive_simpson",
        integration_eps_abs=1e-10,
        integration_eps_rel=1e-10,
    )

    z_star = float(baseline["z_star"])
    r_s_star_mpc = float(baseline["r_s_star_Mpc"])

    h = H0 / 100.0
    Omega_r = float(omega_r_h2(Tcmb_K=Tcmb, N_eff=N_eff)) / (h * h)
    Omega_lambda = 1.0 - Omega_m - Omega_r
    if not (math.isfinite(Omega_lambda) and Omega_lambda > 0.0):
        raise DiagnosticError("derived Omega_lambda is non-physical")

    def H_lcdm_full(z: float) -> float:
        zp1 = 1.0 + float(z)
        e2 = Omega_r * (zp1**4) + Omega_m * (zp1**3) + Omega_lambda
        if not (math.isfinite(e2) and e2 > 0.0):
            raise DiagnosticError("E(z)^2 became non-physical")
        return H0 * math.sqrt(e2)

    def H_toy(z: float) -> float:
        zz = float(z)
        if float(z_drift_min) <= zz <= float(z_drift_max):
            return (1.0 - float(drift_eps)) * H0 * (1.0 + zz)
        return H_lcdm_full(zz)

    D_M_toy = _dm_mpc_to_z(z=z_star, H_func_km_s_mpc=H_toy)
    R_toy = math.sqrt(Omega_m) * H0 * D_M_toy / C_KM_S
    lA_toy = math.pi * D_M_toy / r_s_star_mpc

    priors_ds, cov_mode_used, cov_used, cov_fallback_reason = _load_priors(
        csv_path=priors_csv_path,
        cov_path=priors_cov_path,
        use_cov_requested=bool(use_cov_requested),
    )

    R_mean, sigma_R = _find_prior(priors_ds, "R")
    lA_mean, sigma_lA = _find_prior(priors_ds, "lA")

    n_sigma_R = (float(R_toy) - float(R_mean)) / float(sigma_R)
    n_sigma_lA = (float(lA_toy) - float(lA_mean)) / float(sigma_lA)

    pred_vals = {
        "R": float(R_toy),
        "lA": float(lA_toy),
        "omega_b_h2": float(omega_b_h2),
    }
    chi2_res = priors_ds.chi2_from_values(pred_vals)

    return {
        "assumptions": {
            "toy_background": f"H(z)=(1-drift_eps)*H0*(1+z) in [{float(z_drift_min):g},{float(z_drift_max):g}], LCDM+rad elsewhere",
            "late_time_deformation_only": True,
            "rs_star_fixed_to_lcdm_baseline": True,
            "note": "Toy deformation check for tension quantification, not action-derived prediction.",
        },
        "inputs": {
            "H0_km_s_Mpc": float(H0),
            "Omega_m": float(Omega_m),
            "omega_b_h2": float(omega_b_h2),
            "omega_c_h2": float(omega_c_h2),
            "N_eff": float(N_eff),
            "Tcmb_K": float(Tcmb),
            "drift_eps": float(drift_eps),
            "z_drift_min": float(z_drift_min),
            "z_drift_max": float(z_drift_max),
        },
        "baseline": {
            "z_star": float(z_star),
            "D_M_star_Mpc": float(baseline["D_M_star_Mpc"]),
            "r_s_star_Mpc": float(r_s_star_mpc),
            "R": float(baseline["R"]),
            "lA": float(baseline["lA"]),
        },
        "toy_prediction": {
            "D_M_star_Mpc": float(D_M_toy),
            "R": float(R_toy),
            "lA": float(lA_toy),
        },
        "chw2018": {
            "R_mean": float(R_mean),
            "sigma_R": float(sigma_R),
            "lA_mean": float(lA_mean),
            "sigma_lA": float(sigma_lA),
            "n_sigma_R": float(n_sigma_R),
            "n_sigma_lA": float(n_sigma_lA),
            "covariance_mode_requested": "cov" if bool(use_cov_requested) else "diag",
            "covariance_mode_used": str(cov_mode_used),
            "covariance_used": bool(cov_used),
            "covariance_fallback_reason": None if cov_fallback_reason is None else str(cov_fallback_reason),
            "chi2": float(chi2_res.chi2),
            "ndof": int(chi2_res.ndof),
            "chi2_method": str(chi2_res.meta.get("method", cov_mode_used)) if isinstance(chi2_res.meta, Mapping) else str(cov_mode_used),
        },
    }


def _render_markdown(payload: Mapping[str, Any]) -> str:
    det = payload.get("details") if isinstance(payload.get("details"), Mapping) else {}
    kin = det.get("kinetic_barrier") if isinstance(det.get("kinetic_barrier"), Mapping) else {}
    scale = det.get("scale_separation") if isinstance(det.get("scale_separation"), Mapping) else {}
    drift = det.get("drift_vs_cmb") if isinstance(det.get("drift_vs_cmb"), Mapping) else {}
    chw = drift.get("chw2018") if isinstance(drift.get("chw2018"), Mapping) else {}

    lines = [
        "# Phase4 M163 Five-Problems Diagnostic Report",
        "",
        "Deterministic diagnostic artifact for kinetic barrier, scale separation, and CHW2018 tension under a toy barely-positive-drift deformation.",
        "",
        "## Summary",
        f"- barrier_present: `{bool(kin.get('barrier_present'))}`",
        f"- phi_near_over_phi_far: `{float(kin.get('phi_near_over_phi_far', float('nan'))):.6e}`",
        f"- k_star_Mpc_inv: `{float(scale.get('k_star_mpc_inv', float('nan'))):.6e}`",
        f"- n_sigma_R (drift-eps): `{float(chw.get('n_sigma_R', float('nan'))):.6f}`",
        f"- n_sigma_lA (drift-eps): `{float(chw.get('n_sigma_lA', float('nan'))):.6f}`",
        f"- covariance mode used: `{chw.get('covariance_mode_used')}`",
        "",
        "## Kinetic barrier check",
        f"- sigma_star: `{float(kin.get('sigma_star', float('nan'))):.12e}`",
        f"- sigma_near: `{float(kin.get('sigma_near', float('nan'))):.12e}`",
        f"- phi_near: `{float(kin.get('phi_near', float('nan'))):.12e}`",
        f"- phi_far: `{float(kin.get('phi_far', float('nan'))):.12e}`",
        "",
        "## Scale separation check",
        "| scale | k [Mpc^-1] | k/k* | log10((k/k*)^2) |",
        "|---|---:|---:|---:|",
    ]
    rows = scale.get("scales") if isinstance(scale.get("scales"), list) else []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| "
            + f"{row.get('label')} | {float(row.get('k_Mpc_inv', float('nan'))):.12e} | "
            + f"{float(row.get('k_over_k_star', float('nan'))):.12e} | {float(row.get('log10_k_over_k_star_sq', float('nan'))):.12e} |"
        )

    lines.extend(
        [
            "",
            "## Drift vs CHW2018 (toy)",
            f"- R_toy: `{float(drift.get('toy_prediction', {}).get('R', float('nan'))):.12e}`",
            f"- R_mean: `{float(chw.get('R_mean', float('nan'))):.12e}`",
            f"- sigma_R: `{float(chw.get('sigma_R', float('nan'))):.12e}`",
            f"- n_sigma_R: `{float(chw.get('n_sigma_R', float('nan'))):.12e}`",
            f"- chi2: `{float(chw.get('chi2', float('nan'))):.12e}` (`ndof={int(chw.get('ndof', -1))}`)",
            "",
            "## Scope and non-claims",
            "- This report is a deterministic diagnostic note, not a full cosmology fit.",
            "- `mu`-running to cosmic-time variation is not implied without extra assumptions.",
            "- Toy barely-positive-drift deformation is not action-derived.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_text(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return (
        f"schema={payload.get('schema')}\n"
        f"status={payload.get('status')}\n"
        f"barrier_present={bool(summary.get('barrier_present'))}\n"
        f"n_sigma_R={float(summary.get('n_sigma_R', float('nan'))):.12e}\n"
        f"n_sigma_lA={float(summary.get('n_sigma_lA', float('nan'))):.12e}\n"
        f"covariance_mode_used={summary.get('covariance_mode_used')}\n"
        "report_json=FIVE_PROBLEMS_REPORT.json\n"
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic Phase4 M163 Five-Problems diagnostic report.")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--format", choices=("json", "text"), default="json")
    ap.add_argument("--created-utc", type=int, default=DEFAULT_CREATED_UTC_EPOCH)

    ap.add_argument("--sigma-star-ratio", type=float, default=0.85)
    ap.add_argument("--omega0", type=float, default=500.0)
    ap.add_argument("--lambda-qcd-gev", type=float, default=0.2)

    ap.add_argument("--drift-eps", type=float, default=0.01)
    ap.add_argument("--z-drift-min", type=float, default=2.0)
    ap.add_argument("--z-drift-max", type=float, default=5.0)

    ap.add_argument("--use-cov", type=int, choices=(0, 1), default=1)
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)

        created_epoch = int(args.created_utc)
        created_utc_iso = _to_iso_utc(created_epoch)

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        priors_csv_path = (ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv").resolve()
        priors_cov_path = (ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov").resolve()

        kin = _kinetic_barrier_check(
            sigma_star_ratio=float(args.sigma_star_ratio),
            omega0=float(args.omega0),
        )
        scale = _scale_separation_check(lambda_qcd_gev=float(args.lambda_qcd_gev))
        drift = _drift_vs_cmb_check(
            drift_eps=float(args.drift_eps),
            z_drift_min=float(args.z_drift_min),
            z_drift_max=float(args.z_drift_max),
            use_cov_requested=bool(int(args.use_cov)),
            priors_csv_path=priors_csv_path,
            priors_cov_path=priors_cov_path,
        )

        chw = drift["chw2018"] if isinstance(drift.get("chw2018"), Mapping) else {}

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "status": "ok",
            "created_utc": int(created_epoch),
            "created_utc_iso": str(created_utc_iso),
            "repo_version_dir": "v11.0.0",
            "paths_redacted": True,
            "inputs": {
                "sigma_star_ratio": float(args.sigma_star_ratio),
                "omega0": float(args.omega0),
                "lambda_qcd_gev": float(args.lambda_qcd_gev),
                "drift_eps": float(args.drift_eps),
                "z_drift_min": float(args.z_drift_min),
                "z_drift_max": float(args.z_drift_max),
                "use_cov_requested": bool(int(args.use_cov)),
                "priors_basename": priors_csv_path.name,
                "priors_sha256": _sha256_file(priors_csv_path),
                "cov_basename": priors_cov_path.name,
                "cov_sha256": _sha256_file(priors_cov_path) if priors_cov_path.is_file() else None,
            },
            "summary": {
                "barrier_present": bool(kin.get("barrier_present")),
                "phi_near_over_phi_far": float(kin.get("phi_near_over_phi_far", float("nan"))),
                "k_star_mpc_inv": float(scale.get("k_star_mpc_inv", float("nan"))),
                "n_sigma_R": float(chw.get("n_sigma_R", float("nan"))),
                "n_sigma_lA": float(chw.get("n_sigma_lA", float("nan"))),
                "covariance_mode_used": str(chw.get("covariance_mode_used", "diag")),
                "chi2": float(chw.get("chi2", float("nan"))),
                "ndof": int(chw.get("ndof", -1)),
            },
            "details": {
                "kinetic_barrier": kin,
                "scale_separation": scale,
                "drift_vs_cmb": drift,
            },
            **_snapshot_fingerprint(),
        }

        md_text = _render_markdown(payload)
        md_path = outdir / "FIVE_PROBLEMS_REPORT.md"
        md_path.write_text(md_text, encoding="utf-8")

        json_text = _json_pretty(payload)
        json_path = outdir / "FIVE_PROBLEMS_REPORT.json"
        json_path.write_text(json_text, encoding="utf-8")

        if str(args.format) == "json":
            print(json_text, end="")
        else:
            print(_render_text(payload), end="")
        return 0

    except (UsageError, DiagnosticError, ValueError) as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
