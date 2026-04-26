#!/usr/bin/env python3
"""Phase-2 structure-formation bridge report (diagnostic-only, stdlib-only)."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from _outdir import resolve_outdir

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import FlatLambdaCDMHistory, H0_to_SI  # noqa: E402
from gsc.structure.growth_factor import fsigma8_from_D_f, solve_growth_D_f  # noqa: E402
from gsc.structure.transfer_bbks import (  # noqa: E402
    sample_k_grid,
    shape_parameter_sugiyama,
    transfer_bbks_many,
)

SCHEMA_ID = "phase2_structure_report_v1"


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _parse_float_csv(text: str, *, name: str) -> List[float]:
    raw = str(text).strip()
    if not raw:
        raise SystemExit(f"{name} must be a non-empty comma-separated list")
    out: List[float] = []
    for token in raw.split(","):
        value = _finite_float(token.strip())
        if value is None:
            raise SystemExit(f"{name} contains non-finite value: {token!r}")
        out.append(float(value))
    return out


def _parse_z_eval(text: str) -> List[float]:
    z_vals = _parse_float_csv(text, name="--z-eval")
    out = sorted(set(float(z) for z in z_vals))
    if not out:
        raise SystemExit("--z-eval must provide at least one z")
    for z in out:
        if z < 0.0:
            raise SystemExit("--z-eval values must be >= 0")
    return out


def _parse_k_points(args: argparse.Namespace) -> List[float]:
    if args.k_sample and args.k_grid:
        raise SystemExit("use either --k-sample or --k-grid, not both")

    if args.k_grid:
        raw = [item.strip() for item in str(args.k_grid).split(",")]
        if len(raw) != 3:
            raise SystemExit("--k-grid expects 'kmin,kmax,n'")
        kmin = _finite_float(raw[0])
        kmax = _finite_float(raw[1])
        n = _finite_float(raw[2])
        if kmin is None or kmax is None or n is None:
            raise SystemExit("--k-grid contains non-finite values")
        if int(n) != float(n):
            raise SystemExit("--k-grid third value n must be an integer")
        return sample_k_grid(kmin=float(kmin), kmax=float(kmax), n=int(n))

    raw_points = _parse_float_csv(args.k_sample, name="--k-sample")
    out = sorted(set(float(k) for k in raw_points))
    if not out:
        raise SystemExit("--k-sample must provide at least one k value")
    for k in out:
        if not (k > 0.0):
            raise SystemExit("--k-sample values must be > 0")
    return out


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bestfit_extract(payload: Mapping[str, Any], keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        value = _finite_float(payload.get(key))
        if value is not None:
            return float(value)
    best = _mapping(payload.get("best"))
    params = _mapping(best.get("params"))
    for key in keys:
        value = _finite_float(params.get(key))
        if value is not None:
            return float(value)
    return None


def _extract_background_from_bestfit(path: Path, omega_b_default: float) -> Dict[str, float]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"failed to read --bestfit-json: {exc}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in --bestfit-json: {exc}")

    if not isinstance(payload, Mapping):
        raise SystemExit("--bestfit-json must contain a JSON object")

    omega_m0 = _bestfit_extract(payload, ("Omega_m0", "Omega_m", "omega_m0", "omega_m"))
    if omega_m0 is None:
        raise SystemExit("--bestfit-json missing Omega_m0/Omega_m (top-level or best.params)")

    h = _bestfit_extract(payload, ("h", "h0"))
    if h is None:
        H0 = _bestfit_extract(payload, ("H0", "H0_km_s_Mpc", "hubble", "hubble_km_s_Mpc"))
        if H0 is not None:
            h = float(H0) / 100.0

    if h is None:
        raise SystemExit("--bestfit-json missing h or H0 (top-level or best.params)")

    omega_b0 = _bestfit_extract(payload, ("Omega_b0", "Omega_b", "omega_b0", "omega_b"))
    if omega_b0 is None:
        omega_b0 = float(omega_b_default)

    return {
        "Omega_m0": float(omega_m0),
        "Omega_b0": float(omega_b0),
        "h": float(h),
    }


def _validate_background(omega_m0: float, omega_b0: float, h: float) -> None:
    if not (omega_m0 > 0.0):
        raise SystemExit("Omega_m0 must be > 0")
    if not (0.0 <= omega_b0 <= omega_m0):
        raise SystemExit("Omega_b0 must satisfy 0 <= Omega_b0 <= Omega_m0")
    if not (0.0 < h <= 2.0):
        raise SystemExit("h must satisfy 0 < h <= 2")


def _write_text_report(path: Path, payload: Mapping[str, Any]) -> None:
    background = _mapping(payload.get("background"))
    transfer = _mapping(payload.get("transfer"))
    growth = _mapping(payload.get("growth"))

    lines: List[str] = []
    lines.append("== Structure Formation Bridge Report ==")
    lines.append(f"schema={payload.get('schema')}")
    lines.append("== Background ==")
    lines.append(f"mode={background.get('mode')}")
    lines.append(f"Omega_m0={background.get('Omega_m0')}")
    lines.append(f"Omega_b0={background.get('Omega_b0')}")
    lines.append(f"h={background.get('h')}")
    lines.append(f"H0_km_s_Mpc={background.get('H0_km_s_Mpc')}")
    lines.append(f"Tcmb_K={background.get('Tcmb_K')}")

    lines.append("== Transfer (BBKS) ==")
    lines.append(f"Gamma_eff={transfer.get('Gamma_eff_sugiyama')}")
    for row in transfer.get("samples", []):
        if not isinstance(row, Mapping):
            continue
        lines.append(f"k_Mpc^-1={row.get('k_Mpc_inv')} T_k={row.get('T_k')}")

    lines.append("== Growth (GR baseline) ==")
    z_vals = growth.get("z", [])
    d_vals = growth.get("D", [])
    f_vals = growth.get("f", [])
    fs8_vals = growth.get("fsigma8", None)
    for idx, z in enumerate(z_vals if isinstance(z_vals, list) else []):
        d = d_vals[idx] if isinstance(d_vals, list) and idx < len(d_vals) else None
        f = f_vals[idx] if isinstance(f_vals, list) and idx < len(f_vals) else None
        if isinstance(fs8_vals, list) and idx < len(fs8_vals):
            lines.append(f"z={z} D={d} f={f} fsigma8={fs8_vals[idx]}")
        else:
            lines.append(f"z={z} D={d} f={f}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Phase-2 structure formation bridge report (diagnostic-only).")
    ap.add_argument("--outdir", "--out-dir", dest="outdir", type=Path, default=None)

    ap.add_argument(
        "--background",
        choices=("lcdm_params", "from_bestfit_json"),
        default="lcdm_params",
        help="Background source for structure bridge diagnostics.",
    )
    ap.add_argument("--bestfit-json", type=Path, default=None)
    ap.add_argument("--Omega_m0", type=float, default=0.315)
    ap.add_argument("--Omega_b0", type=float, default=0.049)
    ap.add_argument("--h", type=float, default=0.674)
    ap.add_argument("--Tcmb", type=float, default=2.7255)

    ap.add_argument("--z-eval", default="0,0.5,1,2,5")
    ap.add_argument("--z-init", type=float, default=100.0)
    ap.add_argument("--n-steps", type=int, default=4000)
    ap.add_argument("--sigma8-0", type=float, default=None)

    ap.add_argument("--k-sample", default="1e-4,1e-3,1e-2,1e-1,1")
    ap.add_argument("--k-grid", default=None)

    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    if args.background == "from_bestfit_json":
        if args.bestfit_json is None:
            raise SystemExit("--background from_bestfit_json requires --bestfit-json")
        bg = _extract_background_from_bestfit(Path(args.bestfit_json).expanduser().resolve(), float(args.Omega_b0))
    else:
        bg = {
            "Omega_m0": float(args.Omega_m0),
            "Omega_b0": float(args.Omega_b0),
            "h": float(args.h),
        }

    omega_m0 = float(bg["Omega_m0"])
    omega_b0 = float(bg["Omega_b0"])
    h = float(bg["h"])
    Tcmb_K = float(args.Tcmb)

    _validate_background(omega_m0, omega_b0, h)
    if not (Tcmb_K > 0.0 and math.isfinite(Tcmb_K)):
        raise SystemExit("Tcmb must be finite and > 0")

    z_eval = _parse_z_eval(args.z_eval)
    k_points = _parse_k_points(args)

    H0_km_s_Mpc = 100.0 * h
    H0_si = H0_to_SI(H0_km_s_Mpc)
    Omega_lambda = max(0.0, 1.0 - omega_m0)
    history = FlatLambdaCDMHistory(H0=H0_si, Omega_m=omega_m0, Omega_Lambda=Omega_lambda)

    growth = solve_growth_D_f(
        z_eval,
        H_of_z=history.H,
        Omega_m0=omega_m0,
        z_init=float(args.z_init),
        n_steps=int(args.n_steps),
    )

    fs8: Optional[List[float]] = None
    if args.sigma8_0 is not None:
        fs8 = fsigma8_from_D_f(growth["z"], growth["D"], growth["f"], float(args.sigma8_0))

    gamma_eff = shape_parameter_sugiyama(omega_m0, omega_b0, h)
    T_vals = transfer_bbks_many(
        k_points,
        Omega_m0=omega_m0,
        Omega_b0=omega_b0,
        h=h,
        Tcmb_K=Tcmb_K,
    )

    out_root = resolve_outdir(args.outdir, v101_dir=ROOT)
    out_root.mkdir(parents=True, exist_ok=True)
    out_json = (out_root / "structure_report.json").resolve()
    out_txt = (out_root / "structure_report.txt").resolve()

    payload: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "background": {
            "mode": str(args.background),
            "source_bestfit_json": str(Path(args.bestfit_json).expanduser().resolve()) if args.bestfit_json is not None else None,
            "Omega_m0": float(omega_m0),
            "Omega_b0": float(omega_b0),
            "h": float(h),
            "H0_km_s_Mpc": float(H0_km_s_Mpc),
            "Tcmb_K": float(Tcmb_K),
            "Omega_lambda_assumed": float(Omega_lambda),
        },
        "inputs": {
            "z_eval": [float(z) for z in z_eval],
            "z_init": float(args.z_init),
            "n_steps": int(args.n_steps),
            "k_points_Mpc_inv": [float(k) for k in k_points],
            "sigma8_0": float(args.sigma8_0) if args.sigma8_0 is not None else None,
        },
        "transfer": {
            "model": "bbks_sugiyama_v1",
            "Gamma_eff_sugiyama": float(gamma_eff),
            "samples": [
                {"k_Mpc_inv": float(k), "T_k": float(t)}
                for k, t in zip(k_points, T_vals)
            ],
        },
        "growth": {
            "method": growth.get("method"),
            "z_init": growth.get("z_init"),
            "n_steps": growth.get("n_steps"),
            "z": [float(v) for v in growth.get("z", [])],
            "D": [float(v) for v in growth.get("D", [])],
            "f": [float(v) for v in growth.get("f", [])],
            "fsigma8": fs8,
        },
    }

    out_json.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_text_report(out_txt, payload)

    print(f"WROTE {out_json}")
    print(f"WROTE {out_txt}")
    z0 = float(payload["growth"]["z"][0]) if payload["growth"]["z"] else float("nan")
    d0 = float(payload["growth"]["D"][0]) if payload["growth"]["D"] else float("nan")
    print(
        "summary: "
        f"Gamma_eff={gamma_eff:.8g}, "
        f"D(z={z0:.6g})={d0:.6g}, "
        f"n_z={len(payload['growth']['z'])}, n_k={len(payload['transfer']['samples'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
