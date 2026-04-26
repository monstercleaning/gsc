#!/usr/bin/env python3
"""Analytic lower bound implied by positive drift in a redshift window.

Diagnostic-only helper (no pipeline side effects).

If `H(z) < H0*(1+z)` on z in [z1, z2], then:

    integral_{z1}^{z2} dz / H(z) > (1/H0) * ln[(1+z2)/(1+z1)].

Comoving-distance lower bound in Mpc:

    Delta chi_min = (c/H0) * ln[(1+z2)/(1+z1)].
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent

_C_KM_S = 299792.458


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _run_git(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(list(args), stderr=subprocess.STDOUT, text=True).strip()
    except Exception:  # pragma: no cover
        # Keep manifests portable in git-less snapshots.
        return "<git_unavailable>"


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def delta_chi_min_mpc(*, H0_km_s_Mpc: float, z1: float, z2: float) -> float:
    """Lower bound on comoving distance contribution from [z1, z2] in Mpc."""
    H0 = float(H0_km_s_Mpc)
    zz1 = float(z1)
    zz2 = float(z2)
    if not (math.isfinite(H0) and H0 > 0.0):
        raise ValueError("H0_km_s_Mpc must be finite and > 0.")
    if not (math.isfinite(zz1) and math.isfinite(zz2) and zz2 > zz1 and zz1 > -1.0):
        raise ValueError("Require finite z1,z2 with z2>z1 and z1>-1.")
    return (_C_KM_S / H0) * math.log((1.0 + zz2) / (1.0 + zz1))


def _parse_h0_values(s: str) -> List[float]:
    vals: List[float] = []
    for tok in str(s).split(","):
        t = tok.strip()
        if not t:
            continue
        vals.append(float(t))
    if not vals:
        raise ValueError("Empty H0 value list.")
    return vals


def _make_h0_grid(*, h0_min: float, h0_max: float, h0_step: float) -> List[float]:
    if not (h0_step > 0.0):
        raise ValueError("h0_step must be > 0.")
    if not (h0_max >= h0_min):
        raise ValueError("require h0_max >= h0_min")
    out: List[float] = []
    x = float(h0_min)
    limit = float(h0_max) + 0.5 * float(h0_step)
    while x <= limit:
        out.append(round(x, 10))
        x += float(h0_step)
    return out


def run(
    *,
    out_dir: Path,
    z1: float,
    z2: float,
    h0_values: Sequence[float],
    reference_h0: float,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables = out_dir / "tables"
    _ensure_dir(tables)

    rows: List[Dict[str, float]] = []
    for h0 in sorted(float(x) for x in h0_values):
        bound = float(delta_chi_min_mpc(H0_km_s_Mpc=h0, z1=z1, z2=z2))
        rows.append(
            {
                "H0_km_s_Mpc": float(h0),
                "z1": float(z1),
                "z2": float(z2),
                "ln_ratio": float(math.log((1.0 + float(z2)) / (1.0 + float(z1)))),
                "delta_chi_min_Mpc": float(bound),
            }
        )

    csv_path = tables / "drift_bound_analytic_h0_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["H0_km_s_Mpc", "z1", "z2", "ln_ratio", "delta_chi_min_Mpc"],
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: f"{float(v):.16g}" for k, v in r.items()})

    ref_bound = float(delta_chi_min_mpc(H0_km_s_Mpc=float(reference_h0), z1=z1, z2=z2))
    summary = tables / "summary.txt"
    summary.write_text(
        (
            "E2 analytic drift bound (diagnostic-only)\n\n"
            "If H(z) < H0(1+z) on [z1,z2], then\n"
            "  integral dz/H(z) > (1/H0) ln[(1+z2)/(1+z1)].\n"
            "Comoving-distance lower bound:\n"
            "  Delta chi_min = (c/H0) ln[(1+z2)/(1+z1)].\n\n"
            f"z1={float(z1):g}, z2={float(z2):g}, ln-ratio={math.log((1.0+float(z2))/(1.0+float(z1))):.12g}\n"
            f"H0_ref={float(reference_h0):g} km/s/Mpc -> Delta chi_min={ref_bound:.12g} Mpc\n"
        ),
        encoding="utf-8",
    )

    manifest = {
        "diagnostic_only": True,
        "kind": "e2_drift_bound_analytic",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "z1": float(z1),
            "z2": float(z2),
            "h0_values": [float(x) for x in h0_values],
            "reference_h0": float(reference_h0),
            "formula": "delta_chi_min_Mpc = (c/H0) * ln((1+z2)/(1+z1))",
            "c_km_s": float(_C_KM_S),
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "table_h0_scan": _relpath(csv_path),
            "summary_text": _relpath(summary),
        },
        "notes": [
            "Analytic sanity bound only; no cosmological fit is performed.",
            "Useful as an intuition appendix for WS14 drift-constrained diagnostics.",
        ],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    print(f"WROTE {csv_path}")
    print(f"WROTE {summary}")
    print(f"WROTE {manifest_path}")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_e2_drift_bound_analytic"))
    ap.add_argument("--z1", type=float, default=2.0)
    ap.add_argument("--z2", type=float, default=5.0)
    ap.add_argument("--h0-min", type=float, default=60.0)
    ap.add_argument("--h0-max", type=float, default=75.0)
    ap.add_argument("--h0-step", type=float, default=2.5)
    ap.add_argument("--h0-values", type=str, default="", help="Optional CSV list overriding min/max/step.")
    ap.add_argument("--reference-h0", type=float, default=67.4)
    args = ap.parse_args(argv)

    h0_values = (
        _parse_h0_values(args.h0_values)
        if str(args.h0_values).strip()
        else _make_h0_grid(h0_min=float(args.h0_min), h0_max=float(args.h0_max), h0_step=float(args.h0_step))
    )
    run(
        out_dir=Path(args.outdir),
        z1=float(args.z1),
        z2=float(args.z2),
        h0_values=h0_values,
        reference_h0=float(args.reference_h0),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
