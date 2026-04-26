#!/usr/bin/env python3
"""Phase-3 SigmaTensor-v1 growth + fsigma8 diagnostic report (stdlib-only).

Scope:
- GR linear-growth overlay over explicit SigmaTensor-v1 background
- optional RSD chi2 diagnostic with diagonal covariance and optional AP correction
- no full Boltzmann perturbation solver or likelihood fit
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    D_A_flat,
    FlatLambdaCDMHistory,
    H0_to_SI,
)
from gsc.structure.growth_factor import (  # noqa: E402
    growth_observables_from_solution,
    solve_growth_ln_a,
)
from gsc.structure.power_spectrum_linear import sigma8_0_from_As  # noqa: E402
from gsc.structure.rsd_fsigma8_data import (  # noqa: E402
    chi2_diag,
    load_fsigma8_csv,
    profile_scale_chi2_diag,
)
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1History,
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


TOOL_NAME = "phase3_sf_sigmatensor_fsigma8_report"
SCHEMA_NAME = "phase3_sigmatensor_fsigma8_report_v1"
FAIL_MARKER = "PHASE3_SIGMATENSOR_FSIGMA8_FAILED"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
DEFAULT_DATA_PATH = ROOT / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"
AP_DA_TRAPZ_N = 4000
_CSV_FMT = "{:.12e}"
_CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class UsageError(Exception):
    """Usage/configuration error (exit 1)."""


class GateError(Exception):
    """Physics/data precondition gate failure (exit 2)."""


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise UsageError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise UsageError(f"{name} must be a finite float")
    return float(out)


def _finite_positive(value: Any, *, name: str) -> float:
    out = _finite_float(value, name=name)
    if out <= 0.0:
        raise UsageError(f"{name} must be > 0")
    return float(out)


def _normalize_created_utc(value: str) -> str:
    text = str(value or "").strip()
    if not _CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt(v: float) -> str:
    return _CSV_FMT.format(float(v))


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_rows_digest(rows: Sequence[Mapping[str, float]]) -> str:
    lines: List[str] = []
    for row in rows:
        lines.append(
            f"{float(row['z']):.12e},{float(row['E']):.12e},{float(row['w_phi']):.12e},"
            f"{float(row['Omega_phi']):.12e},{float(row['D']):.12e},{float(row['f']):.12e},"
            f"{float(row['fsigma8']):.12e}\n"
        )
    return _sha256_text("".join(lines))


def _stable_residual_digest(rows: Sequence[Mapping[str, float]]) -> str:
    lines: List[str] = []
    for row in rows:
        lines.append(
            f"{float(row['z']):.12e},{float(row['residual']):.12e},{float(row['pull']):.12e}\n"
        )
    return _sha256_text("".join(lines))


def _canonical_transfer_model(name: str) -> str:
    raw = str(name).strip().lower()
    if raw == "bbks":
        return "bbks"
    if raw in {"eh98", "eh98_nowiggle"}:
        return "eh98_nowiggle"
    raise UsageError("unsupported transfer model; expected one of: bbks, eh98_nowiggle")


def _require_bg_zmax(*, z_start: float, eps_dlnH: float) -> float:
    return float(z_start + (1.0 + z_start) * (3.0 * eps_dlnH) + 1.0e-3)


def _derive_z_max_bg_effective(*, z_start: float, eps_dlnH: float, z_max_bg_arg: Optional[float]) -> Tuple[Optional[float], float]:
    needed = _require_bg_zmax(z_start=z_start, eps_dlnH=eps_dlnH)
    if z_max_bg_arg is None:
        return None, float(needed)
    requested = float(z_max_bg_arg)
    if requested <= 0.0:
        raise UsageError("--z-max-bg must be > 0 when provided")
    return float(requested), float(max(requested, needed))


def _ap_factor(
    *,
    z: float,
    omega_m_ref: float,
    ap_correction: bool,
    history: SigmaTensorV1History,
    H0_si: float,
    model_da_cache: Dict[float, float],
    ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]],
) -> float:
    if not ap_correction:
        return 1.0

    z_key = float(z)
    om_key = float(omega_m_ref)

    if z_key not in model_da_cache:
        h_model = float(history.H(z_key))
        da_model = float(D_A_flat(z=z_key, H_of_z=history.H, n=AP_DA_TRAPZ_N))
        if not (math.isfinite(h_model) and h_model > 0.0 and math.isfinite(da_model) and da_model > 0.0):
            raise GateError("invalid model H(z) or D_A(z) for AP correction")
        model_da_cache[z_key] = float(da_model)

    ref_key = (z_key, om_key)
    if ref_key not in ref_hd_cache:
        ref_history = FlatLambdaCDMHistory(
            H0=float(H0_si),
            Omega_m=float(om_key),
            Omega_Lambda=float(max(0.0, 1.0 - om_key)),
        )
        h_ref = float(ref_history.H(z_key))
        da_ref = float(D_A_flat(z=z_key, H_of_z=ref_history.H, n=AP_DA_TRAPZ_N))
        if not (math.isfinite(h_ref) and h_ref > 0.0 and math.isfinite(da_ref) and da_ref > 0.0):
            raise GateError("invalid reference H(z) or D_A(z) for AP correction")
        ref_hd_cache[ref_key] = (float(h_ref), float(da_ref))

    h_model = float(history.H(z_key))
    da_model = float(model_da_cache[z_key])
    h_ref, da_ref = ref_hd_cache[ref_key]
    return float((h_ref * da_ref) / (h_model * da_model))


def _summary_markdown(*, args: argparse.Namespace, payload: Mapping[str, Any]) -> str:
    lines: List[str] = [
        "# SigmaTensor-v1 growth / fsigma8 diagnostic report",
        "",
        "Claim-safe scope: GR linear-growth overlay on an explicit background history.",
        "This report is a diagnostic layer and not a full Boltzmann perturbation fit.",
        "",
        "## Inputs",
        f"- H0_km_s_Mpc: `{float(payload['params']['H0_km_s_Mpc']):.12g}`",
        f"- Omega_m0: `{float(payload['params']['Omega_m0']):.12g}`",
        f"- w_phi0: `{float(payload['params']['w_phi0']):.12g}`",
        f"- lambda: `{float(payload['params']['lambda']):.12g}`",
        f"- sigma8_mode: `{payload['sigma8']['mode']}`",
        "",
        "## Key values",
        "",
        "| z | E | w_phi | Omega_phi | D | f | fsigma8 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]

    rows = payload.get("grids", {}).get("rows", []) if isinstance(payload.get("grids"), Mapping) else []
    probe_z = {0.0, 0.5, 1.0, 2.0}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        z = float(row.get("z", 0.0))
        if min(abs(z - p) for p in probe_z) > 1.0e-12:
            continue
        lines.append(
            "| "
            + f"{z:.6g} | {float(row.get('E')):.12g} | {float(row.get('w_phi')):.12g} | "
            + f"{float(row.get('Omega_phi')):.12g} | {float(row.get('D')):.12g} | {float(row.get('f')):.12g} | "
            + f"{float(row.get('fsigma8')):.12g} |"
        )

    rsd = payload.get("rsd") if isinstance(payload.get("rsd"), Mapping) else None
    if rsd is not None:
        lines.extend(
            [
                "",
                "## RSD diagnostic",
                f"- n_points: `{int(rsd.get('n_points') or 0)}`",
                f"- chi2: `{float(rsd.get('chi2')):.12g}`",
                f"- ap_correction: `{bool(rsd.get('ap_correction'))}`",
            ]
        )
        sigma8_block = payload.get("sigma8")
        sigma8_bestfit = (
            sigma8_block.get("sigma8_0_bestfit")
            if isinstance(sigma8_block, Mapping)
            else None
        )
        if sigma8_bestfit is not None:
            lines.append(f"- sigma8_0_bestfit: `{float(sigma8_bestfit):.12g}`")

    cmd = [
        "python3 v11.0.0/scripts/phase3_sf_sigmatensor_fsigma8_report.py",
        f"--H0-km-s-Mpc {float(args.H0_km_s_Mpc):.12g}",
        f"--Omega-m {float(args.Omega_m):.12g}",
        f"--w0 {float(args.w0):.12g}",
        f"--lambda {float(args.lambda_):.12g}",
        f"--z-start {float(args.z_start):.12g}",
        f"--n-steps-growth {int(args.n_steps_growth)}",
        f"--n-steps-bg {int(args.n_steps_bg)}",
        f"--sigma8-mode {str(args.sigma8_mode)}",
        "--outdir <outdir>",
        "--format text",
    ]
    if args.sigma8_mode == "fixed":
        cmd.append(f"--sigma8-0 {float(args.sigma8_0):.12g}")
    if args.sigma8_mode == "derived_As":
        cmd.append(f"--As {float(args.As):.12g}")
    if int(args.rsd) == 0:
        cmd.append("--rsd 0")
    if int(args.ap_correction) == 1:
        cmd.append("--ap-correction 1")
    lines.extend(
        [
            "",
            "## Reproduce",
            "```bash",
            " \\\n  ".join(cmd),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _text_summary(payload: Mapping[str, Any]) -> str:
    rows = payload.get("grids", {}).get("rows", []) if isinstance(payload.get("grids"), Mapping) else []
    row_map: Dict[float, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_map[float(row.get("z", 0.0))] = row

    probes = [0.0, 0.5, 1.0, 2.0]
    lines: List[str] = ["SigmaTensor-v1 growth / fsigma8 summary", "z,E,w_phi,Omega_phi,D,f,fsigma8"]
    for z in probes:
        row = row_map.get(float(z))
        if row is None:
            continue
        lines.append(
            f"{z:.6g},{float(row['E']):.12g},{float(row['w_phi']):.12g},{float(row['Omega_phi']):.12g},"
            f"{float(row['D']):.12g},{float(row['f']):.12g},{float(row['fsigma8']):.12g}"
        )
    rsd = payload.get("rsd") if isinstance(payload.get("rsd"), Mapping) else None
    if rsd is not None:
        lines.append("")
        lines.append(f"rsd_chi2={float(rsd.get('chi2')):.12g} n_points={int(rsd.get('n_points') or 0)}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Phase-3 SigmaTensor-v1 growth + fsigma8 diagnostic report (stdlib-only).")
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, required=True)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, required=True)
    ap.add_argument("--w0", type=float, required=True)
    ap.add_argument("--lambda", dest="lambda_", type=float, required=True)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)

    ap.add_argument("--z-start", dest="z_start", type=float, default=100.0)
    ap.add_argument("--n-steps-growth", dest="n_steps_growth", type=int, default=4000)
    ap.add_argument("--eps-dlnH", dest="eps_dlnH", type=float, default=1.0e-5)
    ap.add_argument("--z-max-bg", dest="z_max_bg", type=float, default=None)
    ap.add_argument("--n-steps-bg", dest="n_steps_bg", type=int, default=8192)

    ap.add_argument("--sigma8-mode", choices=("nuisance", "derived_As", "fixed"), default="nuisance")
    ap.add_argument("--sigma8-0", dest="sigma8_0", type=float, default=None)
    ap.add_argument("--As", dest="As", type=float, default=None)
    ap.add_argument("--ns", dest="ns", type=float, default=0.965)
    ap.add_argument("--transfer-model", choices=("bbks", "eh98_nowiggle"), default="bbks")
    ap.add_argument("--Omega-b0", dest="Omega_b0", type=float, default=0.049)
    ap.add_argument("--k0-mpc", dest="k0_mpc", type=float, default=0.05)
    ap.add_argument("--k-pivot-mpc", dest="k_pivot_mpc", type=float, default=None)
    ap.add_argument("--kmin", dest="kmin", type=float, default=1.0e-4)
    ap.add_argument("--kmax", dest="kmax", type=float, default=1.0e2)
    ap.add_argument("--nk", dest="nk", type=int, default=2048)

    ap.add_argument("--rsd", choices=("0", "1"), default="1")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    ap.add_argument("--ap-correction", choices=("0", "1"), default="0")

    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))

        H0_km = _finite_positive(args.H0_km_s_Mpc, name="--H0-km-s-Mpc")
        H0_si = float(H0_to_SI(H0_km))
        omega_m0 = _finite_positive(args.Omega_m, name="--Omega-m")
        w0 = _finite_float(args.w0, name="--w0")
        lambda_ = _finite_float(args.lambda_, name="--lambda")
        Tcmb_K = _finite_positive(args.Tcmb_K, name="--Tcmb-K")
        N_eff = _finite_float(args.N_eff, name="--N-eff")
        if N_eff < 0.0:
            raise UsageError("--N-eff must be >= 0")

        z_start = _finite_positive(args.z_start, name="--z-start")
        n_steps_growth = int(args.n_steps_growth)
        if n_steps_growth < 16:
            raise UsageError("--n-steps-growth must be >= 16")
        eps_dlnH = _finite_positive(args.eps_dlnH, name="--eps-dlnH")
        n_steps_bg = int(args.n_steps_bg)
        if n_steps_bg < 32:
            raise UsageError("--n-steps-bg must be >= 32")

        requested_z_max_bg = None if args.z_max_bg is None else _finite_float(args.z_max_bg, name="--z-max-bg")
        z_max_bg_requested, z_max_bg_effective = _derive_z_max_bg_effective(
            z_start=float(z_start),
            eps_dlnH=float(eps_dlnH),
            z_max_bg_arg=requested_z_max_bg,
        )

        omega_r_override = None
        if args.Omega_r0_override is not None:
            omega_r_override = _finite_float(args.Omega_r0_override, name="--Omega-r0-override")
            if omega_r_override < 0.0:
                raise UsageError("--Omega-r0-override must be >= 0")

        sigma8_mode = str(args.sigma8_mode)
        sigma8_fixed: Optional[float] = None
        if sigma8_mode == "fixed":
            if args.sigma8_0 is None:
                raise UsageError("--sigma8-mode fixed requires --sigma8-0")
            sigma8_fixed = _finite_positive(args.sigma8_0, name="--sigma8-0")
        elif args.sigma8_0 is not None:
            raise UsageError("--sigma8-0 is only valid when --sigma8-mode fixed")

        As = None
        if sigma8_mode == "derived_As":
            if args.As is None:
                raise UsageError("--sigma8-mode derived_As requires --As")
            As = _finite_positive(args.As, name="--As")
        elif args.As is not None:
            raise UsageError("--As is only valid when --sigma8-mode derived_As")

        ns = _finite_float(args.ns, name="--ns")
        transfer_model = _canonical_transfer_model(str(args.transfer_model))
        omega_b0 = _finite_float(args.Omega_b0, name="--Omega-b0")
        if omega_b0 < 0.0:
            raise UsageError("--Omega-b0 must be >= 0")
        k0_mpc = _finite_positive(args.k0_mpc, name="--k0-mpc")
        k_pivot_mpc = None
        if args.k_pivot_mpc is not None:
            k_pivot_mpc = _finite_positive(args.k_pivot_mpc, name="--k-pivot-mpc")
        kmin = _finite_positive(args.kmin, name="--kmin")
        kmax = _finite_positive(args.kmax, name="--kmax")
        if kmax <= kmin:
            raise UsageError("--kmax must be > --kmin")
        nk = int(args.nk)
        if nk < 8:
            raise UsageError("--nk must be >= 8")

        rsd_enabled = str(args.rsd) == "1"
        ap_correction = str(args.ap_correction) == "1"
        data_path = Path(args.data).expanduser().resolve()

        params = SigmaTensorV1Params(
            H0_si=float(H0_si),
            Omega_m0=float(omega_m0),
            w_phi0=float(w0),
            lambda_=float(lambda_),
            Tcmb_K=float(Tcmb_K),
            N_eff=float(N_eff),
            Omega_r0_override=None if omega_r_override is None else float(omega_r_override),
            sign_u0=int(args.sign_u0),
        )
        try:
            bg = solve_sigmatensor_v1_background(
                params,
                z_max=float(z_max_bg_effective),
                n_steps=int(n_steps_bg),
            )
        except ValueError as exc:
            raise GateError(str(exc)) from exc
        hist = SigmaTensorV1History(bg)

        E_grid_bg = [float(h) / float(H0_si) for h in bg.H_grid_si]
        denom_grid = [1.0 - (float(u) * float(u)) / 6.0 for u in bg.u_grid]

        def E_of_z_growth(z: float) -> float:
            zz = float(z)
            if zz < 0.0:
                zz = 0.0
            return float(hist.E(zz))

        rsd_rows: List[Mapping[str, Any]] = []
        data_sha256: Optional[str] = None
        z_data: List[float] = []
        if rsd_enabled:
            try:
                rsd_rows = list(load_fsigma8_csv(str(data_path)))
            except Exception as exc:
                raise GateError(f"failed to parse RSD dataset: {exc}") from exc
            if not rsd_rows:
                raise GateError("RSD dataset has no usable rows")
            data_sha256 = _sha256_file(data_path)
            z_data = sorted({float(row["z"]) for row in rsd_rows})

        z_eval_cap = max(5.0, max(z_data) if z_data else 0.0)
        z_grid_set = {float(z) for z in (0.0, 0.5, 1.0, 2.0, 5.0) if float(z) <= z_eval_cap + 1.0e-12}
        if rsd_enabled:
            z_grid_set.update(z_data)
        z_grid = sorted(z_grid_set)
        if not z_grid:
            z_grid = [0.0]
        if max(z_grid) >= float(z_start):
            raise GateError("--z-start must be strictly greater than all evaluation z values")

        try:
            growth_solution = solve_growth_ln_a(
                E_of_z_growth,
                float(omega_m0),
                z_start=float(z_start),
                z_targets=z_grid,
                n_steps=int(n_steps_growth),
                eps_dlnH=float(eps_dlnH),
            )
            growth_obs = growth_observables_from_solution(growth_solution, z_grid)
        except ValueError as exc:
            raise GateError(str(exc)) from exc
        obs_by_z: Dict[float, Dict[str, float]] = {}
        for i, z in enumerate(growth_obs["z"]):
            obs_by_z[float(z)] = {
                "D": float(growth_obs["D"][i]),
                "f": float(growth_obs["f"][i]),
                "g": float(growth_obs["g"][i]),
            }

        sigma8_0_used: Optional[float] = None
        sigma8_0_bestfit: Optional[float] = None
        sigma8_source: str
        if sigma8_mode == "fixed":
            sigma8_0_used = float(sigma8_fixed)
            sigma8_source = "fixed"
        elif sigma8_mode == "derived_As":
            try:
                sigma8_0_used = sigma8_0_from_As(
                    As=float(As),
                    ns=float(ns),
                    omega_m0=float(omega_m0),
                    h=float(H0_km) / 100.0,
                    transfer_model=str(transfer_model),
                    omega_b0=float(omega_b0),
                    Tcmb_K=float(Tcmb_K),
                    N_eff=float(N_eff),
                    k0_mpc=float(k0_mpc),
                    k_pivot_mpc=(None if k_pivot_mpc is None else float(k_pivot_mpc)),
                    kmin=float(kmin),
                    kmax=float(kmax),
                    nk=int(nk),
                    E_of_z=E_of_z_growth,
                    z_start=float(z_start),
                    n_steps=int(n_steps_growth),
                    eps_dlnH=float(eps_dlnH),
                )
            except ValueError as exc:
                raise GateError(str(exc)) from exc
            sigma8_source = "sigma8_0_from_As"
        else:
            if not rsd_enabled:
                raise GateError("--sigma8-mode nuisance requires --rsd 1")
            if not rsd_rows:
                raise GateError("RSD dataset is required for --sigma8-mode nuisance")
            data_y: List[float] = []
            sigmas: List[float] = []
            model_t: List[float] = []
            model_da_cache: Dict[float, float] = {}
            ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]] = {}
            for row in rsd_rows:
                z = float(row["z"])
                y = float(row["fsigma8"])
                sigma = float(row["sigma"])
                om_ref = float(row["omega_m_ref"])
                g = float(obs_by_z[z]["g"])
                ap_factor = _ap_factor(
                    z=z,
                    omega_m_ref=om_ref,
                    ap_correction=bool(ap_correction),
                    history=hist,
                    H0_si=float(H0_si),
                    model_da_cache=model_da_cache,
                    ref_hd_cache=ref_hd_cache,
                )
                t = float(g * ap_factor)
                data_y.append(y)
                sigmas.append(sigma)
                model_t.append(t)
            try:
                prof = profile_scale_chi2_diag(data_y, model_t, sigmas)
            except ValueError as exc:
                raise GateError(str(exc)) from exc
            scale = prof.get("scale_bestfit")
            if scale is None:
                raise GateError("nuisance profiling failed (non-positive denominator)")
            sigma8_0_bestfit = float(scale)
            sigma8_0_used = float(scale)
            sigma8_source = "profile_scale"

        if sigma8_0_used is None or not (math.isfinite(float(sigma8_0_used)) and float(sigma8_0_used) > 0.0):
            raise GateError("failed to determine sigma8_0")

        grid_rows: List[Dict[str, float]] = []
        for z in z_grid:
            pack = obs_by_z[float(z)]
            grid_rows.append(
                {
                    "z": float(z),
                    "E": float(hist.E(z)),
                    "w_phi": float(hist.w_phi(z)),
                    "Omega_phi": float(hist.Omega_phi(z)),
                    "D": float(pack["D"]),
                    "f": float(pack["f"]),
                    "fsigma8": float(pack["g"] * float(sigma8_0_used)),
                }
            )

        rsd_payload: Optional[Dict[str, Any]] = None
        if rsd_enabled:
            model_da_cache = {}
            ref_hd_cache = {}
            residual_rows: List[Dict[str, float]] = []
            sigmas = []
            residuals = []
            for row in rsd_rows:
                z = float(row["z"])
                y = float(row["fsigma8"])
                sigma = float(row["sigma"])
                om_ref = float(row["omega_m_ref"])
                g = float(obs_by_z[z]["g"])
                ap_factor = _ap_factor(
                    z=z,
                    omega_m_ref=om_ref,
                    ap_correction=bool(ap_correction),
                    history=hist,
                    H0_si=float(H0_si),
                    model_da_cache=model_da_cache,
                    ref_hd_cache=ref_hd_cache,
                )
                pred = float(float(sigma8_0_used) * g * ap_factor)
                residual = float(y - pred)
                pull = float(residual / sigma)
                residual_rows.append({"z": z, "residual": residual, "pull": pull})
                sigmas.append(float(sigma))
                residuals.append(float(residual))

            chi2 = chi2_diag(residuals, sigmas)
            rsd_payload = {
                "data_sha256": str(data_sha256),
                "data_path_redacted": data_path.name,
                "ap_correction": bool(ap_correction),
                "n_points": int(len(rsd_rows)),
                "chi2": float(chi2),
                "residuals_digest_sha256": _stable_residual_digest(residual_rows),
            }
            if sigma8_mode == "nuisance":
                rsd_payload["scale_bestfit"] = float(sigma8_0_bestfit)
                rsd_payload["chi2_min"] = float(chi2)

        payload: Dict[str, Any] = {
            "schema": SCHEMA_NAME,
            "tool": TOOL_NAME,
            "created_utc": str(created_utc),
            "params": {
                "H0_km_s_Mpc": float(H0_km),
                "H0_si": float(H0_si),
                "Omega_m0": float(omega_m0),
                "w_phi0": float(w0),
                "lambda": float(lambda_),
                "Tcmb_K": float(Tcmb_K),
                "N_eff": float(N_eff),
                "Omega_r0_override": None if omega_r_override is None else float(omega_r_override),
                "sign_u0": int(args.sign_u0),
                "z_start": float(z_start),
                "n_steps_growth": int(n_steps_growth),
                "eps_dlnH": float(eps_dlnH),
                "z_max_bg_requested": None if z_max_bg_requested is None else float(z_max_bg_requested),
                "z_max_bg_effective": float(z_max_bg_effective),
                "n_steps_bg": int(n_steps_bg),
                "sigma8_mode": str(sigma8_mode),
                "transfer_model": str(transfer_model),
                "Omega_b0": float(omega_b0),
                "k0_mpc": float(k0_mpc),
                "k_pivot_mpc": None if k_pivot_mpc is None else float(k_pivot_mpc),
                "kmin": float(kmin),
                "kmax": float(kmax),
                "nk": int(nk),
                "rsd": int(rsd_enabled),
                "ap_correction": int(ap_correction),
                "data_basename": data_path.name if rsd_enabled else None,
            },
            "derived_today": {
                "Omega_r0": float(bg.meta["Omega_r0"]),
                "Omega_phi0": float(bg.meta["Omega_phi0"]),
                "u0": float(bg.meta["u0"]),
                "Vhat0": float(bg.meta["Vhat0"]),
                "p_action": float(bg.meta["p_action"]),
            },
            "background_summary": {
                "z_start": float(z_start),
                "z_max_bg_requested": None if z_max_bg_requested is None else float(z_max_bg_requested),
                "z_max_bg_effective": float(z_max_bg_effective),
                "n_steps_bg": int(n_steps_bg),
                "denom_min": float(min(denom_grid)),
                "denom_max": float(max(denom_grid)),
                "E_min": float(min(E_grid_bg)),
                "E_max": float(max(E_grid_bg)),
                "w_phi_min": float(min(bg.wphi_grid)),
                "w_phi_max": float(max(bg.wphi_grid)),
                "Omega_phi_min": float(min(bg.Omphi_grid)),
                "Omega_phi_max": float(max(bg.Omphi_grid)),
            },
            "growth_summary": {
                "method": "rk4_ln_a_v2",
                "z_start": float(z_start),
                "n_steps_growth": int(n_steps_growth),
                "eps_dlnH": float(eps_dlnH),
            },
            "sigma8": {
                "mode": str(sigma8_mode),
                "sigma8_0_used": float(sigma8_0_used),
                "sigma8_0_bestfit": (None if sigma8_0_bestfit is None else float(sigma8_0_bestfit)),
                "sigma8_0_source": str(sigma8_source),
                "As": (None if As is None else float(As)),
                "ns": float(ns),
                "transfer_model": str(transfer_model),
                "k0_mpc": float(k0_mpc),
                "k_pivot_mpc": (None if k_pivot_mpc is None else float(k_pivot_mpc)),
            },
            "grids": {
                "z_grid": [float(z) for z in z_grid],
                "rows": grid_rows,
            },
            "digests": {
                "grid_digest_sha256": _stable_rows_digest(grid_rows),
            },
        }
        if rsd_payload is not None:
            payload["rsd"] = rsd_payload

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        json_text = _json_text(payload)
        (outdir / "FSIGMA8_REPORT.json").write_text(json_text, encoding="utf-8")

        with (outdir / "FSIGMA8_GRID.csv").open("w", encoding="utf-8", newline="") as fh:
            fh.write("z,E,w_phi,Omega_phi,D,f,fsigma8\n")
            for row in grid_rows:
                fh.write(
                    ",".join(
                        [
                            _fmt(row["z"]),
                            _fmt(row["E"]),
                            _fmt(row["w_phi"]),
                            _fmt(row["Omega_phi"]),
                            _fmt(row["D"]),
                            _fmt(row["f"]),
                            _fmt(row["fsigma8"]),
                        ]
                    )
                    + "\n"
                )

        (outdir / "SUMMARY.md").write_text(_summary_markdown(args=args, payload=payload), encoding="utf-8")

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
        sys.stdout.write(json_text)
    else:
        sys.stdout.write(_text_summary(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
