#!/usr/bin/env python3
"""Generate compressed-CMB shift parameters as a reproducible JSON artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, Sequence


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from _outdir import resolve_outdir, resolve_path_under_outdir  # noqa: E402
from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time.cmb_shift_params import compute_lcdm_shift_params  # noqa: E402


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="early_time_cmb_shift_params",
        description="Phase 2 M1 scaffold: compute LCDM compressed-CMB shift parameters.",
    )
    ap.add_argument("--model", choices=("lcdm",), default="lcdm")
    ap.add_argument("--H0", type=float, default=67.4, help="Hubble constant in km/s/Mpc.")
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)
    ap.add_argument("--z-star", type=float, default=None, help="Optional fixed z* override.")
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="outdir",
        type=Path,
        default=None,
        help="Output root (CLI > GSC_OUTDIR > v11.0.0/artifacts/release).",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("early_time/cmb_shift_params.json"),
        help="Output JSON path (relative paths are resolved under OUTDIR).",
    )
    ap.add_argument("--priors-csv", type=Path, default=None, help="Optional compressed-CMB priors CSV.")
    ap.add_argument("--cov", type=Path, default=None, help="Optional covariance for --priors-csv.")
    args = ap.parse_args(argv)

    out_root = resolve_outdir(args.outdir, v101_dir=V101_DIR)
    out_path = resolve_path_under_outdir(args.out, out_root=out_root)
    if out_path is None:  # pragma: no cover - argparse default guarantees a path
        raise SystemExit("ERROR: output path is not set")

    print(f"[info] OUTDIR={out_root}")
    print(f"[info] OUTPUT={out_path}")

    try:
        predicted = compute_lcdm_shift_params(
            H0_km_s_Mpc=float(args.H0),
            Omega_m=float(args.Omega_m),
            omega_b_h2=float(args.omega_b_h2),
            omega_c_h2=float(args.omega_c_h2),
            N_eff=float(args.N_eff),
            Tcmb_K=float(args.Tcmb_K),
            z_star=None if args.z_star is None else float(args.z_star),
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    payload: Dict[str, Any] = {
        "model": str(args.model),
        "inputs": {
            "H0_km_s_Mpc": float(args.H0),
            "Omega_m": float(args.Omega_m),
            "omega_b_h2": float(args.omega_b_h2),
            "omega_c_h2": float(args.omega_c_h2),
            "N_eff": float(args.N_eff),
            "Tcmb_K": float(args.Tcmb_K),
            "z_star": None if args.z_star is None else float(args.z_star),
        },
        "predicted": predicted,
    }

    if args.priors_csv is not None:
        priors = CMBPriorsDataset.from_csv(args.priors_csv, cov_path=args.cov, name="cmb_shift_priors")
        chi2 = priors.chi2_from_values(predicted)
        payload["priors_eval"] = {
            "csv": str(args.priors_csv.expanduser().resolve()),
            "cov": str(args.cov.expanduser().resolve()) if args.cov is not None else None,
            "keys": list(priors.keys),
            "chi2": float(chi2.chi2),
            "ndof": int(chi2.ndof),
            "method": str(chi2.meta.get("method", "")),
        }

    _write_json(out_path, payload)
    print(f"[ok] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
