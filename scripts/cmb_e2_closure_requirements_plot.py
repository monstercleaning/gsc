#!/usr/bin/env python3
"""WS13 diagnostic: closure requirements / no-go map consolidation.

Produces a compact referee-grade mapping:
- representative `dm_fit` targets (from E2.4 scan quantiles and/or explicit anchors),
- effective constant `A_required` vs `z_boost_start`,
using the same E2.3 distance-integral mapping.

Diagnostic-only; does not change canonical late-time outputs.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))
sys.path.insert(0, str(V101_DIR / "scripts"))

import numpy as np  # noqa: E402

import cmb_e2_distance_closure_to_hboost as e23  # noqa: E402


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def _run_git(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(list(args), stderr=subprocess.STDOUT, text=True).strip()
    except Exception as e:  # pragma: no cover
        return f"<error: {e}>"


def _parse_float_csv(s: str) -> List[float]:
    out: List[float] = []
    for tok in str(s).split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))
    if not out:
        raise ValueError("empty CSV list")
    return out


def _finite(x: float) -> bool:
    return math.isfinite(float(x))


def _load_dm_values_from_e24(
    *,
    csv_path: Path,
    bridge_z_used: float,
) -> List[float]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"E2.4 scan CSV not found: {csv_path}")
    vals: List[float] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                z = float(row["bridge_z_used"])
                deg = str(row["is_degenerate"]).strip().lower() == "true"
                dm = float(row["dm_fit"])
            except Exception:
                continue
            if deg:
                continue
            if abs(float(z) - float(bridge_z_used)) > 1e-12:
                continue
            if _finite(dm) and dm > 0.0:
                vals.append(float(dm))
    if not vals:
        raise ValueError(f"No non-degenerate dm_fit values for bridge_z_used={bridge_z_used:g} in {csv_path}")
    return vals


@dataclass(frozen=True)
class DMTarget:
    label: str
    source: str
    dm_value: float


@dataclass(frozen=True)
class ClosureRow:
    target_label: str
    target_source: str
    dm_target: float
    z_boost_start: float
    A_required_const: Optional[float]
    deltaH_over_H: Optional[float]
    bridge_z_used: float
    z_star: float

    def as_csv(self) -> Dict[str, str]:
        def f(v: Optional[float]) -> str:
            if v is None:
                return ""
            if not _finite(float(v)):
                return ""
            return f"{float(v):.16g}"

        return {
            "target_label": str(self.target_label),
            "target_source": str(self.target_source),
            "dm_target": f(self.dm_target),
            "z_boost_start": f(self.z_boost_start),
            "A_required_const": f(self.A_required_const),
            "deltaH_over_H": f(self.deltaH_over_H),
            "bridge_z_used": f(self.bridge_z_used),
            "z_star": f(self.z_star),
        }


def _collect_targets(
    *,
    dm_values_e24: Sequence[float],
    quantiles: Sequence[float],
    dm_targets_explicit: Sequence[float],
) -> List[DMTarget]:
    targets: List[DMTarget] = []
    arr = np.asarray(list(dm_values_e24), dtype=float)

    for q in quantiles:
        qq = float(q)
        if not (0.0 <= qq <= 1.0):
            raise ValueError(f"quantile outside [0,1]: {qq}")
        v = float(np.quantile(arr, qq))
        label = f"q{int(round(qq * 100.0)):02d}"
        targets.append(DMTarget(label=label, source="e2.4_quantile", dm_value=v))

    for i, x in enumerate(dm_targets_explicit, start=1):
        xv = float(x)
        if not (xv > 0.0 and _finite(xv)):
            raise ValueError(f"explicit dm target must be finite and >0, got {x}")
        label = f"anchor{i}"
        targets.append(DMTarget(label=label, source="explicit_anchor", dm_value=xv))

    # Stable de-dup by (label, source, rounded value)
    out: List[DMTarget] = []
    seen: set[Tuple[str, str, int]] = set()
    for t in targets:
        k = (t.label, t.source, int(round(float(t.dm_value) * 1.0e12)))
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    if not out:
        raise ValueError("No targets collected")
    return out


def _rows_for_target(
    *,
    target: DMTarget,
    z_boost_starts: Sequence[float],
    model: str,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    gsc_p: float,
    gsc_ztrans: float,
    cmb_bridge_z: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
) -> List[ClosureRow]:
    r = e23.compute_effective_hboost_solution(
        model=str(model),
        H0_km_s_Mpc=float(H0_km_s_Mpc),
        Omega_m=float(Omega_m),
        Omega_L=float(Omega_L),
        gsc_p=float(gsc_p),
        gsc_ztrans=float(gsc_ztrans),
        cmb_bridge_z=float(cmb_bridge_z),
        dm_star_calibration=float(target.dm_value),
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        Neff=float(Neff),
        Tcmb_K=float(Tcmb_K),
        z_boost_starts=list(z_boost_starts),
    )
    rows: List[ClosureRow] = []
    for row in r["rows"]:
        A = row.get("A", None)
        dH = row.get("deltaH_over_H", None)
        if A is not None and not _finite(float(A)):
            A = None
        if dH is not None and not _finite(float(dH)):
            dH = None
        rows.append(
            ClosureRow(
                target_label=str(target.label),
                target_source=str(target.source),
                dm_target=float(target.dm_value),
                z_boost_start=float(row["z_boost_start"]),
                A_required_const=(None if A is None else float(A)),
                deltaH_over_H=(None if dH is None else float(dH)),
                bridge_z_used=float(r["z_bridge_used"]),
                z_star=float(r["z_star"]),
            )
        )
    return rows


def _plot_A_required(
    *,
    rows: Sequence[ClosureRow],
    out_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    labels = sorted(set(r.target_label for r in rows))
    fig, ax = plt.subplots(figsize=(8.0, 4.8), constrained_layout=True)
    for label in labels:
        rr = [r for r in rows if r.target_label == label and r.A_required_const is not None]
        rr = sorted(rr, key=lambda x: float(x.z_boost_start))
        if not rr:
            continue
        xs = [float(r.z_boost_start) for r in rr]
        ys = [float(r.A_required_const) for r in rr]
        src = rr[0].target_source
        dm = rr[0].dm_target
        ax.plot(xs, ys, marker="o", linewidth=2.0, label=f"{label} ({src}, dm={dm:.4f})")

    ax.set_xlabel("z_boost_start")
    ax.set_ylabel("A_required_const")
    ax.set_title("WS13 diagnostic: required constant high-z H-boost vs repair start")
    ax.set_yscale("log")
    ax.grid(True, alpha=0.25, which="both")
    ax.legend(frameon=False, fontsize=8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def run(
    *,
    e24_scan_csv: Path,
    out_dir: Path,
    quantiles: Sequence[float],
    dm_targets_explicit: Sequence[float],
    z_boost_starts: Sequence[float],
    model: str,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    gsc_p: float,
    gsc_ztrans: float,
    cmb_bridge_z: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    dm_vals = _load_dm_values_from_e24(csv_path=e24_scan_csv.resolve(), bridge_z_used=float(cmb_bridge_z))
    targets = _collect_targets(dm_values_e24=dm_vals, quantiles=quantiles, dm_targets_explicit=dm_targets_explicit)

    rows: List[ClosureRow] = []
    for t in targets:
        rows.extend(
            _rows_for_target(
                target=t,
                z_boost_starts=z_boost_starts,
                model=model,
                H0_km_s_Mpc=H0_km_s_Mpc,
                Omega_m=Omega_m,
                Omega_L=Omega_L,
                gsc_p=gsc_p,
                gsc_ztrans=gsc_ztrans,
                cmb_bridge_z=cmb_bridge_z,
                omega_b_h2=omega_b_h2,
                omega_c_h2=omega_c_h2,
                Neff=Neff,
                Tcmb_K=Tcmb_K,
            )
        )
    if not rows:
        raise ValueError("No rows produced")

    csv_path = tables_dir / "A_required_vs_zstart.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv().keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv())

    # Aggregate per target for quick reading.
    summary_rows: List[Dict[str, Any]] = []
    for t in targets:
        rr = [r for r in rows if r.target_label == t.label and r.A_required_const is not None]
        rr = sorted(rr, key=lambda x: float(x.z_boost_start))
        if rr:
            A_min = float(min(float(r.A_required_const) for r in rr if r.A_required_const is not None))
            A_at_5 = next((float(r.A_required_const) for r in rr if abs(float(r.z_boost_start) - 5.0) < 1e-12 and r.A_required_const is not None), None)
            A_at_10 = next((float(r.A_required_const) for r in rr if abs(float(r.z_boost_start) - 10.0) < 1e-12 and r.A_required_const is not None), None)
        else:
            A_min = float("nan")
            A_at_5 = None
            A_at_10 = None
        summary_rows.append(
            {
                "target_label": t.label,
                "target_source": t.source,
                "dm_target": float(t.dm_value),
                "A_min": (None if not _finite(A_min) else float(A_min)),
                "A_at_z5": A_at_5,
                "A_at_z10": A_at_10,
            }
        )

    summary_csv = tables_dir / "A_required_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        fields = ["target_label", "target_source", "dm_target", "A_min", "A_at_z5", "A_at_z10"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in summary_rows:
            row = {}
            for k in fields:
                v = s[k]
                if v is None:
                    row[k] = ""
                elif isinstance(v, float):
                    row[k] = f"{v:.16g}" if _finite(v) else ""
                else:
                    row[k] = str(v)
            w.writerow(row)

    fig_path = figs_dir / "A_required_vs_zstart.png"
    _plot_A_required(rows=rows, out_path=fig_path)

    txt_path = tables_dir / "summary.txt"
    p10, p50, p90 = np.quantile(np.asarray(dm_vals, dtype=float), [0.1, 0.5, 0.9])
    lines = [
        "WS13 E2 closure requirements (diagnostic-only)",
        "",
        f"E2.4 source CSV: {_relpath(e24_scan_csv)}",
        f"bridge_z_used filter: {float(cmb_bridge_z):g}",
        f"non-degenerate dm_fit stats: n={len(dm_vals)}, p10={float(p10):.6g}, p50={float(p50):.6g}, p90={float(p90):.6g}",
        "",
        "Interpretation:",
        "- If repair starts near z~5, A_required is moderate (O(1.2) for dm~0.93 anchors).",
        "- Pushing repair start high (e.g. z~10 and above) increases A_required rapidly.",
        "- In the tested families, delaying repair start tends toward an implausible / no-go regime.",
        "",
        "Per-target snapshot:",
    ]
    for s in summary_rows:
        lines.append(
            f"  {s['target_label']} ({s['target_source']}, dm={float(s['dm_target']):.6g}): "
            f"A_min={s['A_min'] if s['A_min'] is not None else 'NA'}, "
            f"A(z=5)={s['A_at_z5'] if s['A_at_z5'] is not None else 'NA'}, "
            f"A(z=10)={s['A_at_z10'] if s['A_at_z10'] is not None else 'NA'}"
        )
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_closure_requirements",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "e24_scan_csv": _relpath(e24_scan_csv),
        },
        "grid": {
            "quantiles": [float(q) for q in quantiles],
            "dm_targets_explicit": [float(x) for x in dm_targets_explicit],
            "z_boost_starts": [float(z) for z in z_boost_starts],
            "bridge_z_used": float(cmb_bridge_z),
        },
        "model_config": {
            "model": str(model),
            "H0_km_s_Mpc": float(H0_km_s_Mpc),
            "Omega_m": float(Omega_m),
            "Omega_L": float(Omega_L),
            "gsc_p": float(gsc_p),
            "gsc_ztrans": float(gsc_ztrans),
            "omega_b_h2": float(omega_b_h2),
            "omega_c_h2": float(omega_c_h2),
            "Neff": float(Neff),
            "Tcmb_K": float(Tcmb_K),
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "table": _relpath(csv_path),
            "summary_table": _relpath(summary_csv),
            "summary_text": _relpath(txt_path),
            "figure": _relpath(fig_path),
        },
        "summary": {
            "dm_quantiles_bridge": {
                "p10": float(p10),
                "p50": float(p50),
                "p90": float(p90),
            },
            "targets": summary_rows,
        },
        "notes": [
            "Diagnostic-only consolidation of E2 closure requirements.",
            "A_required is computed via the same constant-boost mapping as E2.3.",
            "No canonical late-time outputs are modified.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--e24-scan-csv",
        type=Path,
        default=Path("v11.0.0/results/late_time_fit_cmb_e2_closure_diagnostic/scan/tables/cmb_e2_dm_rs_fit_scan.csv"),
    )
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_e2_closure_requirements"))

    ap.add_argument("--quantiles", type=str, default="0.1,0.5,0.9")
    ap.add_argument("--dm-targets", type=str, default="0.9290939714464278")
    ap.add_argument("--z-boost-start-list", type=str, default="5,6,7,8,10,12,15,20")

    ap.add_argument("--model", choices=("lcdm", "gsc_transition", "gsc_powerlaw"), default="gsc_transition")
    ap.add_argument("--cmb-bridge-z", type=float, default=5.0)
    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)
    ap.add_argument("--gsc-p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", type=float, default=1.8)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    args = ap.parse_args(argv)
    run(
        e24_scan_csv=Path(args.e24_scan_csv),
        out_dir=Path(args.outdir),
        quantiles=_parse_float_csv(str(args.quantiles)),
        dm_targets_explicit=_parse_float_csv(str(args.dm_targets)),
        z_boost_starts=_parse_float_csv(str(args.z_boost_start_list)),
        model=str(args.model),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        Omega_L=float(args.Omega_L),
        gsc_p=float(args.gsc_p),
        gsc_ztrans=float(args.gsc_ztrans),
        cmb_bridge_z=float(args.cmb_bridge_z),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
