#!/usr/bin/env python3
"""Deterministic SigmaTensor-v1 drift-sign diagnostic (Phase-4 M145 / Task 4A.-1)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
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


TOOL = "phase4_sigmatensor_drift_sign_diagnostic"
TOOL_VERSION = "m145-v1"
SCHEMA = "phase4_sigmatensor_drift_sign_diagnostic_report_v1"
FAIL_MARKER = "PHASE4_SIGMATENSOR_DRIFT_SIGN_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
REQUIRED_EVAL_Z: Tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)


class UsageError(Exception):
    """Invalid CLI usage."""


class DiagnosticError(Exception):
    """Physics/precondition failure."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _fmt_e(value: float) -> str:
    return f"{float(value):.12e}"


def _stable_key(value: float) -> str:
    return _fmt_e(float(value))


def _to_iso_utc(epoch_seconds: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    except Exception as exc:
        raise UsageError("--created-utc must be a valid integer epoch-seconds value") from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_csv_floats(text: str, *, name: str) -> List[float]:
    out: List[float] = []
    for chunk in str(text).split(","):
        token = chunk.strip()
        if not token:
            continue
        try:
            value = float(token)
        except Exception as exc:
            raise UsageError(f"{name} must be a comma-separated float list") from exc
        if not math.isfinite(value):
            raise UsageError(f"{name} contains non-finite value")
        out.append(float(value))
    if not out:
        raise UsageError(f"{name} produced empty list")
    return out


def _dedupe_sorted(values: Iterable[float]) -> List[float]:
    uniq = sorted({float(v) for v in values})
    return [float(v) for v in uniq]


def _build_linear_grid(vmin: float, vmax: float, n: int) -> List[float]:
    if int(n) < 1:
        raise UsageError("grid size must be >= 1")
    if not (math.isfinite(vmin) and math.isfinite(vmax)):
        raise UsageError("grid bounds must be finite")
    if float(vmax) < float(vmin):
        raise UsageError("grid max must be >= min")
    if int(n) == 1:
        return [float(vmin)]
    step = (float(vmax) - float(vmin)) / float(int(n) - 1)
    return [float(vmin + i * step) for i in range(int(n))]


def _render_text(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    rows = payload.get("lambda_summaries") if isinstance(payload.get("lambda_summaries"), list) else []

    lines: List[str] = []
    lines.append("SigmaTensor drift-sign diagnostic")
    lines.append(f"schema={payload.get('schema')}")
    lines.append(f"status={payload.get('status')}")
    lines.append(
        "summary="
        f"positive_anywhere_in_2_5={bool(summary.get('drift_positive_anywhere_in_2_5'))} "
        f"positive_all_eval_points={bool(summary.get('drift_positive_all_eval_points'))} "
        f"negative_all_eval_points_all_lambda={bool(summary.get('drift_negative_all_eval_points_all_lambda'))}"
    )
    lines.append("lambda,dz_dt0(z=2),dz_dt0(z=3),dz_dt0(z=4),dz_dt0(z=5),positive_any_eval")
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        eval_map = row.get("eval_points") if isinstance(row.get("eval_points"), Mapping) else {}
        lines.append(
            ",".join(
                [
                    f"{float(row.get('lambda')):.6g}",
                    f"{float(eval_map.get(_stable_key(2.0), {}).get('dz_dt0_si', float('nan'))):.12g}" if isinstance(eval_map.get(_stable_key(2.0)), Mapping) else "nan",
                    f"{float(eval_map.get(_stable_key(3.0), {}).get('dz_dt0_si', float('nan'))):.12g}" if isinstance(eval_map.get(_stable_key(3.0)), Mapping) else "nan",
                    f"{float(eval_map.get(_stable_key(4.0), {}).get('dz_dt0_si', float('nan'))):.12g}" if isinstance(eval_map.get(_stable_key(4.0)), Mapping) else "nan",
                    f"{float(eval_map.get(_stable_key(5.0), {}).get('dz_dt0_si', float('nan'))):.12g}" if isinstance(eval_map.get(_stable_key(5.0)), Mapping) else "nan",
                    "1" if bool(row.get("drift_positive_any_eval")) else "0",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _render_markdown(payload: Mapping[str, Any]) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), Mapping) else {}
    grids = payload.get("grids") if isinstance(payload.get("grids"), Mapping) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    rows = payload.get("lambda_summaries") if isinstance(payload.get("lambda_summaries"), list) else []

    lines: List[str] = []
    lines.append("# SigmaTensor Drift Sign Diagnostic (Task 4A.-1)")
    lines.append("")
    lines.append("Deterministic, reviewer-facing drift-sign diagnostic for SigmaTensor-v1.")
    lines.append("Scope: background-only diagnostic (no perturbation/Boltzmann closure claims).")
    lines.append("")
    lines.append("## Parameters")
    lines.append(f"- H0_km_s_Mpc: `{float(params.get('H0_km_s_Mpc')):.12g}`")
    lines.append(f"- Omega_m0: `{float(params.get('Omega_m0')):.12g}`")
    lines.append(f"- w_phi0: `{float(params.get('w_phi0')):.12g}`")
    lines.append(
        f"- lambda grid: `[{float(params.get('lambda_min')):.12g}, {float(params.get('lambda_max')):.12g}]` with `n_lambda={int(params.get('n_lambda'))}`"
    )
    lines.append(f"- eval z points: `{', '.join(f'{float(z):.6g}' for z in grids.get('eval_z_values', []))}`")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- drift_positive_anywhere_in_2_5: `{bool(summary.get('drift_positive_anywhere_in_2_5'))}`")
    lines.append(f"- drift_positive_all_eval_points: `{bool(summary.get('drift_positive_all_eval_points'))}`")
    lines.append(
        f"- drift_negative_all_eval_points_all_lambda: `{bool(summary.get('drift_negative_all_eval_points_all_lambda'))}`"
    )
    lines.append(
        f"- baseline_lambda0_drift_at_z3_si: `{float(summary.get('baseline_lambda0_drift_at_z3_si', float('nan'))):.12e}`"
    )
    lines.append("")
    lines.append("## Drift table at required evaluation points")
    lines.append("")
    lines.append("| lambda | dz_dt0(z=2) [1/s] | dz_dt0(z=3) [1/s] | dz_dt0(z=4) [1/s] | dz_dt0(z=5) [1/s] | any positive? |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        eval_map = row.get("eval_points") if isinstance(row.get("eval_points"), Mapping) else {}

        def _v(z: float) -> str:
            value = eval_map.get(_stable_key(z))
            if isinstance(value, Mapping):
                return f"{float(value.get('dz_dt0_si')):.12e}"
            return "nan"

        lines.append(
            "| "
            + f"{float(row.get('lambda')):.6g} | {_v(2.0)} | {_v(3.0)} | {_v(4.0)} | {_v(5.0)} | {'yes' if bool(row.get('drift_positive_any_eval')) else 'no'} |"
        )
    lines.append("")
    lines.append("## Reproduce")
    lines.append("```bash")
    lines.append(
        "python3 v11.0.0/scripts/phase4_sigmatensor_drift_sign_diagnostic.py "
        "--outdir <outdir> --format text"
    )
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _plot_if_requested(
    *,
    emit_plot: bool,
    outdir: Path,
    z_values: Sequence[float],
    lambda_rows: Sequence[Mapping[str, Any]],
) -> Tuple[Optional[str], str]:
    if not emit_plot:
        return None, "disabled"

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None, "unavailable_matplotlib"

    if not z_values or not lambda_rows:
        return None, "unavailable_no_data"

    # Deterministic representative subset: first, mid, last rows.
    indices = sorted({0, len(lambda_rows) // 2, len(lambda_rows) - 1})
    selected = [lambda_rows[i] for i in indices]

    fig, ax = plt.subplots(figsize=(7.0, 4.0), dpi=120)
    for row in selected:
        drift_rows = row.get("drift_rows") if isinstance(row.get("drift_rows"), list) else []
        z = [float(r.get("z")) for r in drift_rows if isinstance(r, Mapping)]
        y = [float(r.get("dz_dt0_si")) for r in drift_rows if isinstance(r, Mapping)]
        ax.plot(z, y, linewidth=1.7, label=f"lambda={float(row.get('lambda')):.3g}")

    ax.axhline(0.0, color="black", linewidth=1.0, linestyle="--")
    ax.set_xlabel("z")
    ax.set_ylabel("dz/dt0 [1/s]")
    ax.set_title("SigmaTensor drift sign diagnostic")
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()

    plot_path = outdir / "DRIFT_SIGN_DIAGNOSTIC.svg"
    fig.savefig(plot_path, format="svg", metadata={"Date": None})
    plt.close(fig)
    return plot_path.name, "ok"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic SigmaTensor drift-sign diagnostic (Task 4A.-1).")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--format", choices=("json", "text"), default="text")
    ap.add_argument(
        "--created-utc",
        type=int,
        default=DEFAULT_CREATED_UTC_EPOCH,
        help="UTC epoch-seconds marker for deterministic outputs (default: 946684800).",
    )

    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--w0", type=float, default=-1.0)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)

    ap.add_argument("--lambda-min", dest="lambda_min", type=float, default=0.0)
    ap.add_argument("--lambda-max", dest="lambda_max", type=float, default=2.0)
    ap.add_argument("--n-lambda", dest="n_lambda", type=int, default=9)

    ap.add_argument("--z-grid-csv", dest="z_grid_csv", type=str, default=None)
    ap.add_argument("--z-min", dest="z_min", type=float, default=2.0)
    ap.add_argument("--z-max", dest="z_max", type=float, default=5.0)
    ap.add_argument("--n-z", dest="n_z", type=int, default=7)
    ap.add_argument("--eval-z-csv", dest="eval_z_csv", type=str, default="2,3,4,5")
    ap.add_argument("--n-steps-bg", dest="n_steps_bg", type=int, default=4096)

    ap.add_argument("--emit-plot", dest="emit_plot", type=int, choices=(0, 1), default=0)
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)

        created_epoch = int(args.created_utc)
        created_utc = _to_iso_utc(created_epoch)

        H0_km = float(args.H0_km_s_Mpc)
        H0_si = float(H0_to_SI(H0_km))
        omega_m0 = float(args.Omega_m)
        w0 = float(args.w0)
        Tcmb_K = float(args.Tcmb_K)
        N_eff = float(args.N_eff)
        omega_r0_override = None if args.Omega_r0_override is None else float(args.Omega_r0_override)

        if not (math.isfinite(H0_km) and H0_km > 0.0):
            raise UsageError("--H0-km-s-Mpc must be finite and > 0")
        if not (math.isfinite(omega_m0) and omega_m0 >= 0.0):
            raise UsageError("--Omega-m must be finite and >= 0")
        if not (math.isfinite(w0) and -1.0 <= w0 < 1.0):
            raise UsageError("--w0 must be finite and in [-1, 1)")
        if not (math.isfinite(Tcmb_K) and Tcmb_K > 0.0):
            raise UsageError("--Tcmb-K must be finite and > 0")
        if not (math.isfinite(N_eff) and N_eff >= 0.0):
            raise UsageError("--N-eff must be finite and >= 0")
        if omega_r0_override is not None and not (math.isfinite(omega_r0_override) and omega_r0_override >= 0.0):
            raise UsageError("--Omega-r0-override must be finite and >= 0")

        if args.z_grid_csv:
            base_z = _parse_csv_floats(args.z_grid_csv, name="--z-grid-csv")
        else:
            base_z = _build_linear_grid(float(args.z_min), float(args.z_max), int(args.n_z))

        eval_z = _parse_csv_floats(args.eval_z_csv, name="--eval-z-csv")
        eval_z = _dedupe_sorted(list(eval_z) + list(REQUIRED_EVAL_Z))

        z_grid = _dedupe_sorted(list(base_z) + list(eval_z))
        if any((not math.isfinite(z) or z < 0.0) for z in z_grid):
            raise UsageError("z grid values must be finite and >= 0")
        if int(args.n_steps_bg) < 2:
            raise UsageError("--n-steps-bg must be >= 2")

        lambda_values = _build_linear_grid(float(args.lambda_min), float(args.lambda_max), int(args.n_lambda))

        z_max_bg = float(max(z_grid))
        z_key_to_value = {_stable_key(float(z)): float(z) for z in z_grid}
        eval_keys = [_stable_key(float(z)) for z in eval_z]

        lambda_summaries: List[Dict[str, Any]] = []
        any_positive_any_eval = False
        any_positive_all_eval = False
        all_negative_all_eval_all_lambda = True
        lambda_with_any_positive_eval: List[float] = []
        lambda_with_all_positive_eval: List[float] = []

        baseline_lambda0_drift_at_z3_si: Optional[float] = None
        baseline_lambda0_distance = float("inf")

        for lambda_value in lambda_values:
            params = SigmaTensorV1Params(
                H0_si=H0_si,
                Omega_m0=omega_m0,
                w_phi0=w0,
                lambda_=float(lambda_value),
                Tcmb_K=Tcmb_K,
                N_eff=N_eff,
                Omega_r0_override=omega_r0_override,
                sign_u0=int(args.sign_u0),
            )

            try:
                bg = solve_sigmatensor_v1_background(params, z_max=z_max_bg, n_steps=int(args.n_steps_bg))
            except ValueError as exc:
                raise DiagnosticError(str(exc)) from exc

            hist = SigmaTensorV1History(bg)
            drift_rows: List[Dict[str, Any]] = []
            eval_points: Dict[str, Dict[str, Any]] = {}

            for z in z_grid:
                H_si = float(hist.H(float(z)))
                dz_dt0_si = float(H0_si * (1.0 + float(z)) - H_si)
                sign = 1 if dz_dt0_si > 0.0 else (-1 if dz_dt0_si < 0.0 else 0)
                row = {
                    "z": float(z),
                    "H_si": float(H_si),
                    "dz_dt0_si": float(dz_dt0_si),
                    "drift_sign": int(sign),
                }
                drift_rows.append(row)
                key = _stable_key(float(z))
                if key in eval_keys:
                    eval_points[key] = row

            eval_signs = [int(eval_points[k]["drift_sign"]) for k in eval_keys]
            drift_positive_any_eval = any(s > 0 for s in eval_signs)
            drift_positive_all_eval = all(s > 0 for s in eval_signs)
            drift_negative_all_eval = all(s < 0 for s in eval_signs)

            if drift_positive_any_eval:
                any_positive_any_eval = True
                lambda_with_any_positive_eval.append(float(lambda_value))
            if drift_positive_all_eval:
                any_positive_all_eval = True
                lambda_with_all_positive_eval.append(float(lambda_value))
            if not drift_negative_all_eval:
                all_negative_all_eval_all_lambda = False

            if _stable_key(3.0) in eval_points:
                dist = abs(float(lambda_value) - 0.0)
                if dist < baseline_lambda0_distance:
                    baseline_lambda0_distance = dist
                    baseline_lambda0_drift_at_z3_si = float(eval_points[_stable_key(3.0)]["dz_dt0_si"])

            lambda_summaries.append(
                {
                    "lambda": float(lambda_value),
                    "drift_rows": drift_rows,
                    "eval_points": {k: eval_points[k] for k in eval_keys},
                    "drift_positive_any_eval": bool(drift_positive_any_eval),
                    "drift_positive_all_eval": bool(drift_positive_all_eval),
                    "drift_negative_all_eval": bool(drift_negative_all_eval),
                }
            )

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        plot_rel, plot_status = _plot_if_requested(
            emit_plot=bool(int(args.emit_plot)),
            outdir=outdir,
            z_values=z_grid,
            lambda_rows=lambda_summaries,
        )

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "created_utc": str(created_utc),
            "created_utc_epoch": int(created_epoch),
            "python_version": str(sys.version.split()[0]),
            "platform": str(platform.system()),
            "repo_version_dir": "v11.0.0",
            "paths_redacted": True,
            "status": "ok",
            "params": {
                "H0_km_s_Mpc": float(H0_km),
                "H0_si": float(H0_si),
                "Omega_m0": float(omega_m0),
                "w_phi0": float(w0),
                "Tcmb_K": float(Tcmb_K),
                "N_eff": float(N_eff),
                "Omega_r0_override": None if omega_r0_override is None else float(omega_r0_override),
                "sign_u0": int(args.sign_u0),
                "lambda_min": float(args.lambda_min),
                "lambda_max": float(args.lambda_max),
                "n_lambda": int(args.n_lambda),
                "n_steps_bg": int(args.n_steps_bg),
                "z_grid_mode": "csv" if args.z_grid_csv else "interval",
                "z_grid_csv": None if args.z_grid_csv is None else str(args.z_grid_csv),
            },
            "grids": {
                "lambda_values": [float(v) for v in lambda_values],
                "z_values": [float(v) for v in z_grid],
                "eval_z_values": [float(v) for v in eval_z],
                "required_eval_z": [float(v) for v in REQUIRED_EVAL_Z],
            },
            "summary": {
                "drift_positive_anywhere_in_2_5": bool(any_positive_any_eval),
                "drift_positive_all_eval_points": bool(any_positive_all_eval),
                "drift_negative_all_eval_points_all_lambda": bool(all_negative_all_eval_all_lambda),
                "lambda_with_any_positive_eval": [float(v) for v in lambda_with_any_positive_eval],
                "lambda_with_all_positive_eval": [float(v) for v in lambda_with_all_positive_eval],
                "baseline_lambda0_drift_at_z3_si": None
                if baseline_lambda0_drift_at_z3_si is None
                else float(baseline_lambda0_drift_at_z3_si),
            },
            "lambda_summaries": lambda_summaries,
            "artifacts": {
                "json": "DRIFT_SIGN_DIAGNOSTIC.json",
                "markdown": "DRIFT_SIGN_DIAGNOSTIC.md",
                "plot": plot_rel,
                "plot_status": plot_status,
            },
        }

        json_path = outdir / "DRIFT_SIGN_DIAGNOSTIC.json"
        md_path = outdir / "DRIFT_SIGN_DIAGNOSTIC.md"

        json_text = _json_pretty(payload)
        md_text = _render_markdown(payload)
        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")

    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except DiagnosticError as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if str(args.format) == "json":
        sys.stdout.write(json_text)
    else:
        sys.stdout.write(_render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
