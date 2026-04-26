#!/usr/bin/env python3
"""Phase-2 linear-growth fσ8 diagnostic report (stdlib-only)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    D_A_flat,
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
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

TOOL_ID = "phase2_sf_fsigma8_report_v1"
SNIPPET_MARKER = "phase2_sf_fsigma8_snippet_v1"
DEFAULT_Z_GRID = [0.0, 0.5, 1.0, 2.0]
DEFAULT_RSD_DATA_PATH = ROOT / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"
AP_DA_TRAPZ_N = 4000


class DataParseError(Exception):
    """Raised when input data cannot be parsed."""

    def __init__(self, message: str, *, code: int = 1) -> None:
        super().__init__(message)
        self.code = int(code)


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise ValueError(f"{name} must be a finite float")
    return float(out)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_transfer_model(name: str) -> str:
    raw = str(name).strip().lower()
    if raw in {"bbks"}:
        return "bbks"
    if raw in {"eh98", "eh98_nowiggle"}:
        return "eh98_nowiggle"
    raise ValueError("unsupported transfer model; expected one of: bbks, eh98_nowiggle")


def _parse_data_csv(path: Path) -> List[Dict[str, float]]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DataParseError(f"failed to read --data: {exc}", code=1) from exc

    filtered: List[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        filtered.append(line)

    if not filtered:
        raise DataParseError("--data has no usable rows", code=2)

    reader = csv.DictReader(filtered)
    if reader.fieldnames is None:
        raise DataParseError("--data CSV missing header", code=2)

    required = {"z", "fsigma8", "sigma"}
    got = {str(name).strip() for name in reader.fieldnames}
    if not required.issubset(got):
        raise DataParseError("--data CSV must include header columns: z,fsigma8,sigma", code=2)

    rows: List[Dict[str, float]] = []
    for idx, row in enumerate(reader, start=2):
        try:
            z = _finite_float(row.get("z"), name=f"z (row {idx})")
            y = _finite_float(row.get("fsigma8"), name=f"fsigma8 (row {idx})")
            sigma = _finite_float(row.get("sigma"), name=f"sigma (row {idx})")
        except ValueError as exc:
            raise DataParseError(str(exc), code=2) from exc
        if z < 0.0:
            raise DataParseError(f"z (row {idx}) must be >= 0", code=2)
        if sigma <= 0.0:
            raise DataParseError(f"sigma (row {idx}) must be > 0", code=2)
        rows.append({"z": float(z), "obs": float(y), "sigma": float(sigma)})

    if not rows:
        raise DataParseError("--data has no usable points", code=2)
    return rows


def _history_payload(args: argparse.Namespace) -> Dict[str, Any]:
    omega_lambda = float(args.Omega_lambda) if args.Omega_lambda is not None else (1.0 - float(args.Omega_m))
    payload: Dict[str, Any] = {
        "type": str(args.history),
        "H0_km_s_Mpc": float(args.H0),
        "Omega_m": float(args.Omega_m),
        "Omega_lambda": float(omega_lambda),
        "Omega_b": float(args.Omega_b0),
        "p": None,
        "z_transition": None,
    }
    if args.history == "gsc_transition":
        payload["p"] = float(args.p)
        payload["z_transition"] = float(args.z_transition)
    return payload


def _build_history(args: argparse.Namespace):
    H0_km = _finite_float(args.H0, name="--H0")
    omega_m = _finite_float(args.Omega_m, name="--Omega-m")
    if not (omega_m > 0.0):
        raise ValueError("--Omega-m must be > 0")

    omega_lambda = float(args.Omega_lambda) if args.Omega_lambda is not None else (1.0 - omega_m)
    if not math.isfinite(omega_lambda):
        raise ValueError("--Omega-lambda must be finite")

    H0_si = H0_to_SI(H0_km)
    if args.history == "lcdm":
        return FlatLambdaCDMHistory(H0=H0_si, Omega_m=omega_m, Omega_Lambda=omega_lambda), H0_si

    p = _finite_float(args.p, name="--p")
    z_t = _finite_float(args.z_transition, name="--z-transition")
    return (
        GSCTransitionHistory(
            H0=H0_si,
            Omega_m=omega_m,
            Omega_Lambda=omega_lambda,
            p=p,
            z_transition=z_t,
        ),
        H0_si,
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Phase-2 structure formation linear-growth fσ8 diagnostic (stdlib-only).")
    ap.add_argument("--history", choices=("lcdm", "gsc_transition"), default=None)
    ap.add_argument("--H0", type=float, default=None)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=None)
    ap.add_argument("--Omega-lambda", dest="Omega_lambda", type=float, default=None)
    ap.add_argument("--Omega-b0", dest="Omega_b0", type=float, default=0.049)
    ap.add_argument("--Tcmb", dest="Tcmb", type=float, default=2.7255)

    ap.add_argument("--p", type=float, default=None)
    ap.add_argument("--z-transition", dest="z_transition", type=float, default=None)

    ap.add_argument("--z-start", dest="z_start", type=float, default=100.0)
    ap.add_argument("--n-steps", dest="n_steps", type=int, default=4000)
    ap.add_argument("--eps-dlnH", dest="eps_dlnH", type=float, default=1.0e-5)

    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--sigma8", type=float, default=None)
    ap.add_argument("--fit-sigma8", dest="fit_sigma8", choices=("0", "1"), default=None)
    ap.add_argument("--sigma8-mode", choices=("nuisance", "derived_As"), default="nuisance")

    ap.add_argument("--As", type=float, default=None)
    ap.add_argument("--ns", type=float, default=1.0, help="Primordial tilt n_s (dimensionless).")
    ap.add_argument(
        "--k-pivot",
        dest="k_pivot_mpc",
        type=float,
        default=0.05,
        help="Primordial pivot scale in 1/Mpc.",
    )
    ap.add_argument("--k0-mpc", dest="k0_mpc_legacy", type=float, default=None, help=argparse.SUPPRESS)
    ap.add_argument(
        "--transfer-model",
        choices=("bbks", "eh98", "eh98_nowiggle"),
        default="bbks",
        help="Transfer backend used in derived_As mode (approximation-first).",
    )
    ap.add_argument(
        "--transfer",
        dest="transfer_legacy",
        choices=("bbks", "eh98", "eh98_nowiggle"),
        default=None,
        help=argparse.SUPPRESS,
    )
    ap.add_argument("--kmin", type=float, default=1.0e-4)
    ap.add_argument("--kmax", type=float, default=1.0e2)
    ap.add_argument("--nk", type=int, default=2048)

    ap.add_argument("--rsd", action="store_true", help="Enable RSD fσ8 diagnostic chi2 block.")
    ap.add_argument(
        "--rsd-data",
        type=Path,
        default=DEFAULT_RSD_DATA_PATH,
        help="RSD fσ8 CSV with columns: z,fsigma8,sigma,omega_m_ref,ref_key",
    )
    ap.add_argument(
        "--rsd-ap-correction",
        choices=("none", "ref_omega_m_lcdm"),
        default="none",
        help="Optional AP-like correction for diagnostic comparison.",
    )
    ap.add_argument(
        "--emit-snippets",
        type=Path,
        default=None,
        help="Optional output directory for deterministic phase2_sf_fsigma8.{md,tex,json} snippets.",
    )
    ap.add_argument("--toy", action="store_true", help="Use deterministic toy defaults when required cosmology args are omitted.")

    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--json-out", type=Path, default=None)
    return ap.parse_args(argv)


def _as_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _fmt_float(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        out = float(value)
    except Exception:
        return "n/a"
    if not math.isfinite(out):
        return "n/a"
    return f"{out:.12g}"


def _tex_escape(value: str) -> str:
    text = str(value)
    repl = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
    }
    out = text
    for src, dst in repl.items():
        out = out.replace(src, dst)
    return out


def _snippet_summary(payload: Mapping[str, Any]) -> Dict[str, Any]:
    sigma8 = payload.get("sigma8") if isinstance(payload.get("sigma8"), Mapping) else {}
    rsd = payload.get("rsd_fsigma8") if isinstance(payload.get("rsd_fsigma8"), Mapping) else {}
    data = payload.get("data") if isinstance(payload.get("data"), Mapping) else {}
    if rsd:
        if bool(rsd.get("fit_sigma8")):
            chi2 = rsd.get("chi2_min")
            dof = rsd.get("dof")
        else:
            chi2 = rsd.get("chi2")
            dof = rsd.get("dof")
    else:
        chi2 = data.get("chi2")
        dof = data.get("dof")
    summary: Dict[str, Any] = {
        "dataset_id": payload.get("rsd_dataset_id"),
        "dataset_sha256": payload.get("rsd_dataset_sha256"),
        "n_points": rsd.get("n_points", data.get("n_points", 0)),
        "chi2_total": chi2,
        "dof": dof,
        "sigma8_mode": sigma8.get("mode"),
        "fit_sigma8": rsd.get("fit_sigma8", data.get("fit_sigma8", False)),
        "transfer_model": payload.get("transfer_model"),
        "primordial_ns": sigma8.get("primordial_ns"),
        "primordial_k_pivot_mpc": sigma8.get("primordial_k_pivot_mpc"),
        "status": "ok" if (rsd and not rsd.get("error")) or (data and data.get("chi2") is not None) else "unavailable",
        "status_reason": rsd.get("error") if rsd else None,
    }
    return summary


def _render_snippet_md(payload: Mapping[str, Any]) -> str:
    s = _snippet_summary(payload)
    lines: List[str] = [
        f"<!-- {SNIPPET_MARKER} -->",
        "## Structure formation diagnostics (`fσ8` / RSD)",
        "",
        f"- dataset_id: `{s.get('dataset_id') or 'n/a'}`",
        f"- dataset_sha256: `{s.get('dataset_sha256') or 'n/a'}`",
        f"- n_points: `{int(s.get('n_points') or 0)}`",
        f"- chi2_total: `{_fmt_float(s.get('chi2_total'))}`",
        f"- dof: `{_fmt_float(s.get('dof'))}`",
        f"- sigma8_mode: `{s.get('sigma8_mode') or 'n/a'}`",
        f"- transfer_model: `{s.get('transfer_model') or 'n/a'}`",
        f"- primordial_ns: `{_fmt_float(s.get('primordial_ns'))}`",
        f"- primordial_k_pivot_mpc: `{_fmt_float(s.get('primordial_k_pivot_mpc'))}`",
    ]
    if s.get("status") != "ok":
        lines.append(f"- status: `unavailable` ({s.get('status_reason') or 'missing diagnostics'})")
    lines.extend(
        [
            "",
            "Scope boundary: linear-theory growth with approximate transfer functions; not a full nonlinear LSS treatment.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_snippet_tex(payload: Mapping[str, Any]) -> str:
    s = _snippet_summary(payload)
    lines: List[str] = [
        f"% {SNIPPET_MARKER}",
        "\\paragraph{Structure formation diagnostics ($f\\sigma_8$/RSD).}",
        "\\begin{itemize}",
        "\\item dataset id: \\texttt{"
        + _tex_escape(str(s.get("dataset_id") or "n/a"))
        + "}, dataset sha256: \\texttt{"
        + _tex_escape(str(s.get("dataset_sha256") or "n/a"))
        + "}.",
        "\\item points: "
        + _tex_escape(str(int(s.get("n_points") or 0)))
        + ", $\\chi^2_\\mathrm{total}="
        + _tex_escape(_fmt_float(s.get("chi2_total")))
        + "$, dof="
        + _tex_escape(_fmt_float(s.get("dof")))
        + ".",
        "\\item mode: \\texttt{"
        + _tex_escape(str(s.get("sigma8_mode") or "n/a"))
        + "}, transfer: \\texttt{"
        + _tex_escape(str(s.get("transfer_model") or "n/a"))
        + "}, $n_s="
        + _tex_escape(_fmt_float(s.get("primordial_ns")))
        + "$, $k_\\mathrm{pivot}="
        + _tex_escape(_fmt_float(s.get("primordial_k_pivot_mpc")))
        + "\\,\\mathrm{Mpc}^{-1}$.",
    ]
    if s.get("status") != "ok":
        lines.append(
            "\\item status: unavailable ("
            + _tex_escape(str(s.get("status_reason") or "missing diagnostics"))
            + ")."
        )
    lines.extend(
        [
            "\\end{itemize}",
            "\\noindent\\textit{Scope boundary: linear-theory growth with approximate transfer functions; not a full nonlinear LSS treatment.}",
            "",
        ]
    )
    return "\n".join(lines)


def _emit_snippets(*, outdir: Path, payload: Mapping[str, Any]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    summary = _snippet_summary(payload)
    snippet_json = {
        "marker": SNIPPET_MARKER,
        "schema": "phase2_sf_fsigma8_snippet_v1",
        "summary": summary,
    }
    (outdir / "phase2_sf_fsigma8.md").write_text(_render_snippet_md(payload).rstrip("\n") + "\n", encoding="utf-8")
    (outdir / "phase2_sf_fsigma8.tex").write_text(_render_snippet_tex(payload).rstrip("\n") + "\n", encoding="utf-8")
    (outdir / "phase2_sf_fsigma8.json").write_text(
        json.dumps(snippet_json, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _text_rows(rows: List[Dict[str, Any]], *, with_data: bool, with_sigma8_model: bool) -> List[str]:
    lines: List[str] = []
    if with_data:
        lines.append("z\tg\tpred\tobs\tsigma\tpull")
        for row in rows:
            lines.append(
                f"{row['z']:.6g}\t{row['g']:.8g}\t{row['pred']:.8g}\t"
                f"{row['obs']:.8g}\t{row['sigma']:.8g}\t{row['pull']:.8g}"
            )
        return lines

    if with_sigma8_model:
        lines.append("z\tD\tf\tg\tfsigma8_model")
        for row in rows:
            lines.append(
                f"{row['z']:.6g}\t{row['D']:.8g}\t{row['f']:.8g}\t"
                f"{row['g']:.8g}\t{row['fsigma8_model']:.8g}"
            )
        return lines

    lines.append("z\tD\tf\tg")
    for row in rows:
        lines.append(f"{row['z']:.6g}\t{row['D']:.8g}\t{row['f']:.8g}\t{row['g']:.8g}")
    return lines


def _fit_sigma8(rows: List[Dict[str, float]]) -> float:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        w = 1.0 / (row["sigma"] * row["sigma"])
        numerator += row["g"] * row["obs"] * w
        denominator += row["g"] * row["g"] * w
    if not (math.isfinite(denominator) and denominator > 0.0):
        raise ValueError("cannot profile sigma8: non-positive denominator")
    return float(numerator / denominator)


def _compute_rsd_summary(
    *,
    rsd_rows: List[Dict[str, object]],
    rsd_data_path: str,
    ap_mode: str,
    sigma8_mode: str,
    sigma8_0: Optional[float],
    sigma8_fixed: Optional[float],
    fit_sigma8: bool,
    obs_by_z: Mapping[float, Mapping[str, float]],
    history,
    H0_si: float,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "enabled": True,
        "data_path": str(rsd_data_path),
        "n_points": int(len(rsd_rows)),
        "ap_correction_mode": str(ap_mode),
        "sigma8_mode": str(sigma8_mode),
    }
    if not rsd_rows:
        summary["error"] = "no usable RSD points"
        return summary

    model_da_cache: Dict[float, float] = {}
    ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]] = {}

    def _ap_factor(z: float, omega_m_ref: float) -> float:
        if ap_mode == "none":
            return 1.0

        z_key = float(z)
        om_key = float(omega_m_ref)

        if z_key not in model_da_cache:
            h_model = float(history.H(z_key))
            da_model = float(D_A_flat(z=z_key, H_of_z=history.H, n=AP_DA_TRAPZ_N))
            if not (math.isfinite(h_model) and h_model > 0.0 and math.isfinite(da_model) and da_model > 0.0):
                raise ValueError("invalid model H(z) or D_A(z) in AP correction")
            model_da_cache[z_key] = da_model

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
                raise ValueError("invalid reference H(z) or D_A(z) in AP correction")
            ref_hd_cache[ref_key] = (h_ref, da_ref)

        h_model = float(history.H(z_key))
        da_model = float(model_da_cache[z_key])
        h_ref, da_ref = ref_hd_cache[ref_key]
        return float((h_ref * da_ref) / (h_model * da_model))

    try:
        data_y: List[float] = []
        sigmas: List[float] = []
        model_t: List[float] = []
        row_dump: List[Dict[str, Any]] = []

        for idx, row in enumerate(rsd_rows):
            z = float(row["z"])
            y = float(row["fsigma8"])
            sigma = float(row["sigma"])
            om_ref = float(row["omega_m_ref"])
            ref_key = str(row["ref_key"])
            g_val = float(obs_by_z[z]["g"])
            ap_factor = _ap_factor(z, om_ref)
            t_val = float(g_val * ap_factor)

            if not (math.isfinite(t_val) and math.isfinite(y) and math.isfinite(sigma) and sigma > 0.0):
                raise ValueError(f"non-finite RSD row values at index {idx}")

            data_y.append(float(y))
            sigmas.append(float(sigma))
            model_t.append(float(t_val))
            row_dump.append(
                {
                    "z": float(z),
                    "obs": float(y),
                    "sigma": float(sigma),
                    "shape_t": float(t_val),
                    "ap_factor": float(ap_factor),
                    "omega_m_ref": float(om_ref),
                    "ref_key": ref_key,
                }
            )

        profile_sigma8 = bool(sigma8_mode == "nuisance" and (sigma8_fixed is None or fit_sigma8))
        dof = len(data_y) - 1 if profile_sigma8 else len(data_y)

        if profile_sigma8:
            prof = profile_scale_chi2_diag(data_y, model_t, sigmas)
            scale = prof.get("scale_bestfit")
            chi2_min = prof.get("chi2_min")
            if scale is None or chi2_min is None:
                raise ValueError("failed sigma8 analytic profiling for RSD")
            preds = [float(scale * t) for t in model_t]
            pulls = [float((y - p) / s) for y, p, s in zip(data_y, preds, sigmas)]
            chi2_dof = float(chi2_min / float(dof)) if dof > 0 else None

            summary.update(
                {
                    "fit_sigma8": True,
                    "sigma8_0_bestfit": float(scale),
                    "chi2_min": float(chi2_min),
                    "dof": int(dof),
                    "chi2_dof": float(chi2_dof) if chi2_dof is not None else None,
                    "a_num": float(prof.get("a_num") or 0.0),
                    "b_den": float(prof.get("b_den") or 0.0),
                }
            )
        else:
            sigma8_use = float(sigma8_0) if sigma8_0 is not None else float(sigma8_fixed)
            preds = [float(sigma8_use * t) for t in model_t]
            residuals = [float(y - p) for y, p in zip(data_y, preds)]
            chi2 = chi2_diag(residuals, sigmas)
            pulls = [float((y - p) / s) for y, p, s in zip(data_y, preds, sigmas)]
            chi2_dof = float(chi2 / float(dof)) if dof > 0 else None

            summary.update(
                {
                    "fit_sigma8": False,
                    "sigma8_0": float(sigma8_use),
                    "chi2": float(chi2),
                    "dof": int(dof),
                    "chi2_dof": float(chi2_dof) if chi2_dof is not None else None,
                }
            )

        summary["rows"] = [
            {
                **base,
                "pred": float(pred),
                "pull": float(pull),
            }
            for base, pred, pull in zip(row_dump, preds, pulls)
        ]
    except Exception as exc:  # pragma: no cover - exercised by CLI tests
        summary["error"] = str(exc)

    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    if bool(args.toy):
        if args.history is None:
            args.history = "lcdm"
        if args.H0 is None:
            args.H0 = 70.0
        if args.Omega_m is None:
            args.Omega_m = 0.3
        if args.Omega_lambda is None and args.history == "lcdm":
            args.Omega_lambda = 0.7
        if not bool(args.rsd) and args.data is None:
            args.rsd = True

    if args.history is None:
        print("ERROR: --history is required (or use --toy)")
        return 2
    if args.H0 is None:
        print("ERROR: --H0 is required (or use --toy)")
        return 2
    if args.Omega_m is None:
        print("ERROR: --Omega-m is required (or use --toy)")
        return 2

    k_pivot_mpc = float(args.k0_mpc_legacy) if args.k0_mpc_legacy is not None else float(args.k_pivot_mpc)

    transfer_raw = args.transfer_legacy if args.transfer_legacy is not None else args.transfer_model
    try:
        transfer_model = _canonical_transfer_model(transfer_raw)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.history == "gsc_transition":
        if args.p is None or args.z_transition is None:
            print("ERROR: --history gsc_transition requires --p and --z-transition")
            return 1

    try:
        history, H0_si = _build_history(args)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    rsd_rows: List[Dict[str, object]] = []
    rsd_dataset_sha256: Optional[str] = None
    rsd_dataset_id: Optional[str] = None
    rsd_data_path = str(Path(args.rsd_data).expanduser().resolve())
    if args.rsd:
        try:
            rsd_rows = load_fsigma8_csv(rsd_data_path)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        rsd_path_obj = Path(rsd_data_path)
        rsd_dataset_sha256 = _sha256_file(rsd_path_obj)
        rsd_dataset_id = rsd_path_obj.stem

    if args.data is not None:
        try:
            data_rows = _parse_data_csv(Path(args.data).expanduser().resolve())
        except DataParseError as exc:
            print(f"ERROR: {exc}")
            return int(exc.code)
        z_original = [float(row["z"]) for row in data_rows]
        z_targets_solver = sorted({float(z) for z in z_original})
    else:
        data_rows = []
        z_original = list(DEFAULT_Z_GRID)
        z_targets_solver = list(DEFAULT_Z_GRID)

    if args.rsd:
        z_targets_solver = sorted({*z_targets_solver, *[float(row["z"]) for row in rsd_rows]})

    if args.sigma8_mode == "derived_As":
        if args.As is None:
            print("ERROR: --sigma8-mode derived_As requires --As")
            return 2
        if args.sigma8 is not None:
            print("ERROR: --sigma8 must not be provided when --sigma8-mode derived_As")
            return 2
        if args.fit_sigma8 == "1":
            print("ERROR: --fit-sigma8=1 is incompatible with --sigma8-mode derived_As")
            return 2

    fit_sigma8 = False
    if args.sigma8_mode == "nuisance" and args.data is not None:
        if args.sigma8 is not None:
            fit_sigma8 = False
        elif args.fit_sigma8 is None:
            fit_sigma8 = True
        else:
            fit_sigma8 = args.fit_sigma8 == "1"

    if args.sigma8_mode == "nuisance" and args.data is not None and not fit_sigma8 and args.sigma8 is None:
        print("ERROR: fixed-sigma8 mode requires --sigma8 when --fit-sigma8=0")
        return 1

    sigma8_fixed = float(args.sigma8) if args.sigma8 is not None else None
    if sigma8_fixed is not None and not (math.isfinite(sigma8_fixed) and sigma8_fixed > 0.0):
        print("ERROR: --sigma8 must be finite and > 0")
        return 1

    if not (math.isfinite(float(args.Omega_b0)) and float(args.Omega_b0) >= 0.0):
        print("ERROR: --Omega-b0 must be finite and >= 0")
        return 2
    if not (math.isfinite(float(args.Tcmb)) and float(args.Tcmb) > 0.0):
        print("ERROR: --Tcmb must be finite and > 0")
        return 2

    z_start = float(args.z_start)
    n_steps = int(args.n_steps)
    eps_dlnH = float(args.eps_dlnH)

    def E_of_z(z: float) -> float:
        Hz = float(history.H(float(z)))
        if not (math.isfinite(Hz) and Hz > 0.0):
            raise ValueError("non-positive or non-finite H(z)")
        return float(Hz / H0_si)

    try:
        solution = solve_growth_ln_a(
            E_of_z,
            float(args.Omega_m),
            z_start=z_start,
            z_targets=z_targets_solver,
            n_steps=n_steps,
            eps_dlnH=eps_dlnH,
        )
        obs_unique = growth_observables_from_solution(solution, z_targets_solver)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    obs_by_z: Dict[float, Dict[str, float]] = {}
    for i, z in enumerate(obs_unique["z"]):
        obs_by_z[float(z)] = {
            "D": float(obs_unique["D"][i]),
            "f": float(obs_unique["f"][i]),
            "g": float(obs_unique["g"][i]),
        }

    sigma8_0: Optional[float] = None
    sigma8_meta: Dict[str, Any] = {
        "mode": str(args.sigma8_mode),
        "fit_sigma8": bool(fit_sigma8) if args.sigma8_mode == "nuisance" and args.data is not None else False,
        "sigma8_0": None,
        "As": float(args.As) if args.As is not None else None,
        "ns": float(args.ns),
        "k0_mpc": float(k_pivot_mpc),
        "primordial_ns": float(args.ns),
        "primordial_k_pivot_mpc": float(k_pivot_mpc),
        "primordial_amp_param": ("As" if args.sigma8_mode == "derived_As" else "sigma8"),
        "transfer": str(transfer_model),
        "transfer_model": str(transfer_model),
        "transfer_units": "k in 1/Mpc",
        "transfer_model_notes": (
            "Approximation-first transfer backend; EH98 option is no-wiggle and not a Boltzmann solver."
        ),
        "transfer_model_ignored_in_nuisance": bool(args.sigma8_mode == "nuisance"),
        "kmin": float(args.kmin),
        "kmax": float(args.kmax),
        "nk": int(args.nk),
    }

    if args.sigma8_mode == "derived_As":
        try:
            sigma8_0 = sigma8_0_from_As(
                As=float(args.As),
                ns=float(args.ns),
                omega_m0=float(args.Omega_m),
                h=float(args.H0) / 100.0,
                transfer_model=str(transfer_model),
                omega_b0=float(args.Omega_b0),
                Tcmb_K=float(args.Tcmb),
                k_pivot_mpc=float(k_pivot_mpc),
                kmin=float(args.kmin),
                kmax=float(args.kmax),
                nk=int(args.nk),
                E_of_z=E_of_z,
                z_start=float(args.z_start),
                n_steps=int(args.n_steps),
                eps_dlnH=float(args.eps_dlnH),
            )
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2
    else:
        # nuisance mode
        if args.data is None:
            sigma8_0 = sigma8_fixed
        else:
            sigma8_0 = None

    rows: List[Dict[str, Any]] = []
    data_summary: Optional[Dict[str, Any]] = None
    if args.data is None:
        obs_rows = growth_observables_from_solution(solution, z_original)
        for i, z in enumerate(z_original):
            row: Dict[str, Any] = {
                "z": float(z),
                "D": float(obs_rows["D"][i]),
                "f": float(obs_rows["f"][i]),
                "g": float(obs_rows["g"][i]),
            }
            if sigma8_0 is not None:
                row["fsigma8_model"] = float(sigma8_0 * row["g"])
            rows.append(row)
    else:
        merged: List[Dict[str, float]] = []
        for row in data_rows:
            z = float(row["z"])
            g_pack = obs_by_z[z]
            merged.append(
                {
                    "z": z,
                    "obs": float(row["obs"]),
                    "sigma": float(row["sigma"]),
                    "D": float(g_pack["D"]),
                    "f": float(g_pack["f"]),
                    "g": float(g_pack["g"]),
                }
            )

        try:
            if args.sigma8_mode == "derived_As":
                sigma8_use = float(sigma8_0)
            elif fit_sigma8:
                sigma8_use = _fit_sigma8(merged)
            else:
                sigma8_use = float(sigma8_fixed)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2

        chi2 = 0.0
        for row in merged:
            pred = sigma8_use * row["g"]
            pull = (row["obs"] - pred) / row["sigma"]
            chi2 += pull * pull
            rows.append(
                {
                    "z": float(row["z"]),
                    "D": float(row["D"]),
                    "f": float(row["f"]),
                    "g": float(row["g"]),
                    "obs": float(row["obs"]),
                    "sigma": float(row["sigma"]),
                    "pred": float(pred),
                    "pull": float(pull),
                }
            )

        dof = len(merged) - 1 if (args.sigma8_mode == "nuisance" and fit_sigma8) else len(merged)
        chi2_dof = (chi2 / float(dof)) if dof > 0 else None
        data_summary = {
            "n_points": int(len(merged)),
            "fit_sigma8": bool(args.sigma8_mode == "nuisance" and fit_sigma8),
            "sigma8": float(sigma8_use),
            "chi2": float(chi2),
            "dof": int(dof),
            "chi2_dof": float(chi2_dof) if chi2_dof is not None else None,
        }
        sigma8_0 = float(sigma8_use)

    sigma8_meta["sigma8_0"] = float(sigma8_0) if sigma8_0 is not None else None

    payload: Dict[str, Any] = {
        "tool": TOOL_ID,
        "history": _history_payload(args),
        "integration": {
            "z_start": float(z_start),
            "n_steps": int(n_steps),
            "eps_dlnH": float(eps_dlnH),
        },
        "sigma8": sigma8_meta,
        "primordial": {
            "amp_param": str(sigma8_meta.get("primordial_amp_param")),
            "ns": float(sigma8_meta.get("primordial_ns")),
            "k_pivot_mpc": float(sigma8_meta.get("primordial_k_pivot_mpc")),
        },
        "transfer_model": str(transfer_model),
        "transfer_model_notes": (
            "Approximation-only transfer backend (BBKS or EH98 no-wiggle), not CAMB/CLASS."
        ),
        "data": data_summary,
        "rows": rows,
    }
    if rsd_dataset_id is not None:
        payload["rsd_dataset_id"] = str(rsd_dataset_id)
    if rsd_dataset_sha256 is not None:
        payload["rsd_dataset_sha256"] = str(rsd_dataset_sha256)

    rsd_summary: Optional[Dict[str, Any]] = None
    if args.rsd:
        rsd_summary = _compute_rsd_summary(
            rsd_rows=rsd_rows,
            rsd_data_path=rsd_data_path,
            ap_mode=str(args.rsd_ap_correction),
            sigma8_mode=str(args.sigma8_mode),
            sigma8_0=sigma8_0,
            sigma8_fixed=sigma8_fixed,
            fit_sigma8=bool(fit_sigma8),
            obs_by_z=obs_by_z,
            history=history,
            H0_si=float(H0_si),
        )
        if rsd_dataset_id is not None:
            rsd_summary["dataset_id"] = str(rsd_dataset_id)
        if rsd_dataset_sha256 is not None:
            rsd_summary["dataset_sha256"] = str(rsd_dataset_sha256)
        payload["rsd_fsigma8"] = rsd_summary

    if args.format == "json":
        sys.stdout.write(_as_json(payload))
    else:
        print("== Phase-2 Structure fσ8 Diagnostic ==")
        hist = payload["history"]
        print(
            f"history={hist['type']} H0={hist['H0_km_s_Mpc']} Omega_m={hist['Omega_m']} "
            f"Omega_lambda={hist['Omega_lambda']}"
        )
        if hist["type"] == "gsc_transition":
            print(f"p={hist['p']} z_transition={hist['z_transition']}")
        print(
            f"integration: z_start={payload['integration']['z_start']} "
            f"n_steps={payload['integration']['n_steps']} eps_dlnH={payload['integration']['eps_dlnH']}"
        )
        print(
            f"sigma8_mode={sigma8_meta['mode']} sigma8_0="
            f"{sigma8_meta['sigma8_0'] if sigma8_meta['sigma8_0'] is not None else 'NA'}"
        )
        if sigma8_meta["mode"] == "derived_As":
            print(
                f"derived_As: As={sigma8_meta['As']} ns={sigma8_meta['primordial_ns']} "
                f"k_pivot={sigma8_meta['primordial_k_pivot_mpc']} transfer={sigma8_meta['transfer_model']} "
                f"kmin={sigma8_meta['kmin']} kmax={sigma8_meta['kmax']} nk={sigma8_meta['nk']}"
            )
        elif sigma8_meta.get("transfer_model_ignored_in_nuisance"):
            print(
                f"nuisance mode: transfer_model={sigma8_meta['transfer_model']} is recorded only "
                "and not used in sigma8 fitting."
            )

        if data_summary is None:
            print(f"n_points={len(rows)} (no data mode)")
        else:
            print(
                f"n_points={data_summary['n_points']} fit_sigma8={int(data_summary['fit_sigma8'])} "
                f"sigma8={data_summary['sigma8']:.8g} chi2={data_summary['chi2']:.8g} "
                f"dof={data_summary['dof']} chi2_dof={data_summary['chi2_dof'] if data_summary['chi2_dof'] is not None else 'NA'}"
            )

        print("== Rows ==")
        for line in _text_rows(
            rows,
            with_data=(data_summary is not None),
            with_sigma8_model=(data_summary is None and sigma8_meta["sigma8_0"] is not None),
        ):
            print(line)

        if rsd_summary is not None:
            print("== RSD fσ8 (diagnostic) ==")
            print(f"n_points={rsd_summary.get('n_points')} ap_correction={rsd_summary.get('ap_correction_mode')}")
            print(f"sigma8_mode={rsd_summary.get('sigma8_mode')} fit_sigma8={int(bool(rsd_summary.get('fit_sigma8', False)))}")
            if rsd_summary.get("error"):
                print(f"error={rsd_summary['error']}")
            elif rsd_summary.get("fit_sigma8"):
                print(
                    f"sigma8_0_bestfit={rsd_summary.get('sigma8_0_bestfit')} "
                    f"chi2_min={rsd_summary.get('chi2_min')} dof={rsd_summary.get('dof')} "
                    f"chi2_dof={rsd_summary.get('chi2_dof')}"
                )
            else:
                print(
                    f"sigma8_0={rsd_summary.get('sigma8_0')} chi2={rsd_summary.get('chi2')} "
                    f"dof={rsd_summary.get('dof')} chi2_dof={rsd_summary.get('chi2_dof')}"
                )

    if args.json_out is not None:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_as_json(payload), encoding="utf-8")

    if args.emit_snippets is not None:
        _emit_snippets(outdir=Path(args.emit_snippets).expanduser().resolve(), payload=payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
