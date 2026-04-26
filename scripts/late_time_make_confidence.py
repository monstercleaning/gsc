#!/usr/bin/env python3
"""Generate simple confidence-region artifacts from grid-fit CSVs (v11.0.0).

This is a lightweight post-process step that turns the (model, chi2) grid into:
- 1D profile-likelihood curves and approximate 1σ/2σ intervals (Δχ²=1,4)
- 2D profile-likelihood contours for parameter pairs (Δχ²=2.30,6.17)

Notes:
- This assumes the CSV contains (at least) the full scanned grid. If it only
  contains a top-K subset, results will be incomplete; we detect this and warn.
- The results are *grid-based* and thus approximate (resolution limited).
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit("numpy is required for late_time_make_confidence.py") from e
    return np


def _load_fit_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_grid_csv(path: Path) -> Tuple[List[Dict[str, float]], List[str]]:
    rows: List[Dict[str, float]] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if r.fieldnames is None:
            raise ValueError(f"Missing CSV header: {path}")
        fields = [c.strip() for c in r.fieldnames if c and c.strip()]
        for row in r:
            if not row:
                continue
            chi2_s = (row.get("chi2") or "").strip()
            if not chi2_s:
                continue
            try:
                chi2 = float(chi2_s)
            except ValueError:
                continue
            out: Dict[str, float] = {"chi2": float(chi2)}
            for c in fields:
                if c in ("model", "chi2", "ndof"):
                    continue
                s = (row.get(c) or "").strip()
                if not s:
                    continue
                try:
                    out[c] = float(s)
                except ValueError:
                    continue
            rows.append(out)
    return rows, fields


def _expected_grid_points(grid: Dict[str, Any]) -> int:
    n = 1
    for v in grid.values():
        if isinstance(v, list):
            n *= max(1, int(len(v)))
    return int(n)


def _profile_1d(rows: List[Dict[str, float]], *, param: str) -> Tuple[List[float], List[float]]:
    """Return (x_sorted, chi2_profile) where chi2_profile[x] = min chi2 at that x."""
    by_val: Dict[float, float] = {}
    for r in rows:
        if param not in r:
            continue
        x = float(r[param])
        c2 = float(r["chi2"])
        prev = by_val.get(x)
        if prev is None or c2 < prev:
            by_val[x] = c2
    xs = sorted(by_val.keys())
    chi2s = [float(by_val[x]) for x in xs]
    return xs, chi2s


def _interval(xs: List[float], dchi2: List[float], *, threshold: float) -> List[float] | None:
    if not xs:
        return None
    keep = [x for x, d in zip(xs, dchi2) if float(d) <= float(threshold)]
    if not keep:
        return None
    return [float(min(keep)), float(max(keep))]


def _write_profile_csv(path: Path, *, xs: List[float], chi2: List[float], chi2_min: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["value", "chi2", "delta_chi2"])
        for x, c2 in zip(xs, chi2):
            w.writerow([f"{x:.12g}", f"{c2:.12g}", f"{(c2 - chi2_min):.12g}"])


def _plot_profile(path: Path, *, param: str, xs: List[float], dchi2: List[float], best_x: float) -> None:
    np = _require_numpy()
    import matplotlib.pyplot as plt  # type: ignore

    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.asarray(xs, dtype=float)
    y = np.asarray(dchi2, dtype=float)
    plt.figure(figsize=(6, 4))
    plt.plot(x, y, lw=2)
    plt.axhline(1.0, color="0.5", lw=1, ls="--", label="1σ (Δχ²=1)")
    plt.axhline(4.0, color="0.5", lw=1, ls=":", label="2σ (Δχ²=4)")
    plt.axvline(float(best_x), color="k", lw=1)
    plt.xlabel(param)
    plt.ylabel("Δχ² (profiled)")
    plt.title(f"Profile Likelihood: {param}")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def _profile_2d(
    rows: List[Dict[str, float]],
    *,
    p1: str,
    p2: str,
) -> Tuple[List[float], List[float], List[List[float]]]:
    """Return (x1_sorted, x2_sorted, chi2_min_grid[x1][x2]) profiled over other params."""
    by_pair: Dict[Tuple[float, float], float] = {}
    for r in rows:
        if p1 not in r or p2 not in r:
            continue
        x1 = float(r[p1])
        x2 = float(r[p2])
        c2 = float(r["chi2"])
        key = (x1, x2)
        prev = by_pair.get(key)
        if prev is None or c2 < prev:
            by_pair[key] = c2

    x1s = sorted({k[0] for k in by_pair.keys()})
    x2s = sorted({k[1] for k in by_pair.keys()})
    grid: List[List[float]] = [[float("nan")] * len(x2s) for _ in x1s]
    for (x1, x2), c2 in by_pair.items():
        i = x1s.index(x1)
        j = x2s.index(x2)
        grid[i][j] = float(c2)
    return x1s, x2s, grid


def _plot_contour(
    path: Path,
    *,
    p1: str,
    p2: str,
    x1s: List[float],
    x2s: List[float],
    chi2_grid: List[List[float]],
    chi2_min: float,
    best: Dict[str, float],
) -> None:
    np = _require_numpy()
    import matplotlib.pyplot as plt  # type: ignore

    X1, X2 = np.meshgrid(np.asarray(x2s, dtype=float), np.asarray(x1s, dtype=float))
    Z = np.asarray(chi2_grid, dtype=float) - float(chi2_min)

    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(6, 5))
    # Mask NaNs to avoid contour warnings.
    Zm = np.ma.masked_invalid(Z)
    cs = plt.contour(X1, X2, Zm, levels=[2.30, 6.17], colors=["C0", "C1"])
    plt.clabel(cs, inline=True, fontsize=9, fmt={2.30: "1σ", 6.17: "2σ"})
    if p1 in best and p2 in best:
        plt.plot([float(best[p2])], [float(best[p1])], marker="*", ms=12, color="k", label="best")
    plt.xlabel(p2)
    plt.ylabel(p1)
    plt.title(f"Profile Contours: {p1} vs {p2}")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit-dir", type=Path, default=Path("v11.0.0/results/late_time_fit"))
    ap.add_argument("--models", default="lcdm,gsc_powerlaw,gsc_transition")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    fit_dir = args.fit_dir
    out_dir = args.out_dir or (fit_dir / "confidence")
    out_dir.mkdir(parents=True, exist_ok=True)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    for model in models:
        fit_path = fit_dir / f"{model}_bestfit.json"
        csv_path = fit_dir / f"{model}_top.csv"
        if not fit_path.exists() or not csv_path.exists():
            print(f"[confidence] SKIP {model}: missing {fit_path.name} or {csv_path.name}")
            continue

        fit = _load_fit_json(fit_path)
        best = fit.get("best", {})
        chi2_min = float(best.get("chi2", float("nan")))
        best_params = best.get("params", {}) if isinstance(best.get("params"), dict) else {}

        grid = fit.get("grid", {}) if isinstance(fit.get("grid"), dict) else {}
        expected = _expected_grid_points(grid)

        rows, fields = _load_grid_csv(csv_path)
        n_rows = len(rows)
        incomplete = bool(expected > 0 and n_rows < expected)
        if incomplete:
            print(f"[confidence] WARNING {model}: CSV has {n_rows} rows, expected ~{expected} grid points.")

        # Only parameters that were actually scanned (and varied).
        var_params = [k for k, v in grid.items() if isinstance(v, list) and len(v) > 1]
        if not var_params:
            print(f"[confidence] SKIP {model}: no varying grid parameters found.")
            continue

        payload: Dict[str, Any] = {
            "model": model,
            "chi2_min": float(chi2_min),
            "expected_grid_points": int(expected),
            "rows_in_csv": int(n_rows),
            "incomplete": bool(incomplete),
            "best_params": {k: float(v) for k, v in best_params.items() if isinstance(v, (int, float))},
            "profiles_1d": {},
        }

        # 1D profiles.
        for p in var_params:
            xs, chi2s = _profile_1d(rows, param=p)
            if not xs:
                continue
            chi2_min_p = min(chi2s)
            # Prefer the global chi2_min, but if CSV is incomplete fall back to profile min.
            ref = chi2_min if math.isfinite(chi2_min) else chi2_min_p
            if not math.isfinite(ref):
                ref = chi2_min_p
            dchi2 = [c2 - ref for c2 in chi2s]

            best_x = xs[int(min(range(len(xs)), key=lambda i: chi2s[i]))]
            payload["profiles_1d"][p] = {
                "best": float(best_x),
                "interval_1sigma": _interval(xs, dchi2, threshold=1.0),
                "interval_2sigma": _interval(xs, dchi2, threshold=4.0),
            }

            _write_profile_csv(out_dir / model / f"profile_{p}.csv", xs=xs, chi2=chi2s, chi2_min=ref)
            _plot_profile(out_dir / model / f"profile_{p}.png", param=p, xs=xs, dchi2=dchi2, best_x=best_x)

        # 2D contours for all pairs.
        for p1, p2 in itertools.combinations(var_params, 2):
            x1s, x2s, c2_grid = _profile_2d(rows, p1=p1, p2=p2)
            if len(x1s) < 2 or len(x2s) < 2:
                continue
            # Use minimum value present in the grid if global min is not finite.
            c2_min_grid = min((c2 for row in c2_grid for c2 in row if math.isfinite(c2)), default=float("nan"))
            ref = chi2_min if math.isfinite(chi2_min) else c2_min_grid
            _plot_contour(
                out_dir / model / f"contour_{p1}_vs_{p2}.png",
                p1=p1,
                p2=p2,
                x1s=x1s,
                x2s=x2s,
                chi2_grid=c2_grid,
                chi2_min=ref,
                best={k: float(v) for k, v in best_params.items() if isinstance(v, (int, float))},
            )

        (out_dir / model / "intervals.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[confidence] WROTE {out_dir / model}")


if __name__ == "__main__":
    main()

