#!/usr/bin/env python3
"""Deterministic QCD<->Gravity bridge sanity-check artifact generator (Phase-4 M160).

This tool is explicitly an idea-bank / kill-test scaffold. It does not claim
that QCD explains gravity or that RG running implies cosmic time variation.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

TOOL = "make_qcd_gravity_bridge_artifacts"
TOOL_VERSION = "m160-v1"
SCHEMA = "phase4_qcd_gravity_bridge_numbers_v1"
FAIL_MARKER = "PHASE4_QCD_GRAVITY_BRIDGE_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")

MPC_M = 3.085677581491367e22
HBAR_GEV_S = 6.582119569e-25
MPL_REDUCED_GEV = 2.435e18
PI = math.pi


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _to_iso_utc(epoch_seconds: int) -> str:
    dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt(x: float) -> str:
    return f"{float(x):.12e}"


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def _save_png_rgb(*, width: int, height: int, rows: Sequence[bytes], out_path: Path) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    if len(rows) != height:
        raise ValueError("PNG row count mismatch")
    for row in rows:
        if len(row) != width * 3:
            raise ValueError("PNG row width mismatch")

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rows)
    idat = zlib.compress(raw, level=9)
    data = signature + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")
    out_path.write_bytes(data)


def _make_ratio_plot_fallback(
    *,
    ratio_rows: Sequence[Tuple[str, float]],
    out_path: Path,
) -> None:
    """Deterministic fallback bar-like plot rendered directly to PNG bytes."""
    width, height = 640, 320
    bg = [245, 245, 248]
    image: List[List[List[int]]] = [[[bg[0], bg[1], bg[2]] for _ in range(width)] for _ in range(height)]

    # Axis frame.
    for x in range(50, width - 20):
        image[height - 40][x] = [40, 40, 45]
    for y in range(20, height - 40):
        image[y][50] = [40, 40, 45]

    # Bars use log10 ratios to preserve scale readability.
    bar_w = 120
    gap = 45
    start_x = 90
    colors = ([33, 117, 180], [220, 98, 60], [70, 160, 90], [130, 100, 200])
    values = [max(1.0e-30, float(v)) for _, v in ratio_rows]
    logs = [math.log10(v) for v in values]
    lo = min(logs)
    hi = max(logs)
    span = max(1.0, hi - lo)

    for idx, (_, value) in enumerate(ratio_rows):
        x0 = start_x + idx * (bar_w + gap)
        x1 = min(width - 25, x0 + bar_w)
        lv = math.log10(max(1.0e-30, float(value)))
        frac = (lv - lo) / span
        bar_h = int(round(frac * (height - 90)))
        y0 = height - 41 - bar_h
        y1 = height - 41
        color = colors[idx % len(colors)]
        for y in range(max(20, y0), y1):
            row = image[y]
            for x in range(max(51, x0), x1):
                row[x][0] = color[0]
                row[x][1] = color[1]
                row[x][2] = color[2]

    rows = [bytes(channel for pixel in row for channel in pixel) for row in image]
    _save_png_rgb(width=width, height=height, rows=rows, out_path=out_path)


def _induced_gravity_estimate(*, cutoff_gev: float, n_species: float, m_pl_reduced_gev: float) -> Dict[str, float]:
    pref = max(0.0, float(n_species)) / (12.0 * PI)
    m_pl_induced = math.sqrt(pref) * float(cutoff_gev)
    if m_pl_induced <= 0.0:
        g_ratio = float("inf")
        m_ratio = 0.0
    else:
        g_ratio = (float(m_pl_reduced_gev) / m_pl_induced) ** 2
        m_ratio = m_pl_induced / float(m_pl_reduced_gev)
    return {
        "m_pl_induced_gev": float(m_pl_induced),
        "m_pl_induced_over_observed": float(m_ratio),
        "g_induced_over_newton": float(g_ratio),
    }


def _vacuum_scaling(*, h0_km_s_mpc: float, omega_lambda: float, lambda_qcd_gev: float) -> Dict[str, float]:
    h0_si = float(h0_km_s_mpc) * 1000.0 / MPC_M
    h0_gev = h0_si * HBAR_GEV_S
    rho_qcd = h0_gev * (float(lambda_qcd_gev) ** 3)
    rho_crit = 3.0 * (h0_gev ** 2) * (MPL_REDUCED_GEV ** 2)
    rho_de = float(omega_lambda) * rho_crit
    ratio = rho_qcd / rho_de if rho_de > 0.0 else float("inf")
    required_suppression = ratio if ratio >= 1.0 else (1.0 / ratio if ratio > 0.0 else float("inf"))
    return {
        "h0_si_s_inv": float(h0_si),
        "h0_gev": float(h0_gev),
        "rho_qcd_h0_lambda3_gev4": float(rho_qcd),
        "rho_de_observed_gev4": float(rho_de),
        "ratio_qcd_to_rho_de": float(ratio),
        "required_suppression_factor_if_qcd_is_direct_source": float(required_suppression),
    }


def _kill_matrix_rows() -> List[Dict[str, str]]:
    return [
        {
            "check_id": "KT-001",
            "constraint_name": "MICROSCOPE Eotvos parameter",
            "applies_if": "epsilon induces composition-dependent fifth force without screening at lab scales",
            "bound_value": "1.0e-14",
            "bound_units": "eta",
            "status": "KILLED",
            "notes": "Any unscreened O(1e-6+) composition dependence is excluded.",
            "source_ref": "MICROSCOPE-2017",
        },
        {
            "check_id": "KT-002",
            "constraint_name": "Atomic clock drift",
            "applies_if": "epsilon_em mapped to physical d(alpha)/dt in local environment",
            "bound_value": "1.0e-17",
            "bound_units": "yr^-1",
            "status": "TENSION",
            "notes": "Strongly constrains direct time-varying-coupling interpretation.",
            "source_ref": "AtomicClocks-2021",
        },
        {
            "check_id": "KT-003",
            "constraint_name": "Oklo natural reactor",
            "applies_if": "same epsilon_em applies at geologic lookback with no screening",
            "bound_value": "1.0e-7",
            "bound_units": "|Delta alpha / alpha|",
            "status": "TENSION",
            "notes": "Model-dependent mapping from epsilon to alpha variation is required.",
            "source_ref": "Oklo-Review",
        },
        {
            "check_id": "KT-004",
            "constraint_name": "Lunar laser ranging",
            "applies_if": "epsilon_gr induces direct local dG/dt",
            "bound_value": "1.0e-13",
            "bound_units": "yr^-1",
            "status": "KILLED",
            "notes": "Unscreened local G variation is tightly bounded.",
            "source_ref": "LLR-Review",
        },
        {
            "check_id": "KT-005",
            "constraint_name": "BBN/CMB consistency",
            "applies_if": "epsilon modifies early-time expansion/recombination without compensating sector model",
            "bound_value": "order(1e-2)",
            "bound_units": "fractional",
            "status": "TENSION",
            "notes": "Requires explicit coupling model before any combined statement.",
            "source_ref": "Uzan-2011",
        },
        {
            "check_id": "KT-006",
            "constraint_name": "Cross-constraint combination",
            "applies_if": "single coupling model links all probes consistently",
            "bound_value": "N/A",
            "bound_units": "conditional",
            "status": "N-A",
            "notes": "Apples-vs-oranges otherwise; combined bounds are model-conditional.",
            "source_ref": "Martins-2017",
        },
        {
            "check_id": "KT-007",
            "constraint_name": "Inference-layer epsilon only",
            "applies_if": "epsilon treated strictly as measurement-model parameterization (no physical constant drift claim)",
            "bound_value": "N/A",
            "bound_units": "interpretation",
            "status": "PASS",
            "notes": "Within current roadmap framing this remains a valid working interpretation.",
            "source_ref": "Roadmap-v2.8",
        },
    ]


def _anomaly_rows() -> List[Dict[str, str]]:
    # Convention: dg/dln(mu) = (b_i / 16pi^2) g^3 in SM normalization.
    return [
        {
            "sector": "QED/U(1)_Y",
            "beta_coefficient": "+4.100000000000e+00",
            "sign": "positive",
            "comment": "Landau-like growth in UV for abelian coupling.",
        },
        {
            "sector": "EW/SU(2)_L",
            "beta_coefficient": "-3.166666666667e+00",
            "sign": "negative",
            "comment": "Asymptotically free trend in this convention.",
        },
        {
            "sector": "QCD/SU(3)_c",
            "beta_coefficient": "-7.000000000000e+00",
            "sign": "negative",
            "comment": "Asymptotic freedom; does not imply cosmological time-variation.",
        },
    ]


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate deterministic QCD<->gravity bridge sanity-check artifacts.")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--preset", choices=("ci_smoke", "paper_grade"), default="ci_smoke")
    ap.add_argument("--created-utc", type=int, default=DEFAULT_CREATED_UTC_EPOCH)
    ap.add_argument("--h0-km-s-mpc", type=float, default=67.4)
    ap.add_argument("--omega-lambda", type=float, default=0.685)
    ap.add_argument("--lambda-qcd-gev", type=float, default=0.2)
    ap.add_argument("--induced-cutoff-gev", type=float, default=0.3)
    ap.add_argument("--n-species", type=float, default=60.0)
    ap.add_argument("--emit-plot", type=int, choices=(0, 1), default=1)
    ap.add_argument("--format", choices=("json", "text"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        outdir = Path(str(args.outdir)).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        created_utc = _to_iso_utc(int(args.created_utc))
        induced = _induced_gravity_estimate(
            cutoff_gev=float(args.induced_cutoff_gev),
            n_species=float(args.n_species),
            m_pl_reduced_gev=MPL_REDUCED_GEV,
        )
        vac = _vacuum_scaling(
            h0_km_s_mpc=float(args.h0_km_s_mpc),
            omega_lambda=float(args.omega_lambda),
            lambda_qcd_gev=float(args.lambda_qcd_gev),
        )
        anomaly = _anomaly_rows()
        kill_rows = _kill_matrix_rows()

        kill_csv_path = outdir / "qcd_gravity_bridge_kill_matrix.csv"
        columns = [
            "check_id",
            "constraint_name",
            "applies_if",
            "bound_value",
            "bound_units",
            "status",
            "notes",
            "source_ref",
        ]
        with kill_csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            for row in sorted(kill_rows, key=lambda r: str(r["check_id"])):
                writer.writerow({k: str(row.get(k, "")) for k in columns})

        plot_path = outdir / "qcd_gravity_bridge_scale_plot.png"
        emitted_plot = False
        if int(args.emit_plot) == 1:
            ratio_rows = [
                ("rho_qcd/rho_de", max(1.0e-30, float(vac["ratio_qcd_to_rho_de"]))),
                (
                    "g_ind/g_newton",
                    max(1.0e-30, float(induced["g_induced_over_newton"])) if math.isfinite(float(induced["g_induced_over_newton"])) else 1.0e30,
                ),
                (
                    "suppression_needed",
                    max(1.0e-30, float(vac["required_suppression_factor_if_qcd_is_direct_source"])),
                ),
            ]
            _make_ratio_plot_fallback(ratio_rows=ratio_rows, out_path=plot_path)
            emitted_plot = True

        status_counts: Dict[str, int] = {}
        for row in kill_rows:
            key = str(row.get("status", "")).upper()
            status_counts[key] = status_counts.get(key, 0) + 1

        artifact_rows: List[Dict[str, Any]] = [
            {
                "filename": kill_csv_path.name,
                "sha256": _sha256_file(kill_csv_path),
                "bytes": int(kill_csv_path.stat().st_size),
            }
        ]
        if emitted_plot:
            artifact_rows.append(
                {
                    "filename": plot_path.name,
                    "sha256": _sha256_file(plot_path),
                    "bytes": int(plot_path.stat().st_size),
                }
            )

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "created_utc": created_utc,
            "preset": str(args.preset),
            "seed": int(args.seed),
            "paths_redacted": True,
            "non_claims": [
                "No claim that gravity equals the strong force.",
                "No claim that QCD alone explains M_Pl.",
                "No claim that RG beta-functions imply cosmic time variation.",
                "This artifact is an idea-bank plus kill-test sanity scaffold only.",
            ],
            "assumptions": {
                "induced_gravity_model": "Sakharov/Adler-Zee order-of-magnitude with explicit UV cutoff and species count.",
                "beta_convention": "dg/dln(mu)=(b_i/16pi^2)g^3",
                "vacuum_scaling_ansatz": "rho ~ H0 * Lambda_QCD^3",
                "mu_running_not_time_variation": "Any mu->t mapping is an external assumption (scale setting / background / screening).",
            },
            "constants": {
                "h0_km_s_mpc": float(args.h0_km_s_mpc),
                "omega_lambda": float(args.omega_lambda),
                "lambda_qcd_gev": float(args.lambda_qcd_gev),
                "induced_cutoff_gev": float(args.induced_cutoff_gev),
                "n_species": float(args.n_species),
                "m_pl_reduced_gev": MPL_REDUCED_GEV,
                "hbar_gev_s": HBAR_GEV_S,
            },
            "induced_gravity_sanity": {
                "m_pl_induced_gev": _fmt(induced["m_pl_induced_gev"]),
                "m_pl_induced_over_observed": _fmt(induced["m_pl_induced_over_observed"]),
                "g_induced_over_newton": _fmt(induced["g_induced_over_newton"]),
                "conclusion": "Under the stated assumptions, SM/QCD-scale cutoff is far too small to reproduce observed Planck scale.",
            },
            "trace_anomaly_sector_table": anomaly,
            "qcd_vacuum_scaling": {
                "h0_gev": _fmt(vac["h0_gev"]),
                "rho_qcd_h0_lambda3_gev4": _fmt(vac["rho_qcd_h0_lambda3_gev4"]),
                "rho_de_observed_gev4": _fmt(vac["rho_de_observed_gev4"]),
                "ratio_qcd_to_rho_de": _fmt(vac["ratio_qcd_to_rho_de"]),
                "required_suppression_factor_if_qcd_is_direct_source": _fmt(vac["required_suppression_factor_if_qcd_is_direct_source"]),
                "conclusion": "Naive scaling typically overshoots observed dark-energy density and needs model-dependent suppression.",
            },
            "kill_test_matrix": {
                "rows": kill_rows,
                "status_counts": status_counts,
                "model_conditionality_note": "Combined precision bounds are apples-vs-oranges without an explicit coupling model across probes.",
            },
            "mu_running_vs_time_variation_memo": [
                "RG running is defined against renormalization scale mu, not cosmological time t.",
                "A mu->t mapping requires extra assumptions: scale-setting rule, background dynamics, and screening/environment model.",
                "Therefore beta-function evidence alone is insufficient to claim observable temporal drift.",
            ],
            "artifacts": sorted(artifact_rows, key=lambda r: str(r["filename"])),
            "interpretation": "Supporting sanity-check bundle for reviewer triage; not a standalone unification claim.",
        }

        json_path = outdir / "qcd_gravity_bridge_numbers.json"
        json_text = _json_pretty(payload)
        if any(tok in json_text for tok in ABS_TOKENS):
            raise RuntimeError("JSON payload contains forbidden absolute-path token")
        json_path.write_text(json_text, encoding="utf-8")

        if str(args.format) == "json":
            print(json_text, end="")
        else:
            print(f"schema={SCHEMA}")
            print(f"preset={args.preset}")
            print(f"created_utc={created_utc}")
            print(f"m_pl_induced_gev={_fmt(induced['m_pl_induced_gev'])}")
            print(f"ratio_qcd_to_rho_de={_fmt(vac['ratio_qcd_to_rho_de'])}")
            print(f"kill_rows={len(kill_rows)}")
            print(f"artifacts={len(payload['artifacts']) + 1}")
        return 0

    except Exception as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
