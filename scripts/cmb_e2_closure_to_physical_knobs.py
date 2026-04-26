#!/usr/bin/env python3
"""E2.11 diagnostic: translate closure requirements into physical knobs.

Maps WS13-style closure requirements (`A_required_const`) into:
- effective running-G interpretation:    deltaG_required = A^2 - 1
- effective energy-density interpretation: delta_rho_over_rho_required = A^2 - 1

Diagnostic-only; does not modify canonical late-time outputs.
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

import numpy as np  # noqa: E402


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


def _is_finite(x: float) -> bool:
    return math.isfinite(float(x))


@dataclass(frozen=True)
class Row:
    target_label: str
    target_source: str
    dm_target: float
    z_boost_start: float
    A_required_const: float
    deltaH_over_H: float
    deltaG_required: float
    delta_rho_over_rho_required: float
    bridge_z_used: Optional[float]
    z_star: Optional[float]

    def as_csv(self) -> Dict[str, str]:
        def f(x: Optional[float]) -> str:
            if x is None:
                return ""
            if not _is_finite(float(x)):
                return ""
            return f"{float(x):.16g}"

        return {
            "target_label": str(self.target_label),
            "target_source": str(self.target_source),
            "dm_target": f(self.dm_target),
            "z_boost_start": f(self.z_boost_start),
            "A_required_const": f(self.A_required_const),
            "deltaH_over_H": f(self.deltaH_over_H),
            "deltaG_required": f(self.deltaG_required),
            "delta_rho_over_rho_required": f(self.delta_rho_over_rho_required),
            "bridge_z_used": f(self.bridge_z_used),
            "z_star": f(self.z_star),
        }


def _load_ws13_rows(ws13_table_csv: Path) -> List[Row]:
    if not ws13_table_csv.is_file():
        raise FileNotFoundError(f"WS13 table not found: {ws13_table_csv}")

    rows: List[Row] = []
    with ws13_table_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                A = float(r["A_required_const"])
                dm = float(r["dm_target"])
                z_start = float(r["z_boost_start"])
            except Exception:
                continue
            if not (_is_finite(A) and A > 0.0):
                continue
            if not (_is_finite(dm) and dm > 0.0):
                continue
            if not (_is_finite(z_start) and z_start >= 0.0):
                continue

            dH = float(A - 1.0)
            dG = float(A * A - 1.0)
            drho = float(dG)

            bz: Optional[float]
            zs: Optional[float]
            try:
                bz = float(r.get("bridge_z_used", "nan"))
                if not _is_finite(bz):
                    bz = None
            except Exception:
                bz = None
            try:
                zs = float(r.get("z_star", "nan"))
                if not _is_finite(zs):
                    zs = None
            except Exception:
                zs = None

            rows.append(
                Row(
                    target_label=str(r.get("target_label", "")),
                    target_source=str(r.get("target_source", "")),
                    dm_target=float(dm),
                    z_boost_start=float(z_start),
                    A_required_const=float(A),
                    deltaH_over_H=float(dH),
                    deltaG_required=float(dG),
                    delta_rho_over_rho_required=float(drho),
                    bridge_z_used=bz,
                    z_star=zs,
                )
            )
    if not rows:
        raise ValueError(f"No valid rows parsed from {ws13_table_csv}")
    return rows


def _write_summary_by_z(rows: Sequence[Row], out_csv: Path) -> List[Dict[str, Any]]:
    zs = sorted(set(float(r.z_boost_start) for r in rows))
    out: List[Dict[str, Any]] = []
    for z in zs:
        rr = [r for r in rows if abs(float(r.z_boost_start) - float(z)) < 1e-12]
        arr_dm = np.asarray([float(r.dm_target) for r in rr], dtype=float)
        arr_A = np.asarray([float(r.A_required_const) for r in rr], dtype=float)
        arr_dG = np.asarray([float(r.deltaG_required) for r in rr], dtype=float)
        entry = {
            "z_boost_start": float(z),
            "n_targets": int(len(rr)),
            "dm_p10": float(np.quantile(arr_dm, 0.1)),
            "dm_p50": float(np.quantile(arr_dm, 0.5)),
            "dm_p90": float(np.quantile(arr_dm, 0.9)),
            "A_p10": float(np.quantile(arr_A, 0.1)),
            "A_p50": float(np.quantile(arr_A, 0.5)),
            "A_p90": float(np.quantile(arr_A, 0.9)),
            "deltaG_p10": float(np.quantile(arr_dG, 0.1)),
            "deltaG_p50": float(np.quantile(arr_dG, 0.5)),
            "deltaG_p90": float(np.quantile(arr_dG, 0.9)),
        }
        out.append(entry)

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "z_boost_start",
            "n_targets",
            "dm_p10",
            "dm_p50",
            "dm_p90",
            "A_p10",
            "A_p50",
            "A_p90",
            "deltaG_p10",
            "deltaG_p50",
            "deltaG_p90",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in out:
            row = {}
            for k in fields:
                v = e[k]
                if isinstance(v, float):
                    row[k] = f"{v:.16g}"
                else:
                    row[k] = str(v)
            w.writerow(row)
    return out


def _plot_deltaG_vs_dm(rows: Sequence[Row], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    groups = sorted(set(float(r.z_boost_start) for r in rows))
    fig, ax = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    for z in groups:
        rr = [r for r in rows if abs(float(r.z_boost_start) - float(z)) < 1e-12]
        rr = sorted(rr, key=lambda x: float(x.dm_target))
        ax.plot(
            [float(r.dm_target) for r in rr],
            [float(r.deltaG_required) for r in rr],
            marker="o",
            linewidth=1.8,
            label=f"z_start={z:g}",
        )
    ax.set_xlabel("dm_target")
    ax.set_ylabel("deltaG_required = A^2 - 1")
    ax.set_title("E2.11 diagnostic: effective deltaG required vs dm target")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, ncol=2, fontsize=8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def _plot_deltaG_vs_z(rows: Sequence[Row], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    labels = sorted(set(r.target_label for r in rows))
    fig, ax = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    for label in labels:
        rr = [r for r in rows if r.target_label == label]
        rr = sorted(rr, key=lambda x: float(x.z_boost_start))
        ax.plot(
            [float(r.z_boost_start) for r in rr],
            [float(r.deltaG_required) for r in rr],
            marker="o",
            linewidth=1.8,
            label=f"{label} (dm={float(rr[0].dm_target):.4f})",
        )
    ax.set_xlabel("z_boost_start")
    ax.set_ylabel("deltaG_required = A^2 - 1")
    ax.set_yscale("log")
    ax.set_title("E2.11 diagnostic: effective deltaG required vs repair start")
    ax.grid(True, alpha=0.25, which="both")
    ax.legend(frameon=False, fontsize=8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def run(
    *,
    ws13_table_csv: Path,
    out_dir: Path,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    rows = _load_ws13_rows(ws13_table_csv.resolve())
    rows = sorted(rows, key=lambda r: (float(r.z_boost_start), str(r.target_label), float(r.dm_target)))

    table_csv = tables_dir / "closure_to_knobs_summary.csv"
    with table_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv().keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv())

    pivot_csv = tables_dir / "closure_to_knobs_by_zstart.csv"
    pivot = _write_summary_by_z(rows, pivot_csv)

    fig1 = figs_dir / "deltaG_required_vs_dm_target.png"
    _plot_deltaG_vs_dm(rows, fig1)
    fig2 = figs_dir / "deltaG_required_vs_z_start.png"
    _plot_deltaG_vs_z(rows, fig2)

    summary_txt = tables_dir / "summary.txt"
    by_z = {float(e["z_boost_start"]): e for e in pivot}
    z5 = by_z.get(5.0)
    z10 = by_z.get(10.0)
    lines = [
        "E2.11 closure->physical-knobs translation (diagnostic-only)",
        "",
        f"Input WS13 table: {_relpath(ws13_table_csv)}",
        "Mapping used:",
        "  deltaG_required = A_required_const^2 - 1",
        "  delta_rho_over_rho_required = A_required_const^2 - 1",
        "",
    ]
    if z5 is not None:
        lines.append(
            "z_start=5  (p10/p50/p90): "
            f"A=({z5['A_p10']:.4g},{z5['A_p50']:.4g},{z5['A_p90']:.4g})  "
            f"deltaG=({z5['deltaG_p10']:.4g},{z5['deltaG_p50']:.4g},{z5['deltaG_p90']:.4g})"
        )
    if z10 is not None:
        lines.append(
            "z_start=10 (p10/p50/p90): "
            f"A=({z10['A_p10']:.4g},{z10['A_p50']:.4g},{z10['A_p90']:.4g})  "
            f"deltaG=({z10['deltaG_p10']:.4g},{z10['deltaG_p50']:.4g},{z10['deltaG_p90']:.4g})"
        )
    lines += [
        "",
        "Interpretation:",
        "- These are effective mappings, not microphysical claims.",
        "- If required deltaG (or equivalent delta_rho/rho) is large in drift-safe regions, tested repair families are practically no-go.",
    ]
    summary_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_closure_to_physical_knobs",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {"ws13_table_csv": _relpath(ws13_table_csv)},
        "mapping": {
            "deltaG_required": "A_required_const^2 - 1",
            "delta_rho_over_rho_required": "A_required_const^2 - 1",
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "table_summary": _relpath(table_csv),
            "table_by_zstart": _relpath(pivot_csv),
            "summary_text": _relpath(summary_txt),
            "fig_deltaG_vs_dm_target": _relpath(fig1),
            "fig_deltaG_vs_z_start": _relpath(fig2),
        },
        "summary": {
            "num_rows": int(len(rows)),
            "num_targets": int(len(set(r.target_label for r in rows))),
            "z_starts": sorted({float(r.z_boost_start) for r in rows}),
        },
        "notes": [
            "Diagnostic-only mapping from closure requirements to effective physical knob scales.",
            "Uses WS13 A_required_const table as input.",
            "No canonical late-time outputs are modified.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--ws13-table",
        type=Path,
        default=Path("v11.0.0/results/diagnostic_cmb_e2_closure_requirements/tables/A_required_vs_zstart.csv"),
    )
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_e2_closure_to_physical_knobs"))
    args = ap.parse_args(argv)
    run(ws13_table_csv=Path(args.ws13_table), out_dir=Path(args.outdir))


if __name__ == "__main__":  # pragma: no cover
    main()
