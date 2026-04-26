#!/usr/bin/env python3
"""
predictions_compute_P7.py — compute Prediction P7 (GW-memory atomic-clock signature).

Computes the GSC-predicted permanent atomic-frequency shift in a globally-
distributed optical-lattice atomic-clock array following a binary-merger
GW event with measured GW-memory amplitude.

Physics:

The GW memory effect (Favata 2010, Class. Quant. Grav. 27, 084036) leaves a
permanent strain offset h_mem after the GW pulse. Through σ-coupling
(Section 6 of GSC_Framework.md), this couples to a permanent shift in
σ-equilibrium:

    δσ/σ = k_GW × h_mem

where k_GW is the σ-GW coupling strength (parametric until Paper B FRG
calculation supplies the derived value).

The atomic transition frequency depends on σ via the Rydberg constant
(under universal coherent scaling, atomic frequencies scale as σ^-1):

    δν/ν = -δσ/σ = -k_GW × h_mem

For typical binary-merger memory amplitudes h_mem ~ 10^-21 (for events at
~100 Mpc), and clock comparison precision ~10^-18 over relevant timescales,
the predicted signal is far below single-event detectability but may be
extracted via stacking over many events.

Usage:
    python3 scripts/predictions_compute_P7.py
    python3 scripts/predictions_compute_P7.py --k-gw 1.0 --h-mem 1e-21
    python3 scripts/predictions_compute_P7.py --output predictions_register/P7_gw_memory_clocks/pipeline_output.json

Output schema: predictions_p7_pipeline_output_v1.

Status: parametrized leading-order σ-GW coupling. The k_GW coupling is a
free parameter; FRG calculation in Paper B is gating piece for derivation.
The framework permits opportunistic analysis of existing atomic-clock
comparison time-series (ITOC, BACON) cross-correlated with LIGO/Virgo
trigger times.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# Representative GW-memory amplitudes (Favata 2010 + later work).
# These are *strain* amplitudes h_mem at Earth for typical events.
H_MEM_TYPICAL_EVENTS = {
    "GW150914-like (BBH ~30 Msun, 400 Mpc)": 5e-22,
    "GW170817-like (BNS ~1.4+1.4 Msun, 40 Mpc)": 1e-21,
    "Massive BBH (~50 Msun, 100 Mpc)": 5e-21,
    "Local SMBH (~10^6 Msun, 1 Mpc, hypothetical)": 1e-18,
}

# Modern optical-lattice clock instabilities (representative).
CLOCK_INSTABILITY_PER_TAU = {
    "Sr (1 sec)": 1e-15,
    "Sr (10000 sec, white-noise scaling)": 1e-17,
    "Yb+ (1 sec)": 5e-16,
    "Yb+ (10000 sec)": 5e-18,
    "Al+ (1 sec)": 8e-17,
    "Al+ (10000 sec)": 8e-19,
}

DEFAULTS = {
    "k_gw": 1.0,            # σ-GW coupling strength (parametric, dimensionless)
    "h_mem_default": 1e-21, # typical event amplitude
    "n_events_stacked": 100,
    "stacking_sqrt_n_gain": True,
}


def predicted_atomic_shift(*, h_mem: float, k_gw: float) -> dict:
    """Compute predicted δν/ν for one event with given memory amplitude."""
    delta_sigma_over_sigma = k_gw * h_mem
    delta_nu_over_nu = -delta_sigma_over_sigma
    return {
        "h_mem_strain": float(f"{h_mem:.3e}"),
        "k_gw_coupling": float(k_gw),
        "delta_sigma_over_sigma": float(f"{delta_sigma_over_sigma:.3e}"),
        "delta_nu_over_nu_predicted": float(f"{delta_nu_over_nu:.3e}"),
    }


def detectability_assessment(
    *,
    delta_nu_over_nu: float,
    n_events: int,
    sqrt_n_gain: bool,
) -> dict:
    """Compare predicted signal to clock-array detection capability."""
    if sqrt_n_gain and n_events > 0:
        stacked_signal = abs(delta_nu_over_nu) * (n_events ** 0.5)
        stacking_factor = float(n_events ** 0.5)
    else:
        stacked_signal = abs(delta_nu_over_nu)
        stacking_factor = 1.0

    detection_targets = {}
    for label, sigma in CLOCK_INSTABILITY_PER_TAU.items():
        detection_targets[label] = {
            "instability": float(f"{sigma:.3e}"),
            "snr_single_event": float(f"{abs(delta_nu_over_nu) / sigma:.3e}"),
            "snr_stacked": float(f"{stacked_signal / sigma:.3e}"),
            "detectable_at_3sigma_stacked": stacked_signal > 3.0 * sigma,
        }

    return {
        "n_events_stacked": n_events,
        "sqrt_n_gain_assumed": sqrt_n_gain,
        "stacking_factor": stacking_factor,
        "stacked_signal_abs": float(f"{stacked_signal:.3e}"),
        "detection_targets": detection_targets,
    }


def make_record(
    *,
    k_gw: float,
    h_mem: float,
    n_events: int,
    sqrt_n_gain: bool,
) -> dict:
    main_event = predicted_atomic_shift(h_mem=h_mem, k_gw=k_gw)
    detectability = detectability_assessment(
        delta_nu_over_nu=main_event["delta_nu_over_nu_predicted"],
        n_events=n_events,
        sqrt_n_gain=sqrt_n_gain,
    )

    survey = {}
    for label, h in sorted(H_MEM_TYPICAL_EVENTS.items()):
        survey[label] = predicted_atomic_shift(h_mem=h, k_gw=k_gw)

    return {
        "schema": "predictions_p7_pipeline_output_v1",
        "prediction_id": "P7",
        "title": "GW-memory-induced atomic-clock-array signature",
        "tier": "T4",
        "tool": "predictions_compute_P7",
        "tool_version": "v0.1-parametric-coupling",
        "physics_status": (
            "Leading-order σ-GW coupling (k_GW parametric until FRG-derived). "
            "Predicted permanent atomic-frequency shift δν/ν = -k_GW × h_mem "
            "after each merger event with GW-memory amplitude h_mem. Stacking "
            "over multiple events gains √N factor."
        ),
        "registered_couplings": {
            "k_gw": float(k_gw),
            "h_mem_default_strain": float(f"{h_mem:.3e}"),
        },
        "main_event_prediction": main_event,
        "detectability_assessment": detectability,
        "event_amplitude_survey": survey,
        "analysis_strategy": {
            "data_source": (
                "Existing atomic-clock comparison time-series (ITOC, BACON, "
                "NICT-PTB-NIST), correlated with LIGO/Virgo public trigger times "
                "from the GraceDB and gw-openscience catalogs."
            ),
            "trigger_window": "post-merger ±100 s",
            "scoring_method": (
                "Cross-correlate predicted (δν/ν) signal at each station against "
                "the post-merger residuals; stack over events with significance "
                "weighting by registered h_mem; extract combined detection or "
                "upper limit."
            ),
        },
        "determinism_note": (
            "This file intentionally contains no timestamp; SHA-256 is a function "
            "only of the registered inputs."
        ),
    }


def write_output(record: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    output_path.write_text(text, encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sys.stdout.write(f"wrote {output_path}\n  SHA-256: {sha}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--k-gw",
        type=float,
        default=DEFAULTS["k_gw"],
        help="σ-GW coupling strength (dimensionless, default 1.0)",
    )
    parser.add_argument(
        "--h-mem",
        type=float,
        default=DEFAULTS["h_mem_default"],
        help="GW memory strain amplitude for the main event (default 1e-21)",
    )
    parser.add_argument(
        "--n-events",
        type=int,
        default=DEFAULTS["n_events_stacked"],
        help="number of events for stacking analysis (default 100)",
    )
    parser.add_argument(
        "--no-sqrt-n",
        action="store_true",
        help="disable √N stacking gain (use single-event sensitivity only)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P7_gw_memory_clocks"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        k_gw=args.k_gw,
        h_mem=args.h_mem,
        n_events=args.n_events,
        sqrt_n_gain=not args.no_sqrt_n,
    )

    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")

    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
