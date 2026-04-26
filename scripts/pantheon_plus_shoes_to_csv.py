#!/usr/bin/env python3
"""Convert Pantheon+SH0ES DataRelease .dat table to harness CSVs (stdlib-only).

Input:
  v11.0.0/data/sn/pantheon_plus_shoes/Pantheon+SH0ES.dat

Outputs:
  v11.0.0/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_mu.csv
  v11.0.0/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv

Mapping (canonical for v11.0.0 harness):
  z := zHD
  mu := MU_SH0ES
  sigma_mu := MU_SH0ES_ERR_DIAG
  hflow selection: IS_CALIBRATOR == 0

Extra provenance columns (safe for the harness; ignored unless used):
  row_full := 0-based index of the row in the original .dat table
  is_calibrator := IS_CALIBRATOR (0/1)
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--src",
        type=Path,
        default=Path("v11.0.0/data/sn/pantheon_plus_shoes/Pantheon+SH0ES.dat"),
    )
    ap.add_argument(
        "--out-all",
        type=Path,
        default=Path("v11.0.0/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_mu.csv"),
    )
    ap.add_argument(
        "--out-hflow",
        type=Path,
        default=Path("v11.0.0/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv"),
    )
    args = ap.parse_args()

    src: Path = args.src
    if not src.exists():
        raise SystemExit(f"missing input: {src}")

    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        raise SystemExit(f"empty file: {src}")

    header = lines[0].strip().split()
    need = {
        "z": "zHD",
        "mu": "MU_SH0ES",
        "sig": "MU_SH0ES_ERR_DIAG",
        "cal": "IS_CALIBRATOR",
    }
    missing = [v for v in need.values() if v not in header]
    if missing:
        raise SystemExit(f"missing columns in header: {missing}. header[:20]={header[:20]}")

    i_z = header.index(need["z"])
    i_mu = header.index(need["mu"])
    i_sig = header.index(need["sig"])
    i_cal = header.index(need["cal"])

    def parse_rows(*, hflow_only: bool) -> list[tuple[int, float, float, float, int]]:
        rows: list[tuple[int, float, float, float, int]] = []
        row_full = -1
        for ln in lines[1:]:
            ln = ln.strip()
            if not ln:
                continue
            row_full += 1
            parts = ln.split()
            if len(parts) != len(header):
                raise SystemExit(
                    f"bad row with {len(parts)} cols (expected {len(header)}): {ln[:200]}"
                )
            is_cal = int(float(parts[i_cal]))
            if hflow_only and is_cal != 0:
                continue
            z = float(parts[i_z])
            mu = float(parts[i_mu])
            sig = float(parts[i_sig])
            rows.append((row_full, z, mu, sig, is_cal))
        return rows

    def write_csv(path: Path, rows: list[tuple[int, float, float, float, int]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["row_full", "z", "mu", "sigma_mu", "is_calibrator"])
            for row_full, z, mu, sig, is_cal in rows:
                w.writerow([row_full, f"{z:.10g}", f"{mu:.10g}", f"{sig:.10g}", is_cal])

    rows_all = parse_rows(hflow_only=False)
    rows_hf = parse_rows(hflow_only=True)

    write_csv(args.out_all, rows_all)
    write_csv(args.out_hflow, rows_hf)

    print(f"WROTE {args.out_all} N={len(rows_all)}")
    print(f"WROTE {args.out_hflow} N={len(rows_hf)}")


if __name__ == "__main__":
    main()
