#!/usr/bin/env python3
"""Generate batch early-time CMB priors reports for bestfit outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from _outdir import resolve_outdir, resolve_path_under_outdir  # noqa: E402
from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time.cmb_priors_reporting import (  # noqa: E402
    CMBPriorsBatchConfig,
    build_numerics_invariants_report,
    INVARIANTS_SCHEMA_VERSION,
    evaluate_fit_dir_cmb_priors,
    write_cmb_priors_report_csv,
    write_cmb_priors_report_json,
    write_numerics_invariants_report_json,
)
from gsc.early_time.params import early_time_params_from_namespace  # noqa: E402
from gsc.optional_deps import require_numpy  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="early_time_cmb_priors_report",
        description="Phase 2 M4: batch CMB priors reporting for fit_dir bestfit outputs.",
    )
    ap.add_argument("--fit-dir", type=Path, required=True, help="Directory containing *_bestfit.json files.")
    ap.add_argument("--cmb", type=Path, required=True, help="Compressed CMB priors CSV.")
    ap.add_argument("--cmb-cov", type=Path, default=None, help="Optional CMB covariance (.cov/.npz).")
    ap.add_argument(
        "--cmb-mode",
        choices=["distance_priors", "shift_params", "theta_star"],
        default=None,
        help="Optional override for driver mode. If omitted, infer from each bestfit file.",
    )
    ap.add_argument("--cmb-bridge-z", type=float, default=None, help="Optional override for non-LCDM bridge z.")
    ap.add_argument("--omega-b-h2", type=float, required=True)
    ap.add_argument("--omega-c-h2", type=float, required=True)
    ap.add_argument("--Neff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="outdir",
        type=Path,
        default=None,
        help="Output root (CLI > GSC_OUTDIR > v11.0.0/artifacts/release).",
    )
    ap.add_argument("--out", type=Path, default=Path("early_time/cmb_priors_report.json"))
    ap.add_argument("--out-csv", type=Path, default=Path("early_time/cmb_priors_table.csv"))
    ap.add_argument(
        "--out-invariants",
        type=Path,
        default=Path("early_time/numerics_invariants_report.json"),
        help="Path for numerics invariants JSON report (relative paths resolve under outdir).",
    )
    args = ap.parse_args(argv)

    try:
        require_numpy()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    out_root = resolve_outdir(args.outdir, v101_dir=V101_DIR)
    out_json = resolve_path_under_outdir(args.out, out_root=out_root)
    out_csv = resolve_path_under_outdir(args.out_csv, out_root=out_root)
    out_invariants = resolve_path_under_outdir(args.out_invariants, out_root=out_root)
    if out_json is None or out_csv is None or out_invariants is None:  # pragma: no cover
        raise SystemExit("failed to resolve output paths")

    print(f"[info] OUTDIR={out_root}")
    print(f"[info] REPORT={out_json}")
    print(f"[info] TABLE={out_csv}")
    print(f"[info] INVARIANTS={out_invariants}")

    try:
        early_time_params = early_time_params_from_namespace(
            args,
            require=True,
            context="CMB priors reporting",
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if early_time_params is None:  # pragma: no cover - guarded above
        raise SystemExit("CMB priors reporting requires --omega-b-h2 and --omega-c-h2")

    mode = None
    if args.cmb_mode in ("distance_priors", "shift_params"):
        mode = str(args.cmb_mode)
    elif args.cmb_mode == "theta_star":
        mode = "shift_params"

    priors = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb")
    cfg = CMBPriorsBatchConfig(
        omega_b_h2=float(early_time_params.omega_b_h2),
        omega_c_h2=float(early_time_params.omega_c_h2),
        N_eff=float(early_time_params.N_eff),
        Tcmb_K=float(early_time_params.Tcmb_K),
        mode=mode,
        z_bridge=None if args.cmb_bridge_z is None else float(args.cmb_bridge_z),
    )

    try:
        report, table_rows = evaluate_fit_dir_cmb_priors(
            fit_dir=args.fit_dir,
            priors=priors,
            config=cfg,
            repo_root=V101_DIR.parent,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    report.setdefault("priors", {})
    report["priors"]["csv"] = str(args.cmb.expanduser().resolve())
    report["priors"]["cov"] = str(args.cmb_cov.expanduser().resolve()) if args.cmb_cov is not None else None
    invariants = build_numerics_invariants_report(cmb_report=report, repo_root=V101_DIR.parent)

    write_cmb_priors_report_json(out_json, report)
    write_cmb_priors_report_csv(out_csv, table_rows)
    write_numerics_invariants_report_json(out_invariants, invariants)
    print(f"[ok] wrote {out_json}")
    print(f"[ok] wrote {out_csv}")
    print(f"[ok] wrote {out_invariants}")
    if str(invariants.get("schema_version", "")) != INVARIANTS_SCHEMA_VERSION:  # pragma: no cover
        raise SystemExit("unexpected numerics invariants schema version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
