#!/usr/bin/env python3
"""Phase 2 E2 closure scan harness.

Reproducibly scan late-time history parameters against two constraints:
- CMB compressed-prior chi2
- optional positive-drift condition over z in [z_min, z_max]

This is a lightweight diagnostic harness; it is not a full CMB likelihood.
"""

from __future__ import annotations

import argparse
import copy
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import random
import sys
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from _outdir import resolve_outdir

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.bbn.priors import (  # noqa: E402
    BBN_PRIOR_MODES,
    canonical_bbn_prior_mode,
    evaluate_bbn_prior_chi2,
)
from gsc.early_time import early_time_params_from_namespace  # noqa: E402
from gsc.early_time.cmb_microphysics_knobs import (  # noqa: E402
    KNOB_SPECS,
    MicrophysicsKnobs,
    assess_knobs as assess_microphysics_knobs,
    knobs_from_dict as microphysics_knobs_from_dict,
    knobs_to_dict as microphysics_knobs_to_dict,
    validate_knobs as validate_microphysics_knobs,
)
from gsc.early_time.refine_plan_v1 import (  # noqa: E402
    get_plan_source_sha256 as refine_plan_source_sha256,
    iter_plan_points as iter_refine_plan_points,
    load_refine_plan_v1,
)
from gsc.early_time.cmb_priors_driver import CMBPriorsDriverConfig, evaluate_cmb_priors_dataset  # noqa: E402
from gsc.early_time.e2_deformations import (  # noqa: E402
    DEFAULT_BUMP_Z_HI,
    DEFAULT_BUMP_Z_LO,
    DEFAULT_DIP_Z_HI,
    DEFAULT_DIP_Z_LO,
    DEFAULT_FACTOR_FLOOR,
    DEFAULT_WINDOW_W,
    DipBumpWindowDeformation,
    LogHTwoWindowDeformation,
    SPL4_DLOGH_MAX,
    SPL4_DLOGH_MIN,
    Spline4LogHDeformation,
)
from gsc.early_time.numerics_invariants import run_early_time_invariants  # noqa: E402
from gsc.fit import iter_param_grid, parse_grid_spec  # noqa: E402
from gsc.jsonl_io import open_text_auto  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    C_SI,
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
    delta_v_cm_s,
    z_dot_sandage_loeb,
)
from gsc.optional_deps import require_numpy  # noqa: E402
from gsc.search_sampling import (  # noqa: E402
    AdaptiveRWMHSampler,
    halton_bases,
    iter_halton_points,
    iter_lhs_points,
    iter_random_points,
    run_metropolis_hastings,
)
from gsc.search_optimize import nelder_mead_minimize  # noqa: E402
from gsc.structure.rsd_overlay import rsd_overlay_for_e2_record  # noqa: E402


_CHW2018_PREFIX = "planck2018_distance_priors_chw2018_"
DEFAULT_RSD_DATA_PATH = V101_DIR / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"

_MODEL_KEYS: Dict[str, Tuple[str, ...]] = {
    "lcdm": ("H0", "Omega_m"),
    "gsc_powerlaw": ("H0", "p"),
    "gsc_transition": ("H0", "Omega_m", "p", "z_transition"),
    "dip_bump_window": ("H0", "Omega_m", "A_dip", "A_bump"),
    "logh_two_window": ("H0", "Omega_m", "tw1_zc", "tw1_w", "tw1_a", "tw2_zc", "tw2_w", "tw2_a"),
    "spline4_logh": ("H0", "Omega_m", "spl4_dlogh_z3", "spl4_dlogh_z30", "spl4_dlogh_z300", "spl4_dlogh_z1100"),
}

_EARLY_SCAN_KEYS: Tuple[str, ...] = ("omega_b_h2", "omega_c_h2", "N_eff", "Y_p")
_MICROPHYSICS_SCAN_KEYS: Tuple[str, ...] = ("z_star_scale", "r_s_scale", "r_d_scale")
_PRIOR_ALLOWED_KEYS = frozenset(_EARLY_SCAN_KEYS)
_DIP_BUMP_PARAM_BOUNDS: Dict[str, Tuple[float, float]] = {
    "A_dip": (0.0, 0.95),
    "A_bump": (0.0, 5.0),
}
_TWO_WINDOW_PARAM_BOUNDS: Dict[str, Tuple[float, float]] = {
    "tw1_zc": (1.5, 8.0),
    "tw1_w": (0.05, 0.80),
    "tw1_a": (-1.0, 1.0),
    "tw2_zc": (50.0, 2000.0),
    "tw2_w": (0.05, 1.50),
    "tw2_a": (-1.0, 1.0),
}
_SPLINE4_LOGH_PARAM_BOUNDS: Dict[str, Tuple[float, float]] = {
    "spl4_dlogh_z3": (SPL4_DLOGH_MIN, SPL4_DLOGH_MAX),
    "spl4_dlogh_z30": (SPL4_DLOGH_MIN, SPL4_DLOGH_MAX),
    "spl4_dlogh_z300": (SPL4_DLOGH_MIN, SPL4_DLOGH_MAX),
    "spl4_dlogh_z1100": (SPL4_DLOGH_MIN, SPL4_DLOGH_MAX),
}
_DRIFT_PRECHECK_CHOICES: Tuple[str, ...] = ("none", "z2_5_positive", "z2_5_negative")
_DRIFT_PRECHECK_Z_NODES: Tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)
_OPTIMIZE_CHOICES: Tuple[str, ...] = ("none", "nelder_mead")
_OPT_MULTISTART_INIT_CHOICES: Tuple[str, ...] = ("latin_hypercube", "random", "grid")
_CHI2_SENTINEL = 1.0e99
_OPT_OBJECTIVE_BIG = 1.0e30
_OPT_TOY_MAX_EVAL_CAP = 60
_SCAN_CONFIG_SCHEMA = "phase2_e2_scan_config_v1"
_SCAN_CONFIG_VOLATILE_KEYS: frozenset[str] = frozenset(
    {
        "out_dir",
        "points_jsonl_name",
        "resume",
        "resume_mode",
        "jobs",
        "dry_run",
        "plan_slice",
    }
)
_SCAN_CONFIG_PATH_KEYS: frozenset[str] = frozenset(
    {
        "plan",
        "cmb",
        "cmb_cov",
        "bounds_json",
        "seed_points_jsonl",
        "out_dir",
        "rsd_data",
    }
)
_SCAN_CONFIG_SORTED_LIST_KEYS: frozenset[str] = frozenset(
    {
        "grid",
        "gaussian_prior",
        "step_scale",
    }
)
_SCAN_CONFIG_RSD_KEYS: frozenset[str] = frozenset(
    {
        "rsd_overlay",
        "rsd_data",
        "rsd_ap_correction",
        "rsd_mode",
        "rsd_transfer_model",
        "rsd_ns",
        "rsd_k_pivot",
        "rsd_chi2_field",
        "rsd_chi2_weight",
    }
)
_SCAN_CONFIG_OPT_KEYS: frozenset[str] = frozenset(
    {
        "opt_multistart",
        "opt_init",
        "opt_seed",
    }
)
_SCAN_CONFIG_BBN_KEYS: frozenset[str] = frozenset(
    {
        "bbn_prior",
    }
)

_RSD_CHI2_FIELD_PRIORITY: Tuple[str, ...] = (
    "rsd_chi2_total",
    "rsd_chi2",
    "rsd_chi2_min",
)

_OPT_COMMON_PARAM_BOUNDS: Dict[str, Tuple[float, float]] = {
    "H0": (40.0, 100.0),
    "Omega_m": (0.05, 0.95),
    "p": (0.05, 2.50),
    "z_transition": (0.0, 20.0),
    "omega_b_h2": (0.005, 0.040),
    "omega_c_h2": (0.020, 0.300),
    "N_eff": (1.0, 6.0),
    "Y_p": (0.0, 0.5),
}

_REQUIRED_CSV_COLUMNS: Tuple[str, ...] = (
    "model",
    "deformation_family",
    "chi2_cmb",
    "drift_pass",
    "H0",
    "Omega_m",
    "p",
    "z_transition",
    "A_dip",
    "A_bump",
    "tw1_zc",
    "tw1_w",
    "tw1_a",
    "tw2_zc",
    "tw2_w",
    "tw2_a",
    "spl4_dlogh_z3",
    "spl4_dlogh_z30",
    "spl4_dlogh_z300",
    "spl4_dlogh_z1100",
    "dip_zlo",
    "dip_zhi",
    "bump_zlo",
    "bump_zhi",
    "window_w",
    "microphysics_mode",
    "z_star_scale",
    "r_s_scale",
    "r_d_scale",
    "microphysics_plausible_ok",
    "microphysics_penalty",
    "microphysics_max_rel_dev",
    "cmb_bridge_z",
    "theta_star",
    "lA",
    "R",
    "z_star",
    "r_s_star_Mpc",
    "D_M_star_Mpc",
    "bridge_H_ratio",
    "recombination_method",
    "recomb_converged",
    "drag_method",
    "cmb_num_method",
    "cmb_num_n_eval_dm",
    "cmb_num_err_dm",
    "cmb_num_n_eval_rs",
    "cmb_num_err_rs",
    "cmb_num_n_eval_rs_drag",
    "cmb_num_err_rs_drag",
    "cmb_num_rtol",
    "cmb_num_atol",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_chw2018_distance_priors_csv(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith(_CHW2018_PREFIX) and name.endswith(".csv")


def _require_numpy_or_die():
    try:
        return require_numpy()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def _sha256_file(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    p = path.expanduser().resolve()
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_scan_config_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value.expanduser().resolve())
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return float(value)
    if isinstance(value, Mapping):
        return {
            str(k): _normalize_scan_config_value(value[k])
            for k in sorted(str(x) for x in value.keys())
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_scan_config_value(v) for v in value]
    return str(value)


def _build_scan_config_payload(
    *,
    args: argparse.Namespace,
    plan_source_sha256: Optional[str],
    rsd_data_sha256: Optional[str],
    rsd_data_id: str,
    rsd_overlay_settings: Mapping[str, Any],
) -> Tuple[Dict[str, Any], str]:
    raw = vars(args)
    config: Dict[str, Any] = {
        "scan_config_schema": _SCAN_CONFIG_SCHEMA,
        "plan_source_sha256": (
            str(plan_source_sha256).strip()
            if isinstance(plan_source_sha256, str) and str(plan_source_sha256).strip()
            else None
        ),
    }
    for key in sorted(str(k) for k in raw.keys()):
        if key in _SCAN_CONFIG_VOLATILE_KEYS:
            continue
        if key in _SCAN_CONFIG_PATH_KEYS:
            continue
        if key in _SCAN_CONFIG_RSD_KEYS:
            continue
        if key in _SCAN_CONFIG_OPT_KEYS:
            continue
        if key in _SCAN_CONFIG_BBN_KEYS:
            continue
        value = _normalize_scan_config_value(raw.get(key))
        if key in _SCAN_CONFIG_SORTED_LIST_KEYS and isinstance(value, list):
            value = sorted(str(v) for v in value)
        config[str(key)] = value
    chi2_objective = str(getattr(args, "chi2_objective", "cmb")).strip().lower()
    config["opt_objective_key"] = _effective_opt_objective_key(
        chi2_objective=chi2_objective,
        requested_key=str(getattr(args, "opt_objective_key", "chi2_total")),
    )
    config["input_sha256"] = {
        "cmb": _sha256_file(None if args.cmb is None else Path(args.cmb).expanduser().resolve()),
        "cmb_cov": _sha256_file(None if args.cmb_cov is None else Path(args.cmb_cov).expanduser().resolve()),
        "bounds_json": _sha256_file(None if args.bounds_json is None else Path(args.bounds_json).expanduser().resolve()),
        "seed_points_jsonl": _sha256_file(
            None if args.seed_points_jsonl is None else Path(args.seed_points_jsonl).expanduser().resolve()
        ),
        "rsd_data": str(rsd_data_sha256) if bool(args.rsd_overlay) and rsd_data_sha256 else None,
    }
    rsd_enabled = bool(rsd_overlay_settings.get("enabled", False))
    rsd_effective: Dict[str, Any] = {
        "enabled": bool(rsd_enabled),
        "ap_correction": None,
        "mode": None,
        "helper_mode": None,
    }
    if rsd_enabled:
        rsd_effective["ap_correction"] = str(rsd_overlay_settings.get("ap_mode", "none"))
        rsd_effective["mode"] = str(rsd_overlay_settings.get("scan_mode", "profile_sigma8_0"))
        rsd_effective["helper_mode"] = str(rsd_overlay_settings.get("helper_mode", "nuisance_sigma8"))
    if rsd_enabled and bool(
        rsd_overlay_settings.get("uses_primordial_knobs", False)
    ):
        rsd_effective["transfer_model"] = str(rsd_overlay_settings.get("transfer_model", "bbks"))
        rsd_effective["primordial_ns"] = _finite_float(rsd_overlay_settings.get("primordial_ns"))
        rsd_effective["primordial_k_pivot_mpc"] = _finite_float(
            rsd_overlay_settings.get("primordial_k_pivot_mpc")
        )
    else:
        rsd_effective["transfer_model"] = None
        rsd_effective["primordial_ns"] = None
        rsd_effective["primordial_k_pivot_mpc"] = None
    config["rsd_overlay_effective"] = rsd_effective
    config["rsd_data_id"] = str(rsd_data_id) if bool(args.rsd_overlay) else None
    rsd_chi2_field_raw = str(getattr(args, "rsd_chi2_field", "")).strip()
    rsd_chi2_weight = _finite_float(getattr(args, "rsd_chi2_weight", 1.0))
    config["chi2_objective_effective"] = {
        "mode": "joint" if chi2_objective == "joint" else "cmb",
        "rsd_chi2_field": (
            rsd_chi2_field_raw if rsd_chi2_field_raw else "auto"
        )
        if chi2_objective == "joint"
        else None,
        "rsd_chi2_weight": (
            float(rsd_chi2_weight) if rsd_chi2_weight is not None else 1.0
        )
        if chi2_objective == "joint"
        else None,
    }
    optimize_mode = str(getattr(args, "optimize", "none")).strip().lower()
    opt_multistart = int(getattr(args, "opt_multistart", 1))
    if optimize_mode == "nelder_mead":
        config["opt_multistart_effective"] = {
            "enabled": bool(opt_multistart > 1),
            "k": int(opt_multistart),
            "init": (
                str(getattr(args, "opt_init", "random")).strip().lower()
                if opt_multistart > 1
                else None
            ),
            "seed": (
                int(getattr(args, "opt_seed", 0))
                if opt_multistart > 1
                else None
            ),
        }
    bbn_prior_mode = str(getattr(args, "bbn_prior", "none")).strip().lower()
    if bbn_prior_mode != "none":
        config["bbn_prior_effective"] = str(bbn_prior_mode)
    config_safe = _to_json_safe(config)
    canonical = json.dumps(config_safe, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return config_safe, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _scan_config_sidecar_path(points_jsonl: Path) -> Path:
    return Path(str(points_jsonl) + ".scan_config.json")


def _write_scan_config_sidecar(
    *,
    points_jsonl: Path,
    scan_config: Mapping[str, Any],
    scan_config_sha256: str,
) -> None:
    payload = {
        "schema": _SCAN_CONFIG_SCHEMA,
        "scan_config_sha256": str(scan_config_sha256),
        "scan_config": _to_json_safe(scan_config),
    }
    sidecar = _scan_config_sidecar_path(points_jsonl)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_grid_kv(items: Sequence[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in items:
        text = str(raw).strip()
        if not text:
            continue
        if "=" not in text:
            raise SystemExit(f"Invalid --grid entry {text!r}; expected KEY=SPEC")
        key, spec = text.split("=", 1)
        key = key.strip()
        spec = spec.strip()
        if not key or not spec:
            raise SystemExit(f"Invalid --grid entry {text!r}; expected KEY=SPEC")
        if key in out:
            raise SystemExit(f"Duplicate --grid key: {key}")
        out[key] = spec
    return out


def _validate_grid_specs_for_model(*, model_name: str, grid_specs: Mapping[str, str]) -> None:
    model_bounds: Optional[Mapping[str, Tuple[float, float]]] = None
    if model_name == "dip_bump_window":
        model_bounds = _DIP_BUMP_PARAM_BOUNDS
    elif model_name == "logh_two_window":
        model_bounds = _TWO_WINDOW_PARAM_BOUNDS
    elif model_name == "spline4_logh":
        model_bounds = _SPLINE4_LOGH_PARAM_BOUNDS
    if model_bounds is None:
        return
    for key, (lo, hi) in sorted(model_bounds.items()):
        spec = grid_specs.get(key)
        if spec is None:
            continue
        if ":" in str(spec):
            # In non-grid samplers this is min:max and validated in _build_sampling_bounds.
            parts = [p.strip() for p in str(spec).split(":")]
            if len(parts) == 2:
                continue
        try:
            values = parse_grid_spec(spec)
        except Exception:
            # Let existing parser errors surface in grid iteration.
            continue
        for value in values:
            vv = float(value)
            if vv < float(lo) or vv > float(hi):
                raise SystemExit(f"{key}={vv} is outside supported range [{lo}, {hi}] for {model_name}")


def _split_param_keys(
    *,
    model_name: str,
    grid_specs: Mapping[str, str],
    microphysics_mode: str,
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    needed = _MODEL_KEYS[model_name]
    allowed = set(needed) | set(_EARLY_SCAN_KEYS)
    if str(microphysics_mode) == "knobs":
        allowed |= set(_MICROPHYSICS_SCAN_KEYS)
    extras = sorted(k for k in grid_specs.keys() if k not in allowed)
    if extras:
        raise SystemExit(f"Unsupported --grid keys for model {model_name}: {extras}")
    missing = [k for k in needed if k not in grid_specs]
    if missing:
        raise SystemExit(f"Missing --grid specs for model {model_name}: {missing}")
    early_scan = tuple(k for k in _EARLY_SCAN_KEYS if k in grid_specs)
    micro_scan = tuple(k for k in _MICROPHYSICS_SCAN_KEYS if k in grid_specs)
    return needed, early_scan, micro_scan


def _parse_range_spec(spec: str) -> Tuple[float, float]:
    parts = [p.strip() for p in str(spec).split(":")]
    if len(parts) != 2:
        raise SystemExit(f"Sampling range expects min:max, got {spec!r}")
    lo, hi = float(parts[0]), float(parts[1])
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise SystemExit(f"Non-finite sampling range: {spec!r}")
    if hi < lo:
        raise SystemExit(f"Invalid sampling range (hi < lo): {spec!r}")
    return float(lo), float(hi)


def _parse_step_scale_kv(items: Sequence[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for raw in items:
        text = str(raw).strip()
        if not text:
            continue
        if "=" not in text:
            raise SystemExit(f"Invalid --step-scale entry {text!r}; expected KEY=VALUE")
        key, value = text.split("=", 1)
        key = key.strip()
        try:
            scale = float(value.strip())
        except Exception as exc:
            raise SystemExit(f"Invalid --step-scale value in {text!r}") from exc
        if key in out:
            raise SystemExit(f"Duplicate --step-scale key: {key}")
        if not (math.isfinite(scale) and scale > 0.0):
            raise SystemExit(f"--step-scale for {key!r} must be finite and > 0")
        out[key] = scale
    return out


def _parse_gaussian_priors(items: Sequence[str]) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {}
    for raw in items:
        text = str(raw).strip()
        if not text:
            continue
        if "=" not in text:
            raise SystemExit(f"Invalid --gaussian-prior entry {text!r}; expected NAME=MU,SIGMA")
        key, rest = text.split("=", 1)
        key = key.strip()
        if key not in _PRIOR_ALLOWED_KEYS:
            allowed = ", ".join(sorted(_PRIOR_ALLOWED_KEYS))
            raise SystemExit(f"Unsupported --gaussian-prior key {key!r}; allowed keys: {allowed}")
        pair = [p.strip() for p in rest.split(",")]
        if len(pair) != 2:
            raise SystemExit(f"Invalid --gaussian-prior entry {text!r}; expected NAME=MU,SIGMA")
        try:
            mu = float(pair[0])
            sigma = float(pair[1])
        except Exception as exc:
            raise SystemExit(f"Invalid --gaussian-prior entry {text!r}; MU/SIGMA must be floats") from exc
        if not (math.isfinite(mu) and math.isfinite(sigma) and sigma > 0.0):
            raise SystemExit(f"Invalid --gaussian-prior entry {text!r}; require finite MU and SIGMA>0")
        if key in out:
            raise SystemExit(f"Duplicate --gaussian-prior key: {key}")
        out[key] = (float(mu), float(sigma))
    return out


def _parse_drift_z_list(spec: str) -> List[float]:
    out: List[float] = []
    for part in str(spec).split(","):
        text = part.strip()
        if not text:
            continue
        try:
            z = float(text)
        except Exception as exc:
            raise SystemExit(f"Invalid --drift-z-list entry {text!r}") from exc
        if not math.isfinite(z) or z < 0.0:
            raise SystemExit(f"--drift-z-list values must be finite and >= 0 (got {text!r})")
        out.append(float(z))
    if not out:
        raise SystemExit("--drift-z-list must contain at least one redshift")
    return sorted(set(out))


def _is_mcmc_sampler(name: str) -> bool:
    return str(name) in {"mh", "mh_adaptive"}


def _effective_resume_mode(*, sampler: str, requested: Optional[str]) -> str:
    if requested in {"dedupe", "cache"}:
        return str(requested)
    return "cache" if _is_mcmc_sampler(str(sampler)) else "dedupe"


def _microphysics_bounds_from_namespace(ns: argparse.Namespace) -> Dict[str, Tuple[float, float]]:
    bounds = {
        "z_star_scale": (float(ns.z_star_scale_min), float(ns.z_star_scale_max)),
        "r_s_scale": (float(ns.r_s_scale_min), float(ns.r_s_scale_max)),
        "r_d_scale": (float(ns.r_d_scale_min), float(ns.r_d_scale_max)),
    }
    for key, (lo, hi) in sorted(bounds.items()):
        if not (math.isfinite(float(lo)) and math.isfinite(float(hi))):
            raise SystemExit(f"--{key.replace('_', '-')} bounds must be finite")
        if float(lo) <= 0.0 or float(hi) <= 0.0:
            raise SystemExit(f"--{key.replace('_', '-')} bounds must be > 0")
        if float(hi) < float(lo):
            raise SystemExit(f"--{key.replace('_', '-')} max must be >= min")
        try:
            validate_microphysics_knobs({key: float(lo)}, reason_prefix="scan microphysics bounds")
            validate_microphysics_knobs({key: float(hi)}, reason_prefix="scan microphysics bounds")
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    return bounds


def _microphysics_scales_from_params(*, params: Mapping[str, float], mode: str) -> Dict[str, float]:
    if str(mode) == "none":
        scales = microphysics_knobs_to_dict(MicrophysicsKnobs())
    else:
        knobs = MicrophysicsKnobs(
            z_star_scale=float(params.get("z_star_scale", 1.0)),
            r_s_scale=float(params.get("r_s_scale", 1.0)),
            r_d_scale=float(params.get("r_d_scale", 1.0)),
        )
        scales = microphysics_knobs_to_dict(knobs)
    validate_microphysics_knobs(scales, reason_prefix="scan microphysics")
    return {k: float(v) for k, v in scales.items()}


def _microphysics_payload_and_audit(*, scales: Mapping[str, float], mode: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    normalized = microphysics_knobs_to_dict(microphysics_knobs_from_dict(scales))
    audit = assess_microphysics_knobs(normalized)
    payload = {
        "mode": "none" if str(mode) == "none" else "knobs",
        "z_star_scale": float(normalized["z_star_scale"]),
        "r_s_scale": float(normalized["r_s_scale"]),
        "r_d_scale": float(normalized["r_d_scale"]),
    }
    report = {
        "microphysics_knobs": dict(normalized),
        "microphysics_hard_ok": bool(audit.get("hard_ok", False)),
        "microphysics_plausible_ok": bool(audit.get("plausible_ok", False)),
        "microphysics_penalty": float(audit.get("penalty", 0.0)),
        "microphysics_max_rel_dev": float(audit.get("max_rel_dev", 0.0)),
        "microphysics_notes": [str(v) for v in (audit.get("notes") or [])],
    }
    return payload, report


def _load_bounds_overrides(path: Optional[Path]) -> Tuple[Optional[Dict[str, Tuple[float, float]]], Optional[Path]]:
    if path is None:
        return None, None
    rp = path.expanduser().resolve()
    if not rp.is_file():
        raise SystemExit(f"--bounds-json file not found: {rp}")
    try:
        payload = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse --bounds-json: {rp}") from exc
    raw_bounds = payload.get("bounds") if isinstance(payload, Mapping) and isinstance(payload.get("bounds"), Mapping) else payload
    if not isinstance(raw_bounds, Mapping):
        raise SystemExit("--bounds-json must be an object or contain object field 'bounds'")

    out: Dict[str, Tuple[float, float]] = {}
    for key in sorted(str(k) for k in raw_bounds.keys()):
        raw = raw_bounds[key]
        lo: Optional[float] = None
        hi: Optional[float] = None
        if isinstance(raw, Mapping):
            lo = _finite_float(raw.get("min"))
            hi = _finite_float(raw.get("max"))
        elif isinstance(raw, (list, tuple)) and len(raw) == 2:
            lo = _finite_float(raw[0])
            hi = _finite_float(raw[1])
        if lo is None or hi is None:
            raise SystemExit(f"--bounds-json invalid entry for {key!r}; expected {{min,max}} or [min,max]")
        if not (math.isfinite(lo) and math.isfinite(hi) and hi > lo):
            raise SystemExit(f"--bounds-json invalid range for {key!r}; require finite min<max")
        out[str(key)] = (float(lo), float(hi))
    return out, rp


def _apply_bounds_overrides(
    base: Mapping[str, Tuple[float, float]],
    overrides: Optional[Mapping[str, Tuple[float, float]]],
) -> Dict[str, Tuple[float, float]]:
    merged = {str(k): (float(v[0]), float(v[1])) for k, v in sorted(base.items())}
    if not overrides:
        return merged
    for key, (lo, hi) in sorted(overrides.items()):
        if key not in merged:
            raise SystemExit(f"--bounds-json contains unknown parameter {key!r}")
        base_lo, base_hi = merged[key]
        if float(lo) < float(base_lo) or float(hi) > float(base_hi):
            raise SystemExit(
                f"--bounds-json override for {key!r} must stay within scan bounds [{base_lo}, {base_hi}]"
            )
        if not (math.isfinite(float(lo)) and math.isfinite(float(hi)) and float(hi) > float(lo)):
            raise SystemExit(f"--bounds-json invalid override for {key!r}; require finite min<max")
        merged[key] = (float(lo), float(hi))
    return merged


def _load_seed_points(path: Optional[Path]) -> Tuple[List[Dict[str, Any]], Optional[Path]]:
    if path is None:
        return [], None
    rp = path.expanduser().resolve()
    if not rp.is_file():
        raise SystemExit(f"--seed-points-jsonl file not found: {rp}")
    out: List[Dict[str, Any]] = []
    with rp.open("r", encoding="utf-8") as fh:
        for idx, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception as exc:
                raise SystemExit(f"--seed-points-jsonl has invalid JSON at line {idx}") from exc
            if not isinstance(payload, Mapping):
                raise SystemExit(f"--seed-points-jsonl line {idx} must be a JSON object")
            raw_params = payload.get("params", payload)
            if not isinstance(raw_params, Mapping):
                raise SystemExit(f"--seed-points-jsonl line {idx} missing object 'params'")
            params: Dict[str, float] = {}
            for key in sorted(str(k) for k in raw_params.keys()):
                fv = _finite_float(raw_params[key])
                if fv is None:
                    continue
                params[str(key)] = float(fv)
            if not params:
                continue
            out.append(
                {
                    "params": params,
                    "source_line": int(idx),
                    "source_file": str(rp),
                }
            )
    return out, rp


def _build_sampling_bounds(
    *,
    model_name: str,
    grid_specs: Mapping[str, str],
    microphysics_mode: str,
    microphysics_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
) -> Dict[str, Tuple[float, float]]:
    needed, early_scan, micro_scan = _split_param_keys(
        model_name=model_name,
        grid_specs=grid_specs,
        microphysics_mode=microphysics_mode,
    )
    keys = tuple(needed) + tuple(early_scan) + tuple(micro_scan)
    bounds = {k: _parse_range_spec(grid_specs[k]) for k in keys}
    if str(microphysics_mode) == "knobs":
        if microphysics_bounds is None:
            raise SystemExit("Internal error: microphysics bounds missing for microphysics=knobs")
        for key in _MICROPHYSICS_SCAN_KEYS:
            if key in bounds:
                continue
            lo, hi = microphysics_bounds[key]
            bounds[key] = (float(lo), float(hi))
    model_bounds: Optional[Mapping[str, Tuple[float, float]]] = None
    if model_name == "dip_bump_window":
        model_bounds = _DIP_BUMP_PARAM_BOUNDS
    elif model_name == "logh_two_window":
        model_bounds = _TWO_WINDOW_PARAM_BOUNDS
    elif model_name == "spline4_logh":
        model_bounds = _SPLINE4_LOGH_PARAM_BOUNDS
    if model_bounds is not None:
        for key, (allowed_lo, allowed_hi) in sorted(model_bounds.items()):
            if key not in bounds:
                continue
            lo, hi = bounds[key]
            if lo < float(allowed_lo) or hi > float(allowed_hi):
                raise SystemExit(
                    f"{key} scan bounds [{lo}, {hi}] exceed supported range [{allowed_lo}, {allowed_hi}] "
                    f"for {model_name}"
                )
    return bounds


def _iter_param_points_grid(
    *,
    model_name: str,
    grid_specs: Mapping[str, str],
    microphysics_mode: str,
) -> Iterator[Dict[str, float]]:
    needed, early_scan, micro_scan = _split_param_keys(
        model_name=model_name,
        grid_specs=grid_specs,
        microphysics_mode=microphysics_mode,
    )
    keys = tuple(needed) + tuple(early_scan) + tuple(micro_scan)
    grid = {k: parse_grid_spec(grid_specs[k]) for k in keys}
    if str(microphysics_mode) == "knobs":
        for key in _MICROPHYSICS_SCAN_KEYS:
            if key in grid:
                continue
            grid[key] = [1.0]
    yield from iter_param_grid(grid)


class _CallableHistory:
    def __init__(self, fn):
        self._fn = fn

    def H(self, z: float) -> float:
        return float(self._fn(float(z)))


def _dip_bump_hyperparams_from_namespace(ns: argparse.Namespace) -> Dict[str, float]:
    out = {
        "z_dip_lo": float(ns.dip_zlo),
        "z_dip_hi": float(ns.dip_zhi),
        "z_bump_lo": float(ns.bump_zlo),
        "z_bump_hi": float(ns.bump_zhi),
        "w": float(ns.window_w),
        "factor_floor": float(ns.factor_floor),
    }
    for key, value in out.items():
        if not math.isfinite(float(value)):
            raise SystemExit(f"--{key.replace('_', '-')} must be finite")
    if out["z_dip_lo"] < 0.0:
        raise SystemExit("--dip-zlo must be >= 0")
    if out["z_dip_hi"] <= out["z_dip_lo"]:
        raise SystemExit("--dip-zhi must be > --dip-zlo")
    if out["z_bump_lo"] < 0.0:
        raise SystemExit("--bump-zlo must be >= 0")
    if out["z_bump_hi"] <= out["z_bump_lo"]:
        raise SystemExit("--bump-zhi must be > --bump-zlo")
    if out["z_bump_lo"] < out["z_dip_hi"]:
        raise SystemExit("--bump-zlo must be >= --dip-zhi for non-overlapping dip/bump windows")
    if out["w"] <= 0.0:
        raise SystemExit("--window-w must be > 0")
    if out["factor_floor"] <= 0.0:
        raise SystemExit("--factor-floor must be > 0")
    return out


def _build_model(model_name: str, params: Mapping[str, float], *, model_hyper: Optional[Mapping[str, float]] = None):
    h0_si = H0_to_SI(float(params["H0"]))
    if model_name == "lcdm":
        om = float(params["Omega_m"])
        return FlatLambdaCDMHistory(H0=h0_si, Omega_m=om, Omega_Lambda=1.0 - om)
    if model_name == "gsc_powerlaw":
        return PowerLawHistory(H0=h0_si, p=float(params["p"]))
    if model_name == "gsc_transition":
        om = float(params["Omega_m"])
        return GSCTransitionHistory(
            H0=h0_si,
            Omega_m=om,
            Omega_Lambda=1.0 - om,
            p=float(params["p"]),
            z_transition=float(params["z_transition"]),
        )
    if model_name == "dip_bump_window":
        om = float(params["Omega_m"])
        base = FlatLambdaCDMHistory(H0=h0_si, Omega_m=om, Omega_Lambda=1.0 - om)
        hyper = model_hyper or {}
        deformation = DipBumpWindowDeformation(
            A_dip=float(params["A_dip"]),
            A_bump=float(params["A_bump"]),
            z_dip_lo=float(hyper.get("z_dip_lo", DEFAULT_DIP_Z_LO)),
            z_dip_hi=float(hyper.get("z_dip_hi", DEFAULT_DIP_Z_HI)),
            z_bump_lo=float(hyper.get("z_bump_lo", DEFAULT_BUMP_Z_LO)),
            z_bump_hi=float(hyper.get("z_bump_hi", DEFAULT_BUMP_Z_HI)),
            w=float(hyper.get("w", DEFAULT_WINDOW_W)),
        )
        hz = deformation.apply(base.H, floor=float(hyper.get("factor_floor", DEFAULT_FACTOR_FLOOR)))
        return _CallableHistory(hz)
    if model_name == "logh_two_window":
        om = float(params["Omega_m"])
        base = FlatLambdaCDMHistory(H0=h0_si, Omega_m=om, Omega_Lambda=1.0 - om)
        deformation = LogHTwoWindowDeformation(
            tw1_zc=float(params["tw1_zc"]),
            tw1_w=float(params["tw1_w"]),
            tw1_a=float(params["tw1_a"]),
            tw2_zc=float(params["tw2_zc"]),
            tw2_w=float(params["tw2_w"]),
            tw2_a=float(params["tw2_a"]),
        )
        hz = deformation.apply(base.H)
        return _CallableHistory(hz)
    if model_name == "spline4_logh":
        om = float(params["Omega_m"])
        base = FlatLambdaCDMHistory(H0=h0_si, Omega_m=om, Omega_Lambda=1.0 - om)
        deformation = Spline4LogHDeformation(
            spl4_dlogh_z3=float(params["spl4_dlogh_z3"]),
            spl4_dlogh_z30=float(params["spl4_dlogh_z30"]),
            spl4_dlogh_z300=float(params["spl4_dlogh_z300"]),
            spl4_dlogh_z1100=float(params["spl4_dlogh_z1100"]),
        )
        hz = deformation.apply(base.H)
        return _CallableHistory(hz)
    raise ValueError(f"Unknown model {model_name!r}")


def _build_dm_interpolator(model, *, z_max: float, n_grid: int):
    np = _require_numpy_or_die()
    if not (z_max > 0.0 and math.isfinite(z_max)):
        raise ValueError("z_max must be finite and > 0")
    if n_grid < 64:
        raise ValueError("n_grid must be >= 64")

    z_grid = np.linspace(0.0, float(z_max), int(n_grid) + 1, dtype=float)
    inv_h = np.empty_like(z_grid)
    for i, z in enumerate(z_grid):
        hz = float(model.H(float(z)))
        if hz <= 0.0 or not math.isfinite(hz):
            raise ValueError("H(z) must be positive and finite")
        inv_h[i] = 1.0 / hz
    dz = float(z_grid[1] - z_grid[0])
    cum = np.empty_like(z_grid)
    cum[0] = 0.0
    cum[1:] = np.cumsum(0.5 * (inv_h[:-1] + inv_h[1:]) * dz)
    chi_grid = float(C_SI) * cum

    def dm_fn(zs):
        return np.interp(zs, z_grid, chi_grid)

    return dm_fn


def _drift_sign(model, *, z_min: float, z_max: float, z_n: int) -> Tuple[bool, float]:
    if not (z_max > z_min >= 0.0):
        raise ValueError("Require 0 <= drift-z-min < drift-z-max")
    if z_n < 2:
        raise ValueError("drift-z-n must be >= 2")

    h0 = float(model.H(0.0))
    min_zdot = float("inf")
    all_positive = True
    for i in range(int(z_n)):
        z = float(z_min + (z_max - z_min) * i / (z_n - 1))
        zdot = float(z_dot_sandage_loeb(z=z, H0=h0, H_of_z=model.H))
        if not math.isfinite(zdot):
            all_positive = False
            min_zdot = float("nan")
            break
        min_zdot = min(min_zdot, zdot)
        if zdot <= 0.0:
            all_positive = False
    return bool(all_positive), float(min_zdot)


def _drift_metrics(model, *, z_list: Sequence[float]) -> Dict[str, Any]:
    h0 = float(model.H(0.0))
    z_vals: List[float] = []
    z_dot_vals: List[float] = []
    dv_vals: List[float] = []
    all_positive = True
    min_zdot = float("inf")
    for z in z_list:
        zz = float(z)
        zdot = float(z_dot_sandage_loeb(z=zz, H0=h0, H_of_z=model.H))
        dv = float(delta_v_cm_s(z=zz, years=1.0, H0=h0, H_of_z=model.H))
        z_vals.append(zz)
        z_dot_vals.append(zdot)
        dv_vals.append(dv)
        if not math.isfinite(zdot):
            all_positive = False
            min_zdot = float("nan")
            continue
        min_zdot = min(min_zdot, zdot)
        if zdot <= 0.0:
            all_positive = False

    return {
        "z_list": [float(v) for v in z_vals],
        "z_dot": [float(v) if math.isfinite(v) else None for v in z_dot_vals],
        "dv_cm_s_per_yr": [float(v) if math.isfinite(v) else None for v in dv_vals],
        "min_z_dot": float(min_zdot) if math.isfinite(min_zdot) else None,
        "all_positive": bool(all_positive),
    }


def _drift_precheck_pass(*, spec: str, z_dot_values: Sequence[Any]) -> bool:
    mode = str(spec).strip().lower()
    if mode == "none":
        return True
    values: List[float] = []
    for value in z_dot_values:
        fv = _finite_float(value)
        if fv is None:
            return False
        values.append(float(fv))
    if not values:
        return False
    if mode == "z2_5_positive":
        return bool(all(v > 0.0 for v in values))
    if mode == "z2_5_negative":
        return bool(all(v < 0.0 for v in values))
    raise ValueError(f"Unsupported drift precheck spec: {mode!r}")


def _sentinel_chi2_parts(*, drift_pass: bool, min_zdot: float) -> Dict[str, Any]:
    return {
        "cmb": {
            "chi2": float(_CHI2_SENTINEL),
            "method": "skipped_drift_precheck",
            "keys": [],
            "pulls": {},
            "worst_key": None,
            "max_abs_pull": float(_CHI2_SENTINEL),
        },
        "drift": {
            "chi2": float(_CHI2_SENTINEL),
            "sign_ok": bool(drift_pass),
            "penalty": float(_CHI2_SENTINEL),
            "min_zdot_si": float(min_zdot),
        },
        "priors": {
            "chi2": float(_CHI2_SENTINEL),
            "terms": {},
            "active": False,
        },
        "invariants": {
            "chi2": float(_CHI2_SENTINEL),
            "ok": False,
            "error_count": 0,
            "missing_required_count": 0,
        },
    }


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    try:
        fv = float(value)
        return fv if math.isfinite(fv) else None
    except Exception:
        return str(value)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _canonical_opt_init(value: str) -> str:
    token = str(value).strip().lower()
    if token not in _OPT_MULTISTART_INIT_CHOICES:
        raise SystemExit(
            f"Unsupported --opt-init: {value!r} (expected one of {', '.join(_OPT_MULTISTART_INIT_CHOICES)})"
        )
    return token


def _multistart_grid_point(
    *,
    index: int,
    n_points: int,
    bounds: Sequence[Tuple[float, float]],
) -> List[float]:
    n_dim = len(bounds)
    if n_dim <= 0:
        return []
    side = int(math.ceil(float(n_points) ** (1.0 / float(n_dim))))
    side = max(side, 1)
    idx = int(index)
    coords: List[int] = []
    for _ in range(n_dim):
        coords.append(idx % side)
        idx //= side
    out: List[float] = []
    for dim, (lo, hi) in enumerate(bounds):
        span = float(hi) - float(lo)
        if span <= 0.0:
            out.append(float(lo))
            continue
        if side == 1:
            u = 0.5
        else:
            u = (float(coords[dim]) + 0.5) / float(side)
        u = min(max(float(u), 0.0), math.nextafter(1.0, 0.0))
        out.append(float(lo + span * u))
    return out


def _build_multistart_vectors(
    *,
    x0: Sequence[float],
    bounds: Sequence[Tuple[float, float]],
    k: int,
    init_mode: str,
    seed: int,
) -> List[List[float]]:
    k_int = max(int(k), 1)
    x0_vec = [float(v) for v in x0]
    if k_int <= 1:
        return [x0_vec]

    mode = _canonical_opt_init(init_mode)
    starts: List[List[float]] = [list(x0_vec)]
    n_extra = int(k_int - 1)
    bounds_map: Dict[str, Tuple[float, float]] = {
        f"x{idx}": (float(lo), float(hi))
        for idx, (lo, hi) in enumerate(bounds)
    }
    if mode == "latin_hypercube":
        for point in iter_lhs_points(bounds_map, n=n_extra, seed=int(seed)):
            starts.append([float(point[f"x{idx}"]) for idx in range(len(x0_vec))])
    elif mode == "random":
        for point in iter_random_points(bounds_map, n=n_extra, seed=int(seed)):
            starts.append([float(point[f"x{idx}"]) for idx in range(len(x0_vec))])
    else:  # mode == "grid"
        for idx in range(n_extra):
            starts.append(
                _multistart_grid_point(
                    index=idx,
                    n_points=n_extra,
                    bounds=bounds,
                )
            )
    return starts


def _opt_start_points_digest(
    *,
    free_keys: Sequence[str],
    starts: Sequence[Sequence[float]],
) -> str:
    payload = {
        "free_keys": [str(k) for k in free_keys],
        "starts": [[float(v) for v in vec] for vec in starts],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_rsd_mode(value: str) -> str:
    token = str(value).strip().lower()
    aliases = {
        "profile_sigma8_0": "profile_sigma8_0",
        "nuisance_sigma8": "profile_sigma8_0",
        "nuisance": "profile_sigma8_0",
        "profile": "profile_sigma8_0",
        "derived_as": "derived_as",
        "derived": "derived_as",
        "derived-as": "derived_as",
    }
    if token not in aliases:
        raise SystemExit(f"Unsupported --rsd-mode: {value!r}")
    return aliases[token]


def _canonical_rsd_helper_mode(scan_mode: str) -> str:
    mode = str(scan_mode).strip().lower()
    if mode == "profile_sigma8_0":
        return "nuisance_sigma8"
    if mode == "derived_as":
        return "derived_as"
    return "nuisance_sigma8"


def _canonical_rsd_transfer_model(value: str) -> str:
    token = str(value).strip().lower()
    aliases = {
        "bbks": "bbks",
        "eh98": "eh98_nowiggle",
        "eh98_nowiggle": "eh98_nowiggle",
    }
    if token not in aliases:
        raise SystemExit(
            f"Unsupported --rsd-transfer-model: {value!r} (expected bbks or eh98_nowiggle)"
        )
    return aliases[token]


def _extract_rsd_chi2_value(
    record: Mapping[str, Any],
    *,
    requested_field: str,
) -> Tuple[Optional[float], Optional[str]]:
    requested = str(requested_field).strip()
    if requested:
        value = _finite_float(record.get(requested))
        if value is None:
            return None, None
        return float(value), requested
    for candidate in _RSD_CHI2_FIELD_PRIORITY:
        value = _finite_float(record.get(candidate))
        if value is None:
            continue
        return float(value), str(candidate)
    return None, None


def _effective_opt_objective_key(*, chi2_objective: str, requested_key: str) -> str:
    if str(chi2_objective) == "joint":
        return "chi2_joint_total"
    return str(requested_key)


def _apply_joint_objective_fields(
    *,
    row: Dict[str, Any],
    point_record: Dict[str, Any],
    chi2_objective: str,
    rsd_chi2_field: str,
    rsd_chi2_weight: float,
) -> None:
    mode = str(chi2_objective).strip().lower()
    if mode != "joint":
        return

    chi2_total = _finite_float(point_record.get("chi2_total"))
    if chi2_total is None:
        chi2_total = _finite_float(row.get("chi2_total"))
    rsd_chi2, field_used = _extract_rsd_chi2_value(point_record, requested_field=rsd_chi2_field)
    if rsd_chi2 is None:
        rsd_chi2, field_used = _extract_rsd_chi2_value(row, requested_field=rsd_chi2_field)

    payload: Dict[str, Any] = {
        "chi2_objective": "joint",
        "rsd_chi2_weight": float(rsd_chi2_weight),
        "rsd_chi2_field_used": (
            str(field_used)
            if field_used is not None
            else (str(rsd_chi2_field).strip() if str(rsd_chi2_field).strip() else "auto")
        ),
    }
    if chi2_total is not None and rsd_chi2 is not None:
        payload["chi2_joint_total"] = float(chi2_total + float(rsd_chi2_weight) * float(rsd_chi2))

    for target in (row, point_record):
        target.update(payload)


def _rsd_dataset_id_from_path(path: Path) -> str:
    name = str(path.name).strip()
    lowered = name.lower()
    if "gold2017_plus_zhao2018" in lowered:
        return "gold2017_plus_zhao2018"
    stem = name
    if stem.endswith(".gz"):
        stem = stem[:-3]
    if stem.endswith(".csv"):
        stem = stem[:-4]
    if not stem:
        stem = "custom_rsd_dataset"
    out_chars: List[str] = []
    for ch in stem.lower():
        if ch.isalnum():
            out_chars.append(ch)
        else:
            out_chars.append("_")
    normalized = "".join(out_chars).strip("_")
    return normalized or "custom_rsd_dataset"


def _resolve_scan_rsd_overlay_settings(args: argparse.Namespace) -> Dict[str, Any]:
    enabled = bool(args.rsd_overlay)
    ap_mode = str(args.rsd_ap_correction).strip().lower()
    if ap_mode not in {"none", "approx"}:
        raise SystemExit(f"Unsupported --rsd-ap-correction: {args.rsd_ap_correction!r}")
    scan_mode = _canonical_rsd_mode(str(args.rsd_mode))
    transfer_model = _canonical_rsd_transfer_model(str(args.rsd_transfer_model))
    primordial_ns = _finite_float(args.rsd_ns)
    if primordial_ns is None:
        raise SystemExit("--rsd-ns must be finite")
    k_pivot_mpc = _finite_float(args.rsd_k_pivot)
    if k_pivot_mpc is None or not (k_pivot_mpc > 0.0):
        raise SystemExit("--rsd-k-pivot must be finite and > 0")
    data_path = Path(args.rsd_data).expanduser().resolve()
    dataset_id = _rsd_dataset_id_from_path(data_path)

    dataset_available = False
    dataset_sha256: Optional[str] = None
    dataset_missing_reason: Optional[str] = None
    if enabled:
        if data_path.is_file():
            dataset_sha256 = _sha256_file(data_path)
            dataset_available = bool(dataset_sha256)
            if not dataset_available:
                dataset_missing_reason = "dataset_unreadable"
        else:
            dataset_missing_reason = "dataset_missing"

    return {
        "enabled": bool(enabled),
        "dataset_path": str(data_path),
        "dataset_id": str(dataset_id),
        "dataset_sha256": None if dataset_sha256 is None else str(dataset_sha256),
        "dataset_available": bool(dataset_available),
        "dataset_missing_reason": dataset_missing_reason,
        "ap_mode": str(ap_mode),
        "ap_correction": bool(ap_mode == "approx"),
        "scan_mode": str(scan_mode),
        "helper_mode": str(_canonical_rsd_helper_mode(scan_mode)),
        "uses_primordial_knobs": bool(enabled and str(scan_mode) == "derived_as"),
        "transfer_model": str(transfer_model),
        "primordial_ns": float(primordial_ns),
        "primordial_k_pivot_mpc": float(k_pivot_mpc),
        "status_filter": "ok_only",
    }


def _validate_joint_objective_prereqs(args: argparse.Namespace) -> None:
    if str(args.chi2_objective) != "joint":
        return
    if not bool(args.rsd_overlay):
        print(
            "MISSING_RSD_OVERLAY_FOR_JOINT_OBJECTIVE: --chi2-objective joint requires --rsd-overlay.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _rsd_skip_reason_from_overlay(overlay: Mapping[str, Any]) -> str:
    status = str(overlay.get("rsd_overlay_status", "")).strip().lower()
    if status == "skipped_missing_data":
        return "dataset_missing"
    if status == "skipped_ineligible":
        return "not_eligible_status"
    if status == "skipped_missing_cosmo":
        return "missing_cosmo"
    if status == "error":
        err = str(overlay.get("rsd_error", "")).strip().lower()
        if err.startswith("growth_solver_failed"):
            return "growth_solve_failed"
        if err.startswith("row_processing_failed"):
            return "chi2_missing_inputs"
        if err:
            return "overlay_error"
        return "overlay_error"
    if status:
        return f"overlay_{status}"
    return "overlay_unknown"


def _apply_rsd_overlay_fields(
    *,
    row: Dict[str, Any],
    point_record: Dict[str, Any],
    rsd_settings: Mapping[str, Any],
) -> None:
    if not bool(rsd_settings.get("enabled", False)):
        return

    dataset_id = str(rsd_settings.get("dataset_id", "custom_rsd_dataset"))
    dataset_sha256 = str(rsd_settings.get("dataset_sha256") or "")
    ap_mode = str(rsd_settings.get("ap_mode", "none"))
    scan_mode = str(rsd_settings.get("scan_mode", "profile_sigma8_0"))
    uses_primordial_knobs = bool(rsd_settings.get("uses_primordial_knobs", False))
    transfer_model = None
    primordial_ns = None
    primordial_k_pivot = None
    if uses_primordial_knobs:
        transfer_model = str(rsd_settings.get("transfer_model", "bbks"))
        primordial_ns = _finite_float(rsd_settings.get("primordial_ns"))
        primordial_k_pivot = _finite_float(rsd_settings.get("primordial_k_pivot_mpc"))

    payload: Dict[str, Any] = {
        "rsd_overlay_ok": False,
        "rsd_overlay_skip_reason": None,
        "rsd_dataset_id": dataset_id,
        "rsd_dataset_sha256": dataset_sha256,
        "rsd_n": 0,
        "rsd_chi2": None,
        "rsd_chi2_total": None,
        "rsd_dof": None,
        "rsd_sigma8_0_best": None,
        "rsd_ap_correction": ap_mode,
        "rsd_mode": scan_mode,
        "rsd_transfer_model": transfer_model,
        "rsd_primordial_ns": primordial_ns,
        "rsd_primordial_k_pivot_mpc": primordial_k_pivot,
    }

    status = str(point_record.get("status", row.get("status", "ok"))).strip().lower()
    if status != "ok":
        payload["rsd_overlay_skip_reason"] = "not_ok_status"
    elif not bool(rsd_settings.get("dataset_available", False)):
        payload["rsd_overlay_skip_reason"] = str(
            rsd_settings.get("dataset_missing_reason") or "dataset_missing"
        )
    else:
        overlay = rsd_overlay_for_e2_record(
            point_record,
            rsd_csv_path=str(rsd_settings.get("dataset_path", "")),
            ap_correction=bool(rsd_settings.get("ap_correction", False)),
            status_filter=str(rsd_settings.get("status_filter", "ok_only")),
            rsd_mode=str(rsd_settings.get("helper_mode", "nuisance_sigma8")),
            transfer_model=transfer_model,
            primordial_ns=primordial_ns,
            primordial_k_pivot_mpc=primordial_k_pivot,
        )
        chi2_rsd = _finite_float(overlay.get("chi2_rsd_min"))
        sigma8_best = _finite_float(overlay.get("rsd_sigma8_0_best"))
        rsd_n = int(_finite_float(overlay.get("rsd_n")) or 0)
        overlay_sha = str(overlay.get("rsd_data_sha256") or "").strip()
        if overlay_sha:
            payload["rsd_dataset_sha256"] = overlay_sha
        overlay_transfer = overlay.get("rsd_transfer_model")
        if overlay_transfer is not None:
            payload["rsd_transfer_model"] = str(overlay_transfer)
        overlay_ns = _finite_float(overlay.get("rsd_primordial_ns"))
        if overlay_ns is not None:
            payload["rsd_primordial_ns"] = float(overlay_ns)
        overlay_k_pivot = _finite_float(overlay.get("rsd_primordial_k_pivot_mpc"))
        if overlay_k_pivot is not None:
            payload["rsd_primordial_k_pivot_mpc"] = float(overlay_k_pivot)
        if str(overlay.get("rsd_overlay_status", "")).strip().lower() == "ok" and chi2_rsd is not None:
            payload["rsd_overlay_ok"] = True
            payload["rsd_chi2"] = float(chi2_rsd)
            payload["rsd_chi2_total"] = float(chi2_rsd)
            payload["rsd_sigma8_0_best"] = sigma8_best
            payload["rsd_n"] = int(max(rsd_n, 0))
            payload["rsd_dof"] = int(max(rsd_n - 1, 0))
            payload["rsd_overlay_skip_reason"] = None
        else:
            payload["rsd_overlay_skip_reason"] = _rsd_skip_reason_from_overlay(overlay)
            payload["rsd_n"] = int(max(rsd_n, 0))

    for target in (row, point_record):
        target.update(payload)
        if payload.get("rsd_overlay_skip_reason") is None:
            target.pop("rsd_overlay_skip_reason", None)


def _canonical_params(params: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in sorted(str(k) for k in params.keys()):
        fv = _finite_float(params[key])
        if fv is not None:
            out[str(key)] = float(fv)
    return out


def _params_hash(params: Mapping[str, Any]) -> str:
    canonical = _canonical_params(params)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_params_hash_from_record(obj: Mapping[str, Any]) -> Optional[str]:
    raw_hash = obj.get("params_hash")
    if isinstance(raw_hash, str) and raw_hash.strip():
        return raw_hash.strip()
    raw_params = obj.get("params")
    if isinstance(raw_params, Mapping):
        canonical = _canonical_params(raw_params)
        if canonical:
            return _params_hash(canonical)
    return None


def _normalized_status(payload: Mapping[str, Any]) -> str:
    status = str(payload.get("status", "ok")).strip().lower()
    return status or "ok"


def _is_completed_plan_status(payload: Mapping[str, Any]) -> bool:
    return _normalized_status(payload) != "error"


def _load_existing_points(points_jsonl: Path) -> Tuple[List[Dict[str, Any]], set[str]]:
    existing_points: List[Dict[str, Any]] = []
    existing_hashes: set[str] = set()
    if not points_jsonl.is_file():
        return existing_points, existing_hashes
    with open_text_auto(points_jsonl, "r") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if not isinstance(payload, Mapping):
                continue
            point = {str(k): _to_json_safe(v) for k, v in payload.items()}
            ph = _extract_params_hash_from_record(point)
            if ph:
                point["params_hash"] = ph
                existing_hashes.add(ph)
            if "status" not in point:
                point["status"] = "ok"
            existing_points.append(point)
    return existing_points, existing_hashes


def _append_points_jsonl(path: Path, points: Sequence[Mapping[str, Any]]) -> None:
    if not points:
        return
    with open_text_auto(path, "a") as fh:
        for point in points:
            fh.write(json.dumps(_to_json_safe(point), sort_keys=True) + "\n")


def _point_record_to_row(point: Mapping[str, Any]) -> Dict[str, Any]:
    params = _canonical_params(_as_mapping(point.get("params")))
    chi2_parts = _as_mapping(point.get("chi2_parts"))
    cmb = _as_mapping(chi2_parts.get("cmb"))
    drift_parts = _as_mapping(chi2_parts.get("drift"))
    drift = _as_mapping(point.get("drift"))
    predicted = _as_mapping(point.get("predicted"))
    micro = _as_mapping(point.get("microphysics"))

    model_hyper = _as_mapping(point.get("model_hyper"))
    dip_hyper = _as_mapping(model_hyper.get("dip_bump_window"))

    row: Dict[str, Any] = {
        "model": str(point.get("model", "")),
        "deformation_family": str(point.get("deformation_family", point.get("model", ""))),
        "chi2_cmb": _finite_float(cmb.get("chi2")),
        "chi2_total": _finite_float(point.get("chi2_total")),
        "ndof_cmb": int(_finite_float(cmb.get("ndof")) or 0),
        "drift_pass": bool(point.get("drift_pass", False)),
        "drift_required_pass": bool(point.get("drift_required_pass", point.get("drift_pass", False))),
        "min_zdot_si": _finite_float(drift_parts.get("min_zdot_si")),
        "drift_margin": _finite_float(drift.get("min_z_dot")),
        "drift_penalty": _finite_float(drift_parts.get("penalty")) or 0.0,
        "chi2_priors": _finite_float(_as_mapping(chi2_parts.get("priors")).get("chi2")) or 0.0,
        "H0": float(params.get("H0", float("nan"))),
        "Omega_m": float(params.get("Omega_m", float("nan"))),
        "p": float(params.get("p", float("nan"))),
        "z_transition": float(params.get("z_transition", float("nan"))),
        "A_dip": float(params.get("A_dip", float("nan"))),
        "A_bump": float(params.get("A_bump", float("nan"))),
        "tw1_zc": float(params.get("tw1_zc", float("nan"))),
        "tw1_w": float(params.get("tw1_w", float("nan"))),
        "tw1_a": float(params.get("tw1_a", float("nan"))),
        "tw2_zc": float(params.get("tw2_zc", float("nan"))),
        "tw2_w": float(params.get("tw2_w", float("nan"))),
        "tw2_a": float(params.get("tw2_a", float("nan"))),
        "spl4_dlogh_z3": float(params.get("spl4_dlogh_z3", float("nan"))),
        "spl4_dlogh_z30": float(params.get("spl4_dlogh_z30", float("nan"))),
        "spl4_dlogh_z300": float(params.get("spl4_dlogh_z300", float("nan"))),
        "spl4_dlogh_z1100": float(params.get("spl4_dlogh_z1100", float("nan"))),
        "dip_zlo": _finite_float(dip_hyper.get("z_dip_lo")) if dip_hyper else float("nan"),
        "dip_zhi": _finite_float(dip_hyper.get("z_dip_hi")) if dip_hyper else float("nan"),
        "bump_zlo": _finite_float(dip_hyper.get("z_bump_lo")) if dip_hyper else float("nan"),
        "bump_zhi": _finite_float(dip_hyper.get("z_bump_hi")) if dip_hyper else float("nan"),
        "window_w": _finite_float(dip_hyper.get("w")) if dip_hyper else float("nan"),
        "omega_b_h2": float(params.get("omega_b_h2", float("nan"))),
        "omega_c_h2": float(params.get("omega_c_h2", float("nan"))),
        "N_eff": float(params.get("N_eff", float("nan"))),
        "Y_p": float(params.get("Y_p", float("nan"))),
        "Y_p_used": bool(_as_mapping(point.get("early_time")).get("Y_p_used", False)),
        "microphysics_mode": str(micro.get("mode", "none")),
        "z_star_scale": _finite_float(micro.get("z_star_scale")) or 1.0,
        "r_s_scale": _finite_float(micro.get("r_s_scale")) or 1.0,
        "r_d_scale": _finite_float(micro.get("r_d_scale")) or 1.0,
        "microphysics_hard_ok": bool(point.get("microphysics_hard_ok", True)),
        "microphysics_plausible_ok": bool(point.get("microphysics_plausible_ok", True)),
        "microphysics_penalty": _finite_float(point.get("microphysics_penalty")) or 0.0,
        "microphysics_max_rel_dev": _finite_float(point.get("microphysics_max_rel_dev")) or 0.0,
        "cmb_bridge_z": float("nan"),
        "theta_star": _finite_float(predicted.get("theta_star")) or float("nan"),
        "lA": _finite_float(predicted.get("lA")) or float("nan"),
        "R": _finite_float(predicted.get("R")) or float("nan"),
        "z_star": _finite_float(predicted.get("z_star")) or float("nan"),
        "r_s_star_Mpc": _finite_float(predicted.get("r_s_star_Mpc")) or float("nan"),
        "D_M_star_Mpc": _finite_float(predicted.get("D_M_star_Mpc")) or float("nan"),
        "bridge_H_ratio": _finite_float(predicted.get("bridge_H_ratio")) or float("nan"),
        "recombination_method": str(
            predicted.get("recombination_method", point.get("recombination_method", "fit"))
        ),
        "recomb_converged": bool(predicted.get("recomb_converged", True)),
        "drag_method": str(predicted.get("drag_method", "eh98")),
        "cmb_num_method": str(predicted.get("cmb_num_method", point.get("integrator", ""))),
        "cmb_num_n_eval_dm": int(_finite_float(predicted.get("cmb_num_n_eval_dm")) or 0),
        "cmb_num_err_dm": _finite_float(predicted.get("cmb_num_err_dm")),
        "cmb_num_n_eval_rs": int(_finite_float(predicted.get("cmb_num_n_eval_rs")) or 0),
        "cmb_num_err_rs": _finite_float(predicted.get("cmb_num_err_rs")),
        "cmb_num_n_eval_rs_drag": int(_finite_float(predicted.get("cmb_num_n_eval_rs_drag")) or 0),
        "cmb_num_err_rs_drag": _finite_float(predicted.get("cmb_num_err_rs_drag")),
        "cmb_num_rtol": _finite_float(predicted.get("cmb_num_rtol")),
        "cmb_num_atol": _finite_float(predicted.get("cmb_num_atol")),
        "invariants_ok": bool(point.get("invariants_ok", False)),
        "invariants_error_count": int(_as_mapping(chi2_parts.get("invariants")).get("error_count") or 0),
        "drift_metrics_available": isinstance(point.get("drift"), Mapping),
        "sample_index": int(_finite_float(point.get("sample_index")) or -1),
        "status": str(point.get("status", "ok")),
        "params_hash": str(point.get("params_hash", "")),
        "plan_point_id": point.get("plan_point_id"),
        "plan_point_index": int(_finite_float(point.get("plan_point_index")) or -1),
        "plan_source_sha256": point.get("plan_source_sha256"),
        "scan_config_sha256": point.get("scan_config_sha256"),
        "drift_precheck_spec": point.get("drift_precheck_spec"),
        "drift_precheck_ok": point.get("drift_precheck_ok"),
        "skip_reason": point.get("skip_reason"),
        "rsd_overlay_ok": bool(point.get("rsd_overlay_ok", False)),
        "rsd_overlay_skip_reason": point.get("rsd_overlay_skip_reason"),
        "rsd_dataset_id": point.get("rsd_dataset_id"),
        "rsd_dataset_sha256": point.get("rsd_dataset_sha256"),
        "rsd_n": int(_finite_float(point.get("rsd_n")) or 0),
        "rsd_chi2": _finite_float(point.get("rsd_chi2")),
        "rsd_chi2_total": _finite_float(point.get("rsd_chi2_total")),
        "rsd_dof": int(_finite_float(point.get("rsd_dof")) or 0) if _finite_float(point.get("rsd_dof")) is not None else None,
        "rsd_sigma8_0_best": _finite_float(point.get("rsd_sigma8_0_best")),
        "rsd_ap_correction": point.get("rsd_ap_correction"),
        "rsd_mode": point.get("rsd_mode"),
        "rsd_transfer_model": point.get("rsd_transfer_model"),
        "rsd_primordial_ns": _finite_float(point.get("rsd_primordial_ns")),
        "rsd_primordial_k_pivot_mpc": _finite_float(point.get("rsd_primordial_k_pivot_mpc")),
        "chi2_objective": (
            str(point.get("chi2_objective")).strip()
            if point.get("chi2_objective") is not None
            else None
        ),
        "chi2_joint_total": _finite_float(point.get("chi2_joint_total")),
        "rsd_chi2_field_used": (
            str(point.get("rsd_chi2_field_used")).strip()
            if point.get("rsd_chi2_field_used") is not None
            else None
        ),
        "rsd_chi2_weight": _finite_float(point.get("rsd_chi2_weight")),
    }
    opt_multistart = _finite_float(point.get("opt_multistart"))
    if opt_multistart is not None:
        row["opt_multistart"] = int(opt_multistart)
    opt_seed = _finite_float(point.get("opt_seed"))
    if opt_seed is not None:
        row["opt_seed"] = int(opt_seed)
    if point.get("opt_init") is not None:
        row["opt_init"] = str(point.get("opt_init")).strip()
    opt_best_start_index = _finite_float(point.get("opt_best_start_index"))
    if opt_best_start_index is not None:
        row["opt_best_start_index"] = int(opt_best_start_index)
    if point.get("opt_start_points_digest") is not None:
        row["opt_start_points_digest"] = str(point.get("opt_start_points_digest")).strip()
    chi2_bbn = _finite_float(point.get("chi2_bbn"))
    if chi2_bbn is None:
        bbn_part = _as_mapping(chi2_parts.get("bbn"))
        chi2_bbn = _finite_float(bbn_part.get("chi2"))
    if chi2_bbn is not None:
        row["chi2_bbn"] = float(chi2_bbn)
    return row


def _load_scan_plan(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    plan_path = path.expanduser().resolve()
    try:
        payload = load_refine_plan_v1(plan_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    plan_points: List[Dict[str, Any]] = []
    for idx, (point_id, _, params) in enumerate(iter_refine_plan_points(payload)):
        plan_points.append(
            {
                "plan_point_id": str(point_id),
                "plan_point_index": int(idx),
                "params": _canonical_params(params),
            }
        )
    plan_source_sha = str(refine_plan_source_sha256(payload))
    return plan_points, {str(k): _to_json_safe(v) for k, v in payload.items()}, plan_source_sha


def _parse_plan_slice(value: Optional[str]) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "/" not in text:
        raise SystemExit("--plan-slice must be in I/N format (example: 0/8)")
    left, right = text.split("/", 1)
    try:
        i = int(left.strip())
        n = int(right.strip())
    except Exception as exc:
        raise SystemExit("--plan-slice must contain integer values in I/N format") from exc
    if n < 1:
        raise SystemExit("--plan-slice requires N >= 1")
    if i < 0 or i >= n:
        raise SystemExit("--plan-slice requires 0 <= I < N")
    return (int(i), int(n))


def _lookup_path(payload: Mapping[str, Any], key: str) -> Any:
    if "." not in key:
        return payload.get(key)
    cur: Any = payload
    for part in str(key).split("."):
        if not isinstance(cur, Mapping):
            return None
        if part not in cur:
            return None
        cur = cur[part]
    return cur


def _resolve_opt_objective_value(
    *,
    row: Mapping[str, Any],
    point_record: Mapping[str, Any],
    objective_key: str,
) -> Tuple[float, Optional[str]]:
    status = str(point_record.get("status", row.get("status", "ok"))).strip().lower()
    if status != "ok":
        return float(_OPT_OBJECTIVE_BIG), None
    key = str(objective_key).strip()
    if not key:
        return float(_OPT_OBJECTIVE_BIG), "--opt-objective-key must be a non-empty key path"
    row_val = _lookup_path(row, key)
    row_float = _finite_float(row_val)
    if row_float is not None:
        return float(row_float), None
    point_val = _lookup_path(point_record, key)
    point_float = _finite_float(point_val)
    if point_float is not None:
        return float(point_float), None
    available = sorted({str(k) for k in row.keys()} | {str(k) for k in point_record.keys()})
    suffix = ", ".join(available[:40])
    if len(available) > 40:
        suffix += ", ..."
    return (
        float(_OPT_OBJECTIVE_BIG),
        (
            f"--opt-objective-key {key!r} is missing/non-finite for an ok record; "
            f"available top-level keys: {suffix}"
        ),
    )


def _build_opt_param_bounds(
    *,
    model_name: str,
    microphysics_mode: str,
    microphysics_bounds: Mapping[str, Tuple[float, float]],
) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {
        str(k): (float(v[0]), float(v[1]))
        for k, v in sorted(_OPT_COMMON_PARAM_BOUNDS.items())
    }
    if model_name == "dip_bump_window":
        out.update({str(k): (float(v[0]), float(v[1])) for k, v in sorted(_DIP_BUMP_PARAM_BOUNDS.items())})
    elif model_name == "logh_two_window":
        out.update({str(k): (float(v[0]), float(v[1])) for k, v in sorted(_TWO_WINDOW_PARAM_BOUNDS.items())})
    elif model_name == "spline4_logh":
        out.update({str(k): (float(v[0]), float(v[1])) for k, v in sorted(_SPLINE4_LOGH_PARAM_BOUNDS.items())})
    if str(microphysics_mode) == "knobs":
        for key, (lo, hi) in sorted(microphysics_bounds.items()):
            out[str(key)] = (float(lo), float(hi))
    return out


def _opt_param_order(*, model_name: str, params: Mapping[str, float]) -> Tuple[str, ...]:
    ordered: List[str] = []
    seen: set[str] = set()
    for key in _MODEL_KEYS.get(str(model_name), ()):
        if key in params and key not in seen:
            ordered.append(str(key))
            seen.add(str(key))
    for key in _EARLY_SCAN_KEYS:
        if key in params and key not in seen:
            ordered.append(str(key))
            seen.add(str(key))
    for key in _MICROPHYSICS_SCAN_KEYS:
        if key in params and key not in seen:
            ordered.append(str(key))
            seen.add(str(key))
    for key in sorted(str(k) for k in params.keys()):
        if key not in seen:
            ordered.append(str(key))
            seen.add(str(key))
    return tuple(ordered)


def _opt_bounds_for_seed(
    *,
    params: Mapping[str, float],
    ordered_keys: Sequence[str],
    bounds_map: Mapping[str, Tuple[float, float]],
) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {}
    for key in ordered_keys:
        seed_val = float(params[key])
        if key not in bounds_map:
            out[str(key)] = (float(seed_val), float(seed_val))
            continue
        lo, hi = bounds_map[str(key)]
        lo_f = float(lo)
        hi_f = float(hi)
        if hi_f < lo_f:
            lo_f, hi_f = hi_f, lo_f
        if seed_val < lo_f:
            lo_f = float(seed_val)
        if seed_val > hi_f:
            hi_f = float(seed_val)
        out[str(key)] = (float(lo_f), float(hi_f))
    return out


def _select_best(
    rows: Sequence[Dict[str, Any]],
    *,
    drift_pass: Optional[bool],
    objective_key: str,
) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        if drift_pass is not None and bool(row.get("drift_pass")) is not bool(drift_pass):
            continue
        chi2 = _finite_float(row.get(objective_key))
        if chi2 is None:
            continue
        if not bool(row.get("invariants_ok", False)):
            continue
        candidates.append(row)
    if not candidates:
        return None
    best = min(
        candidates,
        key=lambda r: (
            float(_finite_float(r.get(objective_key)) or float("inf")),
            float(_finite_float(r.get("chi2_total")) or float("inf")),
            str(r.get("params_hash", "")),
        ),
    )
    return _to_json_safe(best)


def _write_points_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    extra = sorted({k for r in rows for k in r.keys() if k not in _REQUIRED_CSV_COLUMNS})
    fieldnames = list(_REQUIRED_CSV_COLUMNS) + extra
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_points_jsonl(path: Path, points: Sequence[Dict[str, Any]]) -> None:
    with open_text_auto(path, "w") as f:
        for point in points:
            f.write(json.dumps(_to_json_safe(point), sort_keys=True) + "\n")


def _cmb_pull_summary(dataset: CMBPriorsDataset, predicted_for_keys: Mapping[str, float]) -> Tuple[Dict[str, float], Optional[str], float]:
    pulls: Dict[str, float] = {}
    worst_key: Optional[str] = None
    worst_abs = 0.0
    for prior in dataset.priors:
        sigma_eff = math.sqrt(float(prior.sigma) ** 2 + float(prior.sigma_theory) ** 2)
        if sigma_eff <= 0.0:
            continue
        pred = float(predicted_for_keys[prior.name])
        pull = (pred - float(prior.value)) / sigma_eff
        pulls[str(prior.name)] = float(pull)
        abs_pull = abs(float(pull))
        if abs_pull >= worst_abs:
            worst_abs = abs_pull
            worst_key = str(prior.name)
    return pulls, worst_key, float(worst_abs)


def _cmb_observed_map(dataset: CMBPriorsDataset) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for prior in dataset.priors:
        out[str(prior.name)] = float(prior.value)
    return out


def _cmb_sigma_diag_map(dataset: CMBPriorsDataset, np) -> Dict[str, float]:
    if dataset.cov is None:
        out: Dict[str, float] = {}
        for prior in dataset.priors:
            sigma_eff = math.sqrt(float(prior.sigma) ** 2 + float(prior.sigma_theory) ** 2)
            out[str(prior.name)] = float(sigma_eff)
        return out

    cov = np.asarray(dataset.cov, dtype=float)
    diag = np.diag(cov)
    out = {}
    for i, prior in enumerate(dataset.priors):
        sigma2 = float(diag[i]) + float(prior.sigma_theory) ** 2
        sigma2 = max(sigma2, 0.0)
        out[str(prior.name)] = float(math.sqrt(sigma2))
    return out


def _safe_ratio(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None:
        return None
    if not (math.isfinite(float(num)) and math.isfinite(float(den))):
        return None
    if float(den) == 0.0:
        return None
    return float(num) / float(den)


def _safe_percent(scale: Optional[float]) -> Optional[float]:
    if scale is None:
        return None
    if not math.isfinite(float(scale)):
        return None
    return 100.0 * (float(scale) - 1.0)


def _safe_sigma_residual(pred: Optional[float], obs: Optional[float], sigma: Optional[float]) -> Optional[float]:
    if pred is None or obs is None or sigma is None:
        return None
    if not (math.isfinite(float(pred)) and math.isfinite(float(obs)) and math.isfinite(float(sigma))):
        return None
    if float(sigma) <= 0.0:
        return None
    return (float(pred) - float(obs)) / float(sigma)


def _cmb_tension_metrics(
    *,
    dataset: CMBPriorsDataset,
    pred_all: Mapping[str, float],
    np,
) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]:
    obs = _cmb_observed_map(dataset)
    sigma_diag = _cmb_sigma_diag_map(dataset, np=np)

    r_pred = _finite_float(pred_all.get("R"))
    la_pred = _finite_float(pred_all.get("lA"))
    omega_pred = _finite_float(pred_all.get("omega_b_h2"))

    r_obs = _finite_float(obs.get("R"))
    la_obs = _finite_float(obs.get("lA"))
    omega_obs = _finite_float(obs.get("omega_b_h2"))

    sigma_r = _finite_float(sigma_diag.get("R"))
    sigma_la = _finite_float(sigma_diag.get("lA"))
    sigma_omega = _finite_float(sigma_diag.get("omega_b_h2"))

    scale_d_from_r = _safe_ratio(r_obs, r_pred)
    scale_rs_from_la_given_r = None
    if scale_d_from_r is not None and la_pred is not None and la_obs is not None and float(la_obs) != 0.0:
        scale_rs_from_la_given_r = float(scale_d_from_r) * float(la_pred) / float(la_obs)
    scale_rs_from_la_only = _safe_ratio(la_pred, la_obs)
    scale_d_from_la_only = _safe_ratio(la_obs, la_pred)

    cmb_pred = {
        "R": None if r_pred is None else float(r_pred),
        "lA": None if la_pred is None else float(la_pred),
        "omega_b_h2": None if omega_pred is None else float(omega_pred),
    }
    cmb_tension = {
        "scale_D_from_R": scale_d_from_r,
        "scale_rs_from_lA_given_R": scale_rs_from_la_given_r,
        "scale_rs_from_lA_only": scale_rs_from_la_only,
        "scale_D_from_lA_only": scale_d_from_la_only,
        "delta_D_pct": _safe_percent(scale_d_from_r),
        "delta_rs_pct": _safe_percent(scale_rs_from_la_given_r),
        "dR_sigma_diag": _safe_sigma_residual(r_pred, r_obs, sigma_r),
        "dlA_sigma_diag": _safe_sigma_residual(la_pred, la_obs, sigma_la),
        "domega_sigma_diag": _safe_sigma_residual(omega_pred, omega_obs, sigma_omega),
    }
    return cmb_pred, cmb_tension


def _energy_from_row(
    row: Mapping[str, Any],
    *,
    energy_mode: str,
    chi2_objective: str,
    include_plausibility_if_available: bool,
) -> float:
    objective_mode = str(chi2_objective).strip().lower()
    objective_key = "chi2_joint_total" if objective_mode == "joint" else "chi2_total"
    chi2_value = _finite_float(row.get(objective_key))
    if chi2_value is None:
        return float("inf")
    energy = float(chi2_value)
    mode = str(energy_mode)
    if mode == "chi2_total":
        return energy
    if mode == "chi2_total_plus_plausibility":
        penalty = _finite_float(row.get("microphysics_penalty"))
        if penalty is not None:
            energy += float(penalty)
        return float(energy)
    if include_plausibility_if_available:
        penalty = _finite_float(row.get("microphysics_penalty"))
        if penalty is not None:
            energy += float(penalty)
    return float(energy)


def _resolve_energy_mode(*, requested: str, include_plausibility_if_available: bool) -> str:
    mode = str(requested)
    if mode in {"chi2_total", "chi2_total_plus_plausibility"}:
        return mode
    return "chi2_total_plus_plausibility" if include_plausibility_if_available else "chi2_total"


def _toy_obs_for_key(index: int) -> Tuple[float, float]:
    i = int(index)
    mu = 0.30 + 0.04 * float(i)
    sigma = 0.08 + 0.01 * float(i)
    return float(mu), float(sigma)


def _evaluate_point_toy(
    *,
    model_name: str,
    params: Mapping[str, float],
    early_defaults: Mapping[str, Optional[float]],
    gaussian_priors: Mapping[str, Tuple[float, float]],
    bbn_prior_mode: str,
    drift_z_min: float,
    drift_z_max: float,
    drift_z_n: int,
    drift_z_list: Sequence[float],
    include_drift_metrics: bool,
    require_positive_drift: bool,
    drift_precheck_spec: str,
    microphysics_mode: str,
    recombination_method: str,
    drag_method: str,
    recombination_rtol: float,
    recombination_atol: float,
    recombination_max_steps: int,
    sampler: str,
    seed: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    omega_b_h2 = float(params.get("omega_b_h2", float(early_defaults["omega_b_h2"])))
    omega_c_h2 = float(params.get("omega_c_h2", float(early_defaults["omega_c_h2"])))
    n_eff = float(params.get("N_eff", float(early_defaults["N_eff"])))
    y_p_default = early_defaults.get("Y_p")
    y_p = float(params["Y_p"]) if "Y_p" in params else (None if y_p_default is None else float(y_p_default))
    y_p_used = bool(y_p is not None)

    microphysics_scales = _microphysics_scales_from_params(params=params, mode=str(microphysics_mode))
    microphysics_payload, microphysics_audit = _microphysics_payload_and_audit(
        scales=microphysics_scales,
        mode=str(microphysics_mode),
    )

    h0 = float(params.get("H0", 67.4))
    omega_m = float(params.get("Omega_m", 0.315))
    p = float(params.get("p", 0.6))
    a_dip = float(params.get("A_dip", 0.0))
    a_bump = float(params.get("A_bump", 0.0))
    tw1_zc = float(params.get("tw1_zc", float("nan")))
    tw1_w = float(params.get("tw1_w", float("nan")))
    tw1_a = float(params.get("tw1_a", 0.0))
    tw2_zc = float(params.get("tw2_zc", float("nan")))
    tw2_w = float(params.get("tw2_w", float("nan")))
    tw2_a = float(params.get("tw2_a", 0.0))
    spl4_dlogh_z3 = float(params.get("spl4_dlogh_z3", 0.0))
    spl4_dlogh_z30 = float(params.get("spl4_dlogh_z30", 0.0))
    spl4_dlogh_z300 = float(params.get("spl4_dlogh_z300", 0.0))
    spl4_dlogh_z1100 = float(params.get("spl4_dlogh_z1100", 0.0))

    theta_star = float((0.01041 + 1.0e-5 * (h0 - 67.4) - 2.0e-4 * (omega_m - 0.315)) * microphysics_scales["r_s_scale"])
    theta_star = max(theta_star, 1e-8)
    l_a = float(math.pi / theta_star)
    r_val = float(1.75 + 0.8 * (omega_m - 0.315) + 0.005 * (h0 - 67.4))
    z_star = float(1089.5 * microphysics_scales["z_star_scale"])
    r_s_star_mpc = float(144.4 * microphysics_scales["r_s_scale"])
    d_m_star_mpc = float(l_a * r_s_star_mpc / math.pi)
    rd_mpc = float(147.1 * microphysics_scales["r_d_scale"])
    rd_m = float(rd_mpc * 3.085677581491367e22)

    pred_all = {
        "theta_star": float(theta_star),
        "100theta_star": float(100.0 * theta_star),
        "100*theta_star": float(100.0 * theta_star),
        "lA": float(l_a),
        "R": float(r_val),
        "z_star": float(z_star),
        "r_s_star_Mpc": float(r_s_star_mpc),
        "D_M_star_Mpc": float(d_m_star_mpc),
        "rd_Mpc": float(rd_mpc),
        "rd_m": float(rd_m),
        "omega_b_h2": float(omega_b_h2),
        "omega_c_h2": float(omega_c_h2),
    }
    invariants = run_early_time_invariants(pred_all, profile="phase2_m27_toy", strict=True)
    invariants_ok = bool(invariants.get("ok"))

    cmb_targets = {
        "R": (1.75, 0.02),
        "lA": (301.5, 0.4),
        "omega_b_h2": (0.02237, 5.0e-4),
    }
    chi2_cmb = 0.0
    pulls: Dict[str, float] = {}
    for key, (mu, sigma) in sorted(cmb_targets.items()):
        value = float(pred_all[key])
        pull = (value - float(mu)) / float(sigma)
        pulls[str(key)] = float(pull)
        chi2_cmb += float(pull * pull)

    base_keys = [k for k in sorted(params.keys()) if k not in _MICROPHYSICS_SCAN_KEYS and k not in _EARLY_SCAN_KEYS]
    chi2_late = 0.0
    for idx, key in enumerate(base_keys):
        mu, sigma = _toy_obs_for_key(idx)
        value = float(params[key])
        chi2_late += ((value - mu) / sigma) ** 2

    chi2_priors = 0.0
    prior_breakdown: Dict[str, Dict[str, float]] = {}
    for key, (mu, sigma) in sorted(gaussian_priors.items()):
        if key == "Y_p":
            if y_p is None:
                continue
            value = float(y_p)
        elif key == "omega_b_h2":
            value = float(omega_b_h2)
        elif key == "omega_c_h2":
            value = float(omega_c_h2)
        elif key == "N_eff":
            value = float(n_eff)
        else:
            continue
        pull = (value - float(mu)) / float(sigma)
        contrib = float(pull * pull)
        chi2_priors += contrib
        prior_breakdown[str(key)] = {
            "value": float(value),
            "mu": float(mu),
            "sigma": float(sigma),
            "pull": float(pull),
            "chi2": float(contrib),
        }
    bbn_result = evaluate_bbn_prior_chi2(
        mode=str(bbn_prior_mode),
        omega_b_h2=float(omega_b_h2),
    )
    chi2_bbn = float(bbn_result.chi2) if bool(bbn_result.enabled) else 0.0

    drift_core = (
        (0.5 - (omega_m - 0.30))
        + 0.2 * (0.65 - p)
        + 0.3 * (a_dip - 0.2)
        - 0.25 * max(a_bump - 0.5, 0.0)
        + 0.20 * tw1_a
        - 0.10 * tw2_a
        + 0.25 * spl4_dlogh_z3
        + 0.05 * spl4_dlogh_z30
        - 0.05 * spl4_dlogh_z300
        - 0.10 * spl4_dlogh_z1100
    )
    min_zdot = float(drift_core * 1.0e-10)
    drift_pass = bool(min_zdot > 0.0)
    drift_penalty = 1.0e6 if (require_positive_drift and not drift_pass) else 0.0

    if include_drift_metrics:
        z_vals = [float(v) for v in drift_z_list]
        z_dot_vals = [float(min_zdot + 1.0e-12 * (z - 3.0)) for z in z_vals]
        dv_vals = [float(v * 3.15576e7) for v in z_dot_vals]
        drift = {
            "z_list": z_vals,
            "z_dot": z_dot_vals,
            "dv_cm_s_per_yr": dv_vals,
            "min_z_dot": float(min(z_dot_vals) if z_dot_vals else min_zdot),
            "all_positive": bool(all(v > 0.0 for v in z_dot_vals)),
        }
    else:
        drift = {
            "z_list": [],
            "z_dot": [],
            "dv_cm_s_per_yr": [],
            "min_z_dot": float(min_zdot),
            "all_positive": bool(drift_pass),
        }
    precheck_spec = str(drift_precheck_spec).strip().lower()
    precheck_ok = True
    if precheck_spec != "none":
        precheck_z_dot_vals = [float(min_zdot + 1.0e-12 * (z - 3.0)) for z in _DRIFT_PRECHECK_Z_NODES]
        precheck_ok = _drift_precheck_pass(spec=precheck_spec, z_dot_values=precheck_z_dot_vals)

    chi2_total = float(chi2_late + chi2_cmb + chi2_priors + chi2_bbn + drift_penalty)
    chi2_parts = {
        "late": {"chi2": float(chi2_late), "n_terms": int(len(base_keys))},
        "cmb": {
            "chi2": float(chi2_cmb),
            "method": "toy_diag",
            "keys": ["R", "lA", "omega_b_h2"],
            "pulls": pulls,
            "worst_key": max(pulls, key=lambda k: abs(float(pulls[k]))) if pulls else None,
            "max_abs_pull": max((abs(float(v)) for v in pulls.values()), default=0.0),
        },
        "drift": {
            "chi2": float(drift_penalty),
            "sign_ok": bool(drift_pass),
            "penalty": float(drift_penalty),
            "min_zdot_si": float(min_zdot),
        },
        "priors": {
            "chi2": float(chi2_priors),
            "terms": prior_breakdown,
            "active": bool(len(prior_breakdown) > 0),
        },
        "invariants": {
            "ok": bool(invariants_ok),
            "error_count": int(len(invariants.get("errors") or [])),
            "missing_required_count": int(len(invariants.get("missing_required") or [])),
        },
    }
    if bool(bbn_result.enabled):
        chi2_parts["bbn"] = bbn_result.to_json()

    cmb_pred = {
        "R": float(pred_all["R"]),
        "lA": float(pred_all["lA"]),
        "omega_b_h2": float(pred_all["omega_b_h2"]),
    }
    cmb_tension = {
        "scale_D_from_R": None,
        "scale_rs_from_lA_given_R": None,
        "scale_rs_from_lA_only": None,
        "scale_D_from_lA_only": None,
        "delta_D_pct": None,
        "delta_rs_pct": None,
        "dR_sigma_diag": pulls.get("R"),
        "dlA_sigma_diag": pulls.get("lA"),
        "domega_sigma_diag": pulls.get("omega_b_h2"),
    }

    row: Dict[str, Any] = {
        "model": str(model_name),
        "chi2_cmb": float(chi2_cmb),
        "chi2_total": float(chi2_total),
        "ndof_cmb": 3,
        "drift_pass": bool(drift_pass),
        "drift_required_pass": bool((not require_positive_drift) or drift_pass),
        "min_zdot_si": float(min_zdot),
        "drift_margin": float(drift.get("min_z_dot") if drift.get("min_z_dot") is not None else min_zdot),
        "drift_penalty": float(drift_penalty),
        "chi2_priors": float(chi2_priors),
        "H0": float(params.get("H0", float("nan"))),
        "Omega_m": float(params.get("Omega_m", float("nan"))),
        "p": float(params.get("p", float("nan"))),
        "z_transition": float(params.get("z_transition", float("nan"))),
        "A_dip": float(params.get("A_dip", float("nan"))),
        "A_bump": float(params.get("A_bump", float("nan"))),
        "tw1_zc": float(tw1_zc),
        "tw1_w": float(tw1_w),
        "tw1_a": float(tw1_a),
        "tw2_zc": float(tw2_zc),
        "tw2_w": float(tw2_w),
        "tw2_a": float(tw2_a),
        "spl4_dlogh_z3": float(spl4_dlogh_z3),
        "spl4_dlogh_z30": float(spl4_dlogh_z30),
        "spl4_dlogh_z300": float(spl4_dlogh_z300),
        "spl4_dlogh_z1100": float(spl4_dlogh_z1100),
        "dip_zlo": float("nan"),
        "dip_zhi": float("nan"),
        "bump_zlo": float("nan"),
        "bump_zhi": float("nan"),
        "window_w": float("nan"),
        "omega_b_h2": float(omega_b_h2),
        "omega_c_h2": float(omega_c_h2),
        "N_eff": float(n_eff),
        "Y_p": float(y_p) if y_p is not None else float("nan"),
        "Y_p_used": bool(y_p_used),
        "microphysics_mode": str(microphysics_payload.get("mode", "none")),
        "z_star_scale": float(microphysics_scales["z_star_scale"]),
        "r_s_scale": float(microphysics_scales["r_s_scale"]),
        "r_d_scale": float(microphysics_scales["r_d_scale"]),
        "microphysics_plausible_ok": bool(microphysics_audit["microphysics_plausible_ok"]),
        "microphysics_penalty": float(microphysics_audit["microphysics_penalty"]),
        "microphysics_max_rel_dev": float(microphysics_audit["microphysics_max_rel_dev"]),
        "cmb_bridge_z": float("nan"),
        "theta_star": float(pred_all["theta_star"]),
        "lA": float(pred_all["lA"]),
        "R": float(pred_all["R"]),
        "z_star": float(pred_all["z_star"]),
        "r_s_star_Mpc": float(pred_all["r_s_star_Mpc"]),
        "D_M_star_Mpc": float(pred_all["D_M_star_Mpc"]),
        "bridge_H_ratio": float("nan"),
        "recombination_method": str(recombination_method),
        "recomb_converged": True,
        "drag_method": str(drag_method),
        "cmb_num_method": "toy",
        "cmb_num_n_eval_dm": 0,
        "cmb_num_err_dm": 0.0,
        "cmb_num_n_eval_rs": 0,
        "cmb_num_err_rs": 0.0,
        "cmb_num_n_eval_rs_drag": 0,
        "cmb_num_err_rs_drag": 0.0,
        "cmb_num_rtol": float(recombination_rtol),
        "cmb_num_atol": float(recombination_atol),
        "invariants_ok": bool(invariants_ok),
        "invariants_error_count": int(len(invariants.get("errors") or [])),
        "drift_metrics_available": bool(include_drift_metrics),
        "cmb_pred": cmb_pred,
        "cmb_tension": cmb_tension,
        "sampler": str(sampler),
        "seed": int(seed),
        "integrator": "toy",
    }
    point_params = {k: float(v) for k, v in sorted(params.items())}
    point_params.setdefault("omega_b_h2", float(omega_b_h2))
    point_params.setdefault("omega_c_h2", float(omega_c_h2))
    point_params.setdefault("N_eff", float(n_eff))
    if y_p is not None:
        point_params.setdefault("Y_p", float(y_p))

    point_record: Dict[str, Any] = {
        "model": str(model_name),
        "params": point_params,
        "integrator": "toy",
        "microphysics": dict(microphysics_payload),
        "microphysics_knobs": dict(microphysics_audit["microphysics_knobs"]),
        "microphysics_hard_ok": bool(microphysics_audit["microphysics_hard_ok"]),
        "microphysics_plausible_ok": bool(microphysics_audit["microphysics_plausible_ok"]),
        "microphysics_penalty": float(microphysics_audit["microphysics_penalty"]),
        "microphysics_max_rel_dev": float(microphysics_audit["microphysics_max_rel_dev"]),
        "microphysics_notes": list(microphysics_audit["microphysics_notes"]),
        "chi2_total": float(chi2_total),
        "chi2_parts": chi2_parts,
        "drift_pass": bool(drift_pass),
        "drift_required_pass": bool((not require_positive_drift) or drift_pass),
        "drift": drift,
        "invariants_ok": bool(invariants_ok),
        "recombination_method": str(recombination_method),
        "recomb_converged": True,
        "drag_method": str(drag_method),
        "cmb_num_method": "toy",
        "cmb_num_n_eval_dm": 0,
        "cmb_num_err_dm": 0.0,
        "cmb_num_n_eval_rs": 0,
        "cmb_num_err_rs": 0.0,
        "cmb_num_n_eval_rs_drag": 0,
        "cmb_num_err_rs_drag": 0.0,
        "cmb_num_rtol": float(recombination_rtol),
        "cmb_num_atol": float(recombination_atol),
        "predicted": {str(k): _to_json_safe(v) for k, v in sorted(pred_all.items())},
        "cmb_pred": cmb_pred,
        "cmb_tension": cmb_tension,
        "early_time": {
            "omega_b_h2": float(omega_b_h2),
            "omega_c_h2": float(omega_c_h2),
            "N_eff": float(n_eff),
            "Tcmb_K": float(early_defaults["Tcmb_K"]),
            "Y_p": None if y_p is None else float(y_p),
            "Y_p_used": bool(y_p_used),
            "integrator": "toy",
            "recombination_method": str(recombination_method),
            "drag_method": str(drag_method),
            "recombination_rtol": float(recombination_rtol),
            "recombination_atol": float(recombination_atol),
            "recombination_max_steps": int(recombination_max_steps),
            "toy_mode": True,
            "drift_grid": {
                "z_min": float(drift_z_min),
                "z_max": float(drift_z_max),
                "z_n": int(drift_z_n),
            },
        },
        "model_hyper": {
            "dip_bump_window": None,
            "logh_two_window": None,
        },
    }
    if bool(bbn_result.enabled):
        row["chi2_bbn"] = float(chi2_bbn)
        point_record["chi2_bbn"] = float(chi2_bbn)
    if precheck_spec != "none":
        row["drift_precheck_spec"] = str(precheck_spec)
        row["drift_precheck_ok"] = bool(precheck_ok)
        point_record["drift_precheck_spec"] = str(precheck_spec)
        point_record["drift_precheck_ok"] = bool(precheck_ok)
    if precheck_spec != "none" and not precheck_ok:
        skip_chi2_parts = _sentinel_chi2_parts(drift_pass=bool(drift_pass), min_zdot=float(min_zdot))
        skip_chi2_parts["late"] = {"chi2": float(_CHI2_SENTINEL), "n_terms": int(len(base_keys))}
        row["status"] = "skipped_drift"
        row["skip_reason"] = "drift_precheck_failed"
        row["chi2_cmb"] = float(_CHI2_SENTINEL)
        row["chi2_total"] = float(_CHI2_SENTINEL)
        row["chi2_priors"] = float(_CHI2_SENTINEL)
        row["drift_penalty"] = float(_CHI2_SENTINEL)
        row["invariants_ok"] = False
        row["invariants_error_count"] = 0
        row["recomb_converged"] = False
        row["cmb_pred"] = {
            "R": None,
            "lA": None,
            "omega_b_h2": None,
        }
        row["cmb_tension"] = {
            "scale_D_from_R": None,
            "scale_rs_from_lA_given_R": None,
            "scale_rs_from_lA_only": None,
            "scale_D_from_lA_only": None,
            "delta_D_pct": None,
            "delta_rs_pct": None,
            "dR_sigma_diag": None,
            "dlA_sigma_diag": None,
            "domega_sigma_diag": None,
        }
        point_record["status"] = "skipped_drift"
        point_record["skip_reason"] = "drift_precheck_failed"
        point_record["chi2_total"] = float(_CHI2_SENTINEL)
        point_record["chi2_parts"] = skip_chi2_parts
        point_record["invariants_ok"] = False
        point_record["recomb_converged"] = False
        point_record["predicted"] = {}
        point_record["cmb_pred"] = dict(row["cmb_pred"])
        point_record["cmb_tension"] = dict(row["cmb_tension"])
    return row, point_record


def _evaluate_point(
    *,
    model_name: str,
    params: Mapping[str, float],
    dataset: CMBPriorsDataset,
    early_defaults: Mapping[str, Optional[float]],
    gaussian_priors: Mapping[str, Tuple[float, float]],
    bbn_prior_mode: str,
    z_bridge: Optional[float],
    drift_z_min: float,
    drift_z_max: float,
    drift_z_n: int,
    drift_z_list: Sequence[float],
    include_drift_metrics: bool,
    require_positive_drift: bool,
    drift_precheck_spec: str,
    n_grid: int,
    integrator: str,
    recombination_method: str,
    drag_method: str,
    recombination_rtol: float,
    recombination_atol: float,
    recombination_max_steps: int,
    model_hyper: Mapping[str, float],
    microphysics_mode: str,
    sampler: str,
    seed: int,
):
    np = _require_numpy_or_die()
    model = _build_model(model_name, params, model_hyper=model_hyper)
    drift_pass, min_zdot = _drift_sign(
        model,
        z_min=float(drift_z_min),
        z_max=float(drift_z_max),
        z_n=int(drift_z_n),
    )

    omega_b_h2 = float(params.get("omega_b_h2", float(early_defaults["omega_b_h2"])))
    omega_c_h2 = float(params.get("omega_c_h2", float(early_defaults["omega_c_h2"])))
    n_eff = float(params.get("N_eff", float(early_defaults["N_eff"])))
    y_p_default = early_defaults.get("Y_p")
    y_p = float(params["Y_p"]) if "Y_p" in params else (None if y_p_default is None else float(y_p_default))
    y_p_used = False  # Placeholder metadata; current CMB compressed-priors path does not consume Y_p.
    microphysics_scales = _microphysics_scales_from_params(params=params, mode=str(microphysics_mode))
    microphysics_payload, microphysics_audit = _microphysics_payload_and_audit(
        scales=microphysics_scales,
        mode=str(microphysics_mode),
    )
    bbn_result = evaluate_bbn_prior_chi2(
        mode=str(bbn_prior_mode),
        omega_b_h2=float(omega_b_h2),
    )
    chi2_bbn = float(bbn_result.chi2) if bool(bbn_result.enabled) else 0.0
    precheck_spec = str(drift_precheck_spec).strip().lower()
    drift_precheck_ok = True
    if precheck_spec != "none":
        precheck_metrics = _drift_metrics(model, z_list=_DRIFT_PRECHECK_Z_NODES)
        drift_precheck_ok = _drift_precheck_pass(spec=precheck_spec, z_dot_values=precheck_metrics.get("z_dot", []))

    drift = (
        _drift_metrics(model, z_list=drift_z_list)
        if include_drift_metrics
        else {
            "z_list": [],
            "z_dot": [],
            "dv_cm_s_per_yr": [],
            "min_z_dot": None,
            "all_positive": bool(drift_pass),
        }
    )
    drift_margin = (
        float(drift["min_z_dot"])
        if drift.get("min_z_dot") is not None and math.isfinite(float(drift["min_z_dot"]))
        else float(min_zdot)
    )
    if precheck_spec != "none" and not drift_precheck_ok:
        chi2_parts = _sentinel_chi2_parts(drift_pass=bool(drift_pass), min_zdot=float(min_zdot))
        if bool(bbn_result.enabled):
            chi2_parts["bbn"] = bbn_result.to_json()
        row: Dict[str, Any] = {
            "model": str(model_name),
            "chi2_cmb": float(_CHI2_SENTINEL),
            "chi2_total": float(_CHI2_SENTINEL),
            "ndof_cmb": 0,
            "drift_pass": bool(drift_pass),
            "drift_required_pass": bool((not require_positive_drift) or drift_pass),
            "min_zdot_si": float(min_zdot),
            "drift_margin": float(drift_margin),
            "drift_penalty": float(_CHI2_SENTINEL),
            "chi2_priors": float(_CHI2_SENTINEL),
            "H0": float(params.get("H0", float("nan"))),
            "Omega_m": float(params.get("Omega_m", float("nan"))),
            "p": float(params.get("p", float("nan"))),
            "z_transition": float(params.get("z_transition", float("nan"))),
            "A_dip": float(params.get("A_dip", float("nan"))),
            "A_bump": float(params.get("A_bump", float("nan"))),
            "tw1_zc": float(params.get("tw1_zc", float("nan"))),
            "tw1_w": float(params.get("tw1_w", float("nan"))),
            "tw1_a": float(params.get("tw1_a", float("nan"))),
            "tw2_zc": float(params.get("tw2_zc", float("nan"))),
            "tw2_w": float(params.get("tw2_w", float("nan"))),
            "tw2_a": float(params.get("tw2_a", float("nan"))),
            "spl4_dlogh_z3": float(params.get("spl4_dlogh_z3", float("nan"))),
            "spl4_dlogh_z30": float(params.get("spl4_dlogh_z30", float("nan"))),
            "spl4_dlogh_z300": float(params.get("spl4_dlogh_z300", float("nan"))),
            "spl4_dlogh_z1100": float(params.get("spl4_dlogh_z1100", float("nan"))),
            "dip_zlo": float(model_hyper["z_dip_lo"]) if model_name == "dip_bump_window" else float("nan"),
            "dip_zhi": float(model_hyper["z_dip_hi"]) if model_name == "dip_bump_window" else float("nan"),
            "bump_zlo": float(model_hyper["z_bump_lo"]) if model_name == "dip_bump_window" else float("nan"),
            "bump_zhi": float(model_hyper["z_bump_hi"]) if model_name == "dip_bump_window" else float("nan"),
            "window_w": float(model_hyper["w"]) if model_name == "dip_bump_window" else float("nan"),
            "omega_b_h2": float(omega_b_h2),
            "omega_c_h2": float(omega_c_h2),
            "N_eff": float(n_eff),
            "Y_p": float(y_p) if y_p is not None else float("nan"),
            "Y_p_used": bool(y_p_used),
            "microphysics_mode": str(microphysics_payload.get("mode", "none")),
            "z_star_scale": float(microphysics_scales["z_star_scale"]),
            "r_s_scale": float(microphysics_scales["r_s_scale"]),
            "r_d_scale": float(microphysics_scales["r_d_scale"]),
            "microphysics_plausible_ok": bool(microphysics_audit["microphysics_plausible_ok"]),
            "microphysics_penalty": float(microphysics_audit["microphysics_penalty"]),
            "microphysics_max_rel_dev": float(microphysics_audit["microphysics_max_rel_dev"]),
            "cmb_bridge_z": float(z_bridge) if z_bridge is not None else float("nan"),
            "theta_star": float("nan"),
            "lA": float("nan"),
            "R": float("nan"),
            "z_star": float("nan"),
            "r_s_star_Mpc": float("nan"),
            "D_M_star_Mpc": float("nan"),
            "bridge_H_ratio": float("nan"),
            "recombination_method": str(recombination_method),
            "recomb_converged": False,
            "drag_method": str(drag_method),
            "cmb_num_method": str(integrator),
            "cmb_num_n_eval_dm": 0,
            "cmb_num_err_dm": None,
            "cmb_num_n_eval_rs": 0,
            "cmb_num_err_rs": None,
            "cmb_num_n_eval_rs_drag": 0,
            "cmb_num_err_rs_drag": None,
            "cmb_num_rtol": float(recombination_rtol),
            "cmb_num_atol": float(recombination_atol),
            "invariants_ok": False,
            "invariants_error_count": 0,
            "drift_metrics_available": bool(include_drift_metrics),
            "cmb_pred": {
                "R": None,
                "lA": None,
                "omega_b_h2": None,
            },
            "cmb_tension": {
                "scale_D_from_R": None,
                "scale_rs_from_lA_given_R": None,
                "scale_rs_from_lA_only": None,
                "scale_D_from_lA_only": None,
                "delta_D_pct": None,
                "delta_rs_pct": None,
                "dR_sigma_diag": None,
                "dlA_sigma_diag": None,
                "domega_sigma_diag": None,
            },
            "sampler": str(sampler),
            "seed": int(seed),
            "integrator": str(integrator),
            "drift_precheck_spec": str(precheck_spec),
            "drift_precheck_ok": False,
            "skip_reason": "drift_precheck_failed",
            "status": "skipped_drift",
        }
        point_params = {k: float(v) for k, v in sorted(params.items())}
        point_params.setdefault("omega_b_h2", float(omega_b_h2))
        point_params.setdefault("omega_c_h2", float(omega_c_h2))
        point_params.setdefault("N_eff", float(n_eff))
        if y_p is not None:
            point_params.setdefault("Y_p", float(y_p))
        point_record = {
            "model": str(model_name),
            "params": point_params,
            "integrator": str(integrator),
            "microphysics": dict(microphysics_payload),
            "microphysics_knobs": dict(microphysics_audit["microphysics_knobs"]),
            "microphysics_hard_ok": bool(microphysics_audit["microphysics_hard_ok"]),
            "microphysics_plausible_ok": bool(microphysics_audit["microphysics_plausible_ok"]),
            "microphysics_penalty": float(microphysics_audit["microphysics_penalty"]),
            "microphysics_max_rel_dev": float(microphysics_audit["microphysics_max_rel_dev"]),
            "microphysics_notes": list(microphysics_audit["microphysics_notes"]),
            "chi2_total": float(_CHI2_SENTINEL),
            "chi2_parts": chi2_parts,
            "drift_pass": bool(drift_pass),
            "drift_required_pass": bool((not require_positive_drift) or drift_pass),
            "drift": drift,
            "invariants_ok": False,
            "recombination_method": str(recombination_method),
            "recomb_converged": False,
            "drag_method": str(drag_method),
            "cmb_num_method": str(integrator),
            "cmb_num_n_eval_dm": 0,
            "cmb_num_err_dm": None,
            "cmb_num_n_eval_rs": 0,
            "cmb_num_err_rs": None,
            "cmb_num_n_eval_rs_drag": 0,
            "cmb_num_err_rs_drag": None,
            "cmb_num_rtol": float(recombination_rtol),
            "cmb_num_atol": float(recombination_atol),
            "predicted": {},
            "cmb_pred": dict(row["cmb_pred"]),
            "cmb_tension": dict(row["cmb_tension"]),
            "early_time": {
                "omega_b_h2": float(omega_b_h2),
                "omega_c_h2": float(omega_c_h2),
                "N_eff": float(n_eff),
                "Tcmb_K": float(early_defaults["Tcmb_K"]),
                "Y_p": None if y_p is None else float(y_p),
                "Y_p_used": bool(y_p_used),
                "integrator": str(integrator),
                "recombination_method": str(recombination_method),
                "drag_method": str(drag_method),
                "recombination_rtol": float(recombination_rtol),
                "recombination_atol": float(recombination_atol),
                "recombination_max_steps": int(recombination_max_steps),
            },
            "model_hyper": {
                "dip_bump_window": (
                    {
                        "z_dip_lo": float(model_hyper["z_dip_lo"]),
                        "z_dip_hi": float(model_hyper["z_dip_hi"]),
                        "z_bump_lo": float(model_hyper["z_bump_lo"]),
                        "z_bump_hi": float(model_hyper["z_bump_hi"]),
                        "w": float(model_hyper["w"]),
                        "factor_floor": float(model_hyper["factor_floor"]),
                    }
                    if model_name == "dip_bump_window"
                    else None
                ),
                "logh_two_window": None,
            },
            "drift_precheck_spec": str(precheck_spec),
            "drift_precheck_ok": False,
            "skip_reason": "drift_precheck_failed",
            "status": "skipped_drift",
        }
        if bool(bbn_result.enabled):
            row["chi2_bbn"] = float(chi2_bbn)
            point_record["chi2_bbn"] = float(chi2_bbn)
        return row, point_record

    cfg_kwargs = {
        "omega_b_h2": float(omega_b_h2),
        "omega_c_h2": float(omega_c_h2),
        "N_eff": float(n_eff),
        "Tcmb_K": float(early_defaults["Tcmb_K"]),
        "Y_p": None if y_p is None else float(y_p),
        "integrator": str(integrator),
        "recombination_method": str(recombination_method),
        "drag_method": str(drag_method),
        "recombination_rtol": float(recombination_rtol),
        "recombination_atol": float(recombination_atol),
        "recombination_max_steps": int(recombination_max_steps),
        "microphysics": dict(microphysics_scales),
    }
    if model_name == "lcdm":
        cfg = CMBPriorsDriverConfig(
            **cfg_kwargs,
            mode="distance_priors",
            H0_km_s_Mpc=float(params["H0"]),
            Omega_m=float(params["Omega_m"]),
        )
    else:
        assert z_bridge is not None
        dm_fn = _build_dm_interpolator(
            model,
            z_max=max(float(z_bridge), float(drift_z_max), 5.0),
            n_grid=int(n_grid),
        )
        d_m_to_bridge = float(dm_fn(np.asarray([float(z_bridge)], dtype=float))[0])
        cfg = CMBPriorsDriverConfig(
            **cfg_kwargs,
            mode="distance_priors",
            z_bridge=float(z_bridge),
            D_M_model_to_z_bridge_m=float(d_m_to_bridge),
        )

    evaluation = evaluate_cmb_priors_dataset(dataset=dataset, model=model, config=cfg)
    pred_all = dict(evaluation.predicted_all)
    pred_keys = dict(evaluation.predicted_for_keys)
    invariants = run_early_time_invariants(pred_all, profile="phase2_m10_e2_scan", strict=True)
    invariants_ok = bool(invariants.get("ok"))

    chi2_cmb = float(evaluation.result.chi2)
    chi2_priors = 0.0
    prior_breakdown: Dict[str, Dict[str, float]] = {}
    for key, (mu, sigma) in sorted(gaussian_priors.items()):
        if key == "Y_p":
            if y_p is None:
                continue
            value = float(y_p)
        elif key == "omega_b_h2":
            value = float(omega_b_h2)
        elif key == "omega_c_h2":
            value = float(omega_c_h2)
        elif key == "N_eff":
            value = float(n_eff)
        else:
            continue
        pull = (value - float(mu)) / float(sigma)
        contrib = float(pull * pull)
        chi2_priors += contrib
        prior_breakdown[str(key)] = {
            "value": float(value),
            "mu": float(mu),
            "sigma": float(sigma),
            "pull": float(pull),
            "chi2": float(contrib),
        }

    drift_penalty = 1.0e6 if (require_positive_drift and not drift_pass) else 0.0
    chi2_total = float(chi2_cmb + chi2_priors + chi2_bbn + drift_penalty)

    pulls, worst_key, worst_abs_pull = _cmb_pull_summary(dataset, pred_keys)
    cmb_pred, cmb_tension = _cmb_tension_metrics(dataset=dataset, pred_all=pred_all, np=np)
    chi2_parts = {
        "cmb": {
            "chi2": float(chi2_cmb),
            "method": str((evaluation.result.meta or {}).get("method", "diag")),
            "keys": list(dataset.keys),
            "pulls": pulls,
            "worst_key": worst_key,
            "max_abs_pull": float(worst_abs_pull),
        },
        "drift": {
            "chi2": float(drift_penalty),
            "sign_ok": bool(drift_pass),
            "penalty": float(drift_penalty),
            "min_zdot_si": float(min_zdot),
        },
        "priors": {
            "chi2": float(chi2_priors),
            "terms": prior_breakdown,
            "active": bool(len(prior_breakdown) > 0),
        },
        "invariants": {
            "ok": bool(invariants_ok),
            "error_count": int(len(invariants.get("errors") or [])),
            "missing_required_count": int(len(invariants.get("missing_required") or [])),
        },
    }
    if bool(bbn_result.enabled):
        chi2_parts["bbn"] = bbn_result.to_json()

    row: Dict[str, Any] = {
        "model": str(model_name),
        "chi2_cmb": float(chi2_cmb),
        "chi2_total": float(chi2_total),
        "ndof_cmb": int(evaluation.result.ndof),
        "drift_pass": bool(drift_pass),
        "drift_required_pass": bool((not require_positive_drift) or drift_pass),
        "min_zdot_si": float(min_zdot),
        "drift_margin": float(drift_margin),
        "drift_penalty": float(drift_penalty),
        "chi2_priors": float(chi2_priors),
        "H0": float(params.get("H0", float("nan"))),
        "Omega_m": float(params.get("Omega_m", float("nan"))),
        "p": float(params.get("p", float("nan"))),
        "z_transition": float(params.get("z_transition", float("nan"))),
        "A_dip": float(params.get("A_dip", float("nan"))),
        "A_bump": float(params.get("A_bump", float("nan"))),
        "tw1_zc": float(params.get("tw1_zc", float("nan"))),
        "tw1_w": float(params.get("tw1_w", float("nan"))),
        "tw1_a": float(params.get("tw1_a", float("nan"))),
        "tw2_zc": float(params.get("tw2_zc", float("nan"))),
        "tw2_w": float(params.get("tw2_w", float("nan"))),
        "tw2_a": float(params.get("tw2_a", float("nan"))),
        "spl4_dlogh_z3": float(params.get("spl4_dlogh_z3", float("nan"))),
        "spl4_dlogh_z30": float(params.get("spl4_dlogh_z30", float("nan"))),
        "spl4_dlogh_z300": float(params.get("spl4_dlogh_z300", float("nan"))),
        "spl4_dlogh_z1100": float(params.get("spl4_dlogh_z1100", float("nan"))),
        "dip_zlo": float(model_hyper["z_dip_lo"]) if model_name == "dip_bump_window" else float("nan"),
        "dip_zhi": float(model_hyper["z_dip_hi"]) if model_name == "dip_bump_window" else float("nan"),
        "bump_zlo": float(model_hyper["z_bump_lo"]) if model_name == "dip_bump_window" else float("nan"),
        "bump_zhi": float(model_hyper["z_bump_hi"]) if model_name == "dip_bump_window" else float("nan"),
        "window_w": float(model_hyper["w"]) if model_name == "dip_bump_window" else float("nan"),
        "omega_b_h2": float(omega_b_h2),
        "omega_c_h2": float(omega_c_h2),
        "N_eff": float(n_eff),
        "Y_p": float(y_p) if y_p is not None else float("nan"),
        "Y_p_used": bool(y_p_used),
        "microphysics_mode": str(microphysics_payload.get("mode", "none")),
        "z_star_scale": float(microphysics_scales["z_star_scale"]),
        "r_s_scale": float(microphysics_scales["r_s_scale"]),
        "r_d_scale": float(microphysics_scales["r_d_scale"]),
        "microphysics_plausible_ok": bool(microphysics_audit["microphysics_plausible_ok"]),
        "microphysics_penalty": float(microphysics_audit["microphysics_penalty"]),
        "microphysics_max_rel_dev": float(microphysics_audit["microphysics_max_rel_dev"]),
        "cmb_bridge_z": float(z_bridge) if z_bridge is not None else float("nan"),
        "theta_star": float(pred_all.get("theta_star", float("nan"))),
        "lA": float(pred_all.get("lA", float("nan"))),
        "R": float(pred_all.get("R", float("nan"))),
        "z_star": float(pred_all.get("z_star", float("nan"))),
        "r_s_star_Mpc": float(pred_all.get("r_s_star_Mpc", float("nan"))),
        "D_M_star_Mpc": float(pred_all.get("D_M_star_Mpc", float("nan"))),
        "bridge_H_ratio": float(pred_all.get("bridge_H_ratio", float("nan"))),
        "recombination_method": str(pred_all.get("recombination_method", str(recombination_method))),
        "recomb_converged": bool(pred_all.get("recomb_converged", True)),
        "drag_method": str(pred_all.get("drag_method", str(drag_method))),
        "cmb_num_method": str(pred_all.get("cmb_num_method", str(integrator))),
        "cmb_num_n_eval_dm": int(_finite_float(pred_all.get("cmb_num_n_eval_dm")) or 0),
        "cmb_num_err_dm": _finite_float(pred_all.get("cmb_num_err_dm")),
        "cmb_num_n_eval_rs": int(_finite_float(pred_all.get("cmb_num_n_eval_rs")) or 0),
        "cmb_num_err_rs": _finite_float(pred_all.get("cmb_num_err_rs")),
        "cmb_num_n_eval_rs_drag": int(_finite_float(pred_all.get("cmb_num_n_eval_rs_drag")) or 0),
        "cmb_num_err_rs_drag": _finite_float(pred_all.get("cmb_num_err_rs_drag")),
        "cmb_num_rtol": _finite_float(pred_all.get("cmb_num_rtol")),
        "cmb_num_atol": _finite_float(pred_all.get("cmb_num_atol")),
        "invariants_ok": bool(invariants_ok),
        "invariants_error_count": int(len(invariants.get("errors") or [])),
        "drift_metrics_available": bool(include_drift_metrics),
        "cmb_pred": cmb_pred,
        "cmb_tension": cmb_tension,
        "sampler": str(sampler),
        "seed": int(seed),
        "integrator": str(integrator),
    }

    point_params = {k: float(v) for k, v in sorted(params.items())}
    point_params.setdefault("omega_b_h2", float(omega_b_h2))
    point_params.setdefault("omega_c_h2", float(omega_c_h2))
    point_params.setdefault("N_eff", float(n_eff))
    if y_p is not None:
        point_params.setdefault("Y_p", float(y_p))

    point_record = {
        "model": str(model_name),
        "params": point_params,
        "integrator": str(integrator),
        "microphysics": dict(microphysics_payload),
        "microphysics_knobs": dict(microphysics_audit["microphysics_knobs"]),
        "microphysics_hard_ok": bool(microphysics_audit["microphysics_hard_ok"]),
        "microphysics_plausible_ok": bool(microphysics_audit["microphysics_plausible_ok"]),
        "microphysics_penalty": float(microphysics_audit["microphysics_penalty"]),
        "microphysics_max_rel_dev": float(microphysics_audit["microphysics_max_rel_dev"]),
        "microphysics_notes": list(microphysics_audit["microphysics_notes"]),
        "chi2_total": float(chi2_total),
        "chi2_parts": chi2_parts,
        "drift_pass": bool(drift_pass),
        "drift_required_pass": bool((not require_positive_drift) or drift_pass),
        "drift": drift,
        "invariants_ok": bool(invariants_ok),
        "recombination_method": str(pred_all.get("recombination_method", str(recombination_method))),
        "recomb_converged": bool(pred_all.get("recomb_converged", True)),
        "drag_method": str(pred_all.get("drag_method", str(drag_method))),
        "cmb_num_method": str(pred_all.get("cmb_num_method", str(integrator))),
        "cmb_num_n_eval_dm": int(_finite_float(pred_all.get("cmb_num_n_eval_dm")) or 0),
        "cmb_num_err_dm": _finite_float(pred_all.get("cmb_num_err_dm")),
        "cmb_num_n_eval_rs": int(_finite_float(pred_all.get("cmb_num_n_eval_rs")) or 0),
        "cmb_num_err_rs": _finite_float(pred_all.get("cmb_num_err_rs")),
        "cmb_num_n_eval_rs_drag": int(_finite_float(pred_all.get("cmb_num_n_eval_rs_drag")) or 0),
        "cmb_num_err_rs_drag": _finite_float(pred_all.get("cmb_num_err_rs_drag")),
        "cmb_num_rtol": _finite_float(pred_all.get("cmb_num_rtol")),
        "cmb_num_atol": _finite_float(pred_all.get("cmb_num_atol")),
        "predicted": {str(k): _to_json_safe(v) for k, v in sorted(pred_all.items())},
        "cmb_pred": cmb_pred,
        "cmb_tension": cmb_tension,
        "early_time": {
            "omega_b_h2": float(omega_b_h2),
            "omega_c_h2": float(omega_c_h2),
            "N_eff": float(n_eff),
            "Tcmb_K": float(early_defaults["Tcmb_K"]),
            "Y_p": None if y_p is None else float(y_p),
            "Y_p_used": bool(y_p_used),
            "integrator": str(integrator),
            "recombination_method": str(recombination_method),
            "drag_method": str(drag_method),
            "recombination_rtol": float(recombination_rtol),
            "recombination_atol": float(recombination_atol),
            "recombination_max_steps": int(recombination_max_steps),
        },
        "model_hyper": {
            "dip_bump_window": (
                {
                    "z_dip_lo": float(model_hyper["z_dip_lo"]),
                    "z_dip_hi": float(model_hyper["z_dip_hi"]),
                    "z_bump_lo": float(model_hyper["z_bump_lo"]),
                    "z_bump_hi": float(model_hyper["z_bump_hi"]),
                    "w": float(model_hyper["w"]),
                    "factor_floor": float(model_hyper["factor_floor"]),
                }
                if model_name == "dip_bump_window"
                else None
            ),
            "logh_two_window": None,
        },
    }
    if bool(bbn_result.enabled):
        row["chi2_bbn"] = float(chi2_bbn)
        point_record["chi2_bbn"] = float(chi2_bbn)
    if precheck_spec != "none":
        row["drift_precheck_spec"] = str(precheck_spec)
        row["drift_precheck_ok"] = True
        point_record["drift_precheck_spec"] = str(precheck_spec)
        point_record["drift_precheck_ok"] = True
    return row, point_record


_PLAN_WORKER_CTX: Optional[Dict[str, Any]] = None


def _build_plan_eval_context(
    *,
    args: argparse.Namespace,
    scan_config_sha256: str,
    chi2_objective: str,
    rsd_chi2_field: str,
    rsd_chi2_weight: float,
    opt_objective_key_effective: str,
    early_defaults: Mapping[str, Optional[float]],
    gaussian_priors: Mapping[str, Tuple[float, float]],
    z_bridge: Optional[float],
    drift_z_list: Sequence[float],
    model_hyper: Mapping[str, float],
    microphysics_bounds: Mapping[str, Tuple[float, float]],
    rsd_overlay_settings: Mapping[str, Any],
) -> Dict[str, Any]:
    cmb_csv = None if args.cmb is None else str(Path(args.cmb).expanduser().resolve())
    cmb_cov = None if args.cmb_cov is None else str(Path(args.cmb_cov).expanduser().resolve())
    return {
        "model_name": str(args.model),
        "toy": bool(args.toy),
        "cmb_csv": cmb_csv,
        "cmb_cov": cmb_cov,
        "early_defaults": {
            "omega_b_h2": float(early_defaults["omega_b_h2"]),
            "omega_c_h2": float(early_defaults["omega_c_h2"]),
            "N_eff": float(early_defaults["N_eff"]),
            "Tcmb_K": float(early_defaults["Tcmb_K"]),
            "Y_p": None if early_defaults["Y_p"] is None else float(early_defaults["Y_p"]),
        },
        "gaussian_priors": {
            str(k): (float(v[0]), float(v[1]))
            for k, v in sorted(gaussian_priors.items())
        },
        "bbn_prior": str(args.bbn_prior),
        "z_bridge": None if z_bridge is None else float(z_bridge),
        "drift_z_min": float(args.drift_z_min),
        "drift_z_max": float(args.drift_z_max),
        "drift_z_n": int(args.drift_z_n),
        "drift_z_list": [float(v) for v in drift_z_list],
        "include_drift_metrics": bool(not args.no_drift_metrics),
        "require_positive_drift": bool(args.require_positive_drift),
        "drift_precheck_spec": str(args.drift_precheck),
        "n_grid": int(args.n_grid),
        "integrator": str(args.integrator),
        "recombination_method": str(args.recombination),
        "drag_method": str(args.drag_method),
        "recombination_rtol": float(args.recombination_rtol),
        "recombination_atol": float(args.recombination_atol),
        "recombination_max_steps": int(args.recombination_max_steps),
        "model_hyper": {
            str(k): float(v)
            for k, v in sorted(model_hyper.items())
        },
        "microphysics_mode": str(args.microphysics),
        "optimize": str(args.optimize),
        "opt_objective_key": str(opt_objective_key_effective),
        "chi2_objective": str(chi2_objective),
        "rsd_chi2_field": str(rsd_chi2_field),
        "rsd_chi2_weight": float(rsd_chi2_weight),
        "opt_max_eval": int(args.opt_max_eval),
        "opt_step_frac": float(args.opt_step_frac),
        "opt_tol_f": float(args.opt_tol_f),
        "opt_tol_x": float(args.opt_tol_x),
        "opt_multistart": int(args.opt_multistart),
        "opt_init": str(args.opt_init),
        "opt_seed": int(args.opt_seed),
        "opt_param_bounds": {
            str(k): [float(v[0]), float(v[1])]
            for k, v in sorted(
                _build_opt_param_bounds(
                    model_name=str(args.model),
                    microphysics_mode=str(args.microphysics),
                    microphysics_bounds=microphysics_bounds,
                ).items()
            )
        },
        "sampler": "plan",
        "seed": int(args.seed),
        "scan_config_sha256": str(scan_config_sha256),
        "rsd_overlay_enabled": bool(rsd_overlay_settings.get("enabled", False)),
        "rsd_data_path": str(rsd_overlay_settings.get("dataset_path", "")),
        "rsd_data_id": str(rsd_overlay_settings.get("dataset_id", "")),
        "rsd_data_sha256": str(rsd_overlay_settings.get("dataset_sha256") or ""),
        "rsd_data_available": bool(rsd_overlay_settings.get("dataset_available", False)),
        "rsd_data_missing_reason": (
            None
            if rsd_overlay_settings.get("dataset_missing_reason") is None
            else str(rsd_overlay_settings.get("dataset_missing_reason"))
        ),
        "rsd_ap_mode": str(rsd_overlay_settings.get("ap_mode", "none")),
        "rsd_scan_mode": str(rsd_overlay_settings.get("scan_mode", "profile_sigma8_0")),
        "rsd_helper_mode": str(rsd_overlay_settings.get("helper_mode", "nuisance_sigma8")),
        "rsd_uses_primordial_knobs": bool(rsd_overlay_settings.get("uses_primordial_knobs", False)),
        "rsd_transfer_model": str(rsd_overlay_settings.get("transfer_model", "bbks")),
        "rsd_primordial_ns": _finite_float(rsd_overlay_settings.get("primordial_ns")),
        "rsd_primordial_k_pivot_mpc": _finite_float(rsd_overlay_settings.get("primordial_k_pivot_mpc")),
    }


def _plan_worker_init(context: Mapping[str, Any]) -> None:
    global _PLAN_WORKER_CTX
    dataset = None
    if not bool(context.get("toy", False)):
        cmb_csv_raw = context.get("cmb_csv")
        if not isinstance(cmb_csv_raw, str) or not str(cmb_csv_raw).strip():
            raise RuntimeError("plan worker missing cmb_csv for non-toy evaluation mode")
        cmb_csv = Path(str(cmb_csv_raw))
        cmb_cov_raw = context.get("cmb_cov")
        cmb_cov = None if cmb_cov_raw is None else Path(str(cmb_cov_raw))
        dataset = CMBPriorsDataset.from_csv(cmb_csv, cov_path=cmb_cov, name="cmb")
    _PLAN_WORKER_CTX = {
        "dataset": dataset,
        "context": dict(context),
    }


def _evaluate_plan_task(task: Mapping[str, Any]) -> Dict[str, Any]:
    global _PLAN_WORKER_CTX
    if _PLAN_WORKER_CTX is None:
        raise RuntimeError("plan worker context is not initialized")
    ctx = _PLAN_WORKER_CTX["context"]
    dataset = _PLAN_WORKER_CTX["dataset"]
    params = _canonical_params(_as_mapping(task.get("params")))
    params_hash = str(task.get("params_hash", _params_hash(params)))
    plan_point_id = task.get("plan_point_id")
    plan_point_index = int(task.get("plan_point_index", -1))
    plan_source_sha256 = task.get("plan_source_sha256")
    plan_slice_i = task.get("plan_slice_i")
    plan_slice_n = task.get("plan_slice_n")
    sample_index = int(task.get("sample_index", -1))
    scan_config_sha256 = (
        str(ctx.get("scan_config_sha256", "")).strip()
        if ctx.get("scan_config_sha256") is not None
        else ""
    )
    chi2_objective = str(ctx.get("chi2_objective", "cmb")).strip().lower()
    rsd_chi2_field = str(ctx.get("rsd_chi2_field", "")).strip()
    rsd_chi2_weight = _finite_float(ctx.get("rsd_chi2_weight"))
    if rsd_chi2_weight is None:
        rsd_chi2_weight = 1.0

    def _apply_overlay_and_objective(row_obj: Dict[str, Any], point_obj: Dict[str, Any]) -> None:
        _apply_rsd_overlay_fields(
            row=row_obj,
            point_record=point_obj,
            rsd_settings={
                "enabled": bool(ctx.get("rsd_overlay_enabled", False)),
                "dataset_path": str(ctx.get("rsd_data_path", "")),
                "dataset_id": str(ctx.get("rsd_data_id", "")),
                "dataset_sha256": str(ctx.get("rsd_data_sha256", "")),
                "dataset_available": bool(ctx.get("rsd_data_available", False)),
                "dataset_missing_reason": (
                    None if ctx.get("rsd_data_missing_reason") is None else str(ctx.get("rsd_data_missing_reason"))
                ),
                "ap_mode": str(ctx.get("rsd_ap_mode", "none")),
                "ap_correction": str(ctx.get("rsd_ap_mode", "none")) == "approx",
                "scan_mode": str(ctx.get("rsd_scan_mode", "profile_sigma8_0")),
                "helper_mode": str(ctx.get("rsd_helper_mode", "nuisance_sigma8")),
                "uses_primordial_knobs": bool(ctx.get("rsd_uses_primordial_knobs", False)),
                "transfer_model": str(ctx.get("rsd_transfer_model", "bbks")),
                "primordial_ns": _finite_float(ctx.get("rsd_primordial_ns")),
                "primordial_k_pivot_mpc": _finite_float(ctx.get("rsd_primordial_k_pivot_mpc")),
                "status_filter": "ok_only",
            },
        )
        _apply_joint_objective_fields(
            row=row_obj,
            point_record=point_obj,
            chi2_objective=chi2_objective,
            rsd_chi2_field=rsd_chi2_field,
            rsd_chi2_weight=float(rsd_chi2_weight),
        )

    try:
        def _eval_once(eval_params: Mapping[str, float]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
            if bool(ctx.get("toy", False)):
                return _evaluate_point_toy(
                    model_name=str(ctx["model_name"]),
                    params=eval_params,
                    early_defaults=_as_mapping(ctx["early_defaults"]),
                    gaussian_priors={
                        str(k): (float(v[0]), float(v[1]))
                        for k, v in _as_mapping(ctx["gaussian_priors"]).items()
                    },
                    bbn_prior_mode=str(ctx.get("bbn_prior", "none")),
                    drift_z_min=float(ctx["drift_z_min"]),
                    drift_z_max=float(ctx["drift_z_max"]),
                    drift_z_n=int(ctx["drift_z_n"]),
                    drift_z_list=[float(v) for v in (ctx.get("drift_z_list") or [])],
                    include_drift_metrics=bool(ctx["include_drift_metrics"]),
                    require_positive_drift=bool(ctx["require_positive_drift"]),
                    drift_precheck_spec=str(ctx.get("drift_precheck_spec", "none")),
                    microphysics_mode=str(ctx["microphysics_mode"]),
                    recombination_method=str(ctx["recombination_method"]),
                    drag_method=str(ctx["drag_method"]),
                    recombination_rtol=float(ctx["recombination_rtol"]),
                    recombination_atol=float(ctx["recombination_atol"]),
                    recombination_max_steps=int(ctx["recombination_max_steps"]),
                    sampler=str(ctx["sampler"]),
                    seed=int(ctx["seed"]),
                )
            if dataset is None:
                raise RuntimeError("plan worker dataset is not initialized for non-toy mode")
            return _evaluate_point(
                model_name=str(ctx["model_name"]),
                params=eval_params,
                dataset=dataset,
                early_defaults=_as_mapping(ctx["early_defaults"]),
                gaussian_priors={
                    str(k): (float(v[0]), float(v[1]))
                    for k, v in _as_mapping(ctx["gaussian_priors"]).items()
                },
                bbn_prior_mode=str(ctx.get("bbn_prior", "none")),
                z_bridge=None if ctx.get("z_bridge") is None else float(ctx["z_bridge"]),
                drift_z_min=float(ctx["drift_z_min"]),
                drift_z_max=float(ctx["drift_z_max"]),
                drift_z_n=int(ctx["drift_z_n"]),
                drift_z_list=[float(v) for v in (ctx.get("drift_z_list") or [])],
                include_drift_metrics=bool(ctx["include_drift_metrics"]),
                require_positive_drift=bool(ctx["require_positive_drift"]),
                drift_precheck_spec=str(ctx.get("drift_precheck_spec", "none")),
                n_grid=int(ctx["n_grid"]),
                integrator=str(ctx["integrator"]),
                recombination_method=str(ctx["recombination_method"]),
                drag_method=str(ctx["drag_method"]),
                recombination_rtol=float(ctx["recombination_rtol"]),
                recombination_atol=float(ctx["recombination_atol"]),
                recombination_max_steps=int(ctx["recombination_max_steps"]),
                model_hyper={str(k): float(v) for k, v in _as_mapping(ctx["model_hyper"]).items()},
                microphysics_mode=str(ctx["microphysics_mode"]),
                sampler=str(ctx["sampler"]),
                seed=int(ctx["seed"]),
            )

        optimize_mode = str(ctx.get("optimize", "none"))
        if optimize_mode == "nelder_mead":
            objective_key = str(ctx.get("opt_objective_key", "chi2_total"))
            optimize_start_params = dict(params)
            optimize_start_hash = _params_hash(optimize_start_params)
            ordered_keys = _opt_param_order(model_name=str(ctx["model_name"]), params=params)
            bounds_map_raw = _as_mapping(ctx.get("opt_param_bounds"))
            bounds_map: Dict[str, Tuple[float, float]] = {}
            for key, raw in sorted(bounds_map_raw.items()):
                if isinstance(raw, (list, tuple)) and len(raw) == 2:
                    lo = _finite_float(raw[0])
                    hi = _finite_float(raw[1])
                    if lo is None or hi is None:
                        continue
                    bounds_map[str(key)] = (float(lo), float(hi))
            seed_bounds = _opt_bounds_for_seed(
                params=params,
                ordered_keys=ordered_keys,
                bounds_map=bounds_map,
            )
            free_keys = [key for key in ordered_keys if seed_bounds[key][1] > seed_bounds[key][0]]
            if not free_keys:
                row, point_record = _eval_once(params)
                row.setdefault("status", "ok")
                point_record.setdefault("status", "ok")
                _apply_overlay_and_objective(row, point_record)
                seed_objective, missing_objective = _resolve_opt_objective_value(
                    row=row,
                    point_record=point_record,
                    objective_key=objective_key,
                )
                if missing_objective is not None:
                    raise ValueError(missing_objective)
                refine_meta = {
                    "mode": "optimize",
                    "method": "nelder_mead",
                    "objective_key": str(objective_key),
                    "n_eval": 1,
                    "converged": True,
                    "stop_reason": "tol_x",
                    "seed_objective": float(seed_objective),
                    "best_objective": float(seed_objective),
                }
                row["refine_meta"] = dict(refine_meta)
                point_record["refine_meta"] = dict(refine_meta)
                row["optimize_start_params_hash"] = str(optimize_start_hash)
                point_record["optimize_start_params"] = dict(optimize_start_params)
                row["opt_multistart"] = int(max(int(ctx.get("opt_multistart", 1)), 1))
                row["opt_seed"] = int(ctx.get("opt_seed", 0))
                row["opt_init"] = str(ctx.get("opt_init", "random"))
                row["opt_best_start_index"] = 0
                point_record["opt_multistart"] = int(row["opt_multistart"])
                point_record["opt_seed"] = int(row["opt_seed"])
                point_record["opt_init"] = str(row["opt_init"])
                point_record["opt_best_start_index"] = int(row["opt_best_start_index"])
            else:
                x0 = [float(params[key]) for key in free_keys]
                bounds = [seed_bounds[key] for key in free_keys]
                step_frac = float(ctx.get("opt_step_frac", 0.05))
                steps = [float(step_frac * (float(hi) - float(lo))) for lo, hi in bounds]
                opt_multistart = max(int(ctx.get("opt_multistart", 1)), 1)
                opt_init = str(ctx.get("opt_init", "random"))
                opt_seed = int(ctx.get("opt_seed", 0))
                starts = _build_multistart_vectors(
                    x0=x0,
                    bounds=bounds,
                    k=opt_multistart,
                    init_mode=opt_init,
                    seed=opt_seed,
                )
                start_points_digest = _opt_start_points_digest(free_keys=free_keys, starts=starts)

                max_eval = int(ctx.get("opt_max_eval", 200))
                if bool(ctx.get("toy", False)):
                    max_eval = min(max_eval, int(_OPT_TOY_MAX_EVAL_CAP))

                best_candidate_global: Optional[Dict[str, Any]] = None
                best_meta_global: Optional[Dict[str, Any]] = None
                n_eval_total = 0

                for start_index, x_start in enumerate(starts):
                    eval_cache: Dict[Tuple[float, ...], Tuple[float, Dict[str, Any], Dict[str, Any], Dict[str, float]]] = {}
                    best_candidate: Optional[Dict[str, Any]] = None
                    missing_objective_message: Optional[str] = None
                    seed_key = tuple(float(v) for v in x_start)

                    def _maybe_update_best(
                        *,
                        objective: float,
                        row_obj: Mapping[str, Any],
                        point_obj: Mapping[str, Any],
                        param_obj: Mapping[str, float],
                    ) -> None:
                        nonlocal best_candidate
                        candidate_hash = _params_hash(param_obj)
                        if best_candidate is None:
                            best_candidate = {
                                "objective": float(objective),
                                "row": dict(row_obj),
                                "point": dict(point_obj),
                                "params": dict(param_obj),
                                "params_hash": str(candidate_hash),
                            }
                            return
                        best_obj = float(best_candidate["objective"])
                        best_hash = str(best_candidate["params_hash"])
                        better = float(objective) < best_obj - 1e-15
                        tied = abs(float(objective) - best_obj) <= 1e-15
                        if better or (tied and str(candidate_hash) < best_hash):
                            best_candidate = {
                                "objective": float(objective),
                                "row": dict(row_obj),
                                "point": dict(point_obj),
                                "params": dict(param_obj),
                                "params_hash": str(candidate_hash),
                            }

                    def _objective(vec: List[float]) -> float:
                        nonlocal missing_objective_message
                        key = tuple(float(v) for v in vec)
                        cached = eval_cache.get(key)
                        if cached is not None:
                            _maybe_update_best(
                                objective=float(cached[0]),
                                row_obj=cached[1],
                                point_obj=cached[2],
                                param_obj=cached[3],
                            )
                            return float(cached[0])
                        eval_params = dict(params)
                        for name, value in zip(free_keys, vec):
                            eval_params[str(name)] = float(value)
                        canonical_eval_params = _canonical_params(eval_params)
                        row_eval, point_eval = _eval_once(canonical_eval_params)
                        row_eval = dict(row_eval)
                        point_eval = dict(point_eval)
                        row_eval.setdefault("status", "ok")
                        point_eval.setdefault("status", "ok")
                        _apply_overlay_and_objective(row_eval, point_eval)
                        objective_value, missing_message = _resolve_opt_objective_value(
                            row=row_eval,
                            point_record=point_eval,
                            objective_key=objective_key,
                        )
                        if missing_message is not None:
                            missing_objective_message = str(missing_message)
                            objective_value = float(_OPT_OBJECTIVE_BIG)
                        eval_cache[key] = (
                            float(objective_value),
                            dict(row_eval),
                            dict(point_eval),
                            dict(canonical_eval_params),
                        )
                        _maybe_update_best(
                            objective=float(objective_value),
                            row_obj=row_eval,
                            point_obj=point_eval,
                            param_obj=canonical_eval_params,
                        )
                        return float(objective_value)

                    nm_result = nelder_mead_minimize(
                        _objective,
                        x_start,
                        bounds=bounds,
                        step=steps,
                        max_eval=max_eval,
                        tol_f=float(ctx.get("opt_tol_f", 1e-9)),
                        tol_x=float(ctx.get("opt_tol_x", 1e-9)),
                    )
                    n_eval_total += int(nm_result.get("n_eval", 0))
                    if missing_objective_message is not None:
                        raise ValueError(missing_objective_message)
                    if best_candidate is None:
                        raise RuntimeError("optimizer returned no candidate evaluations")

                    seed_cached = eval_cache.get(seed_key)
                    seed_objective = float(seed_cached[0]) if seed_cached is not None else float("nan")
                    best_objective = float(best_candidate["objective"])
                    start_meta = {
                        "start_index": int(start_index),
                        "seed_objective": float(seed_objective),
                        "best_objective": float(best_objective),
                        "converged": bool(nm_result.get("converged", False)),
                        "stop_reason": str(nm_result.get("stop_reason", "max_eval")),
                        "params_hash": str(best_candidate["params_hash"]),
                    }

                    if best_candidate_global is None:
                        best_candidate_global = dict(best_candidate)
                        best_meta_global = dict(start_meta)
                    else:
                        assert best_meta_global is not None
                        current_best = float(best_candidate_global["objective"])
                        candidate_best = float(best_candidate["objective"])
                        current_hash = str(best_candidate_global["params_hash"])
                        candidate_hash = str(best_candidate["params_hash"])
                        better = candidate_best < current_best - 1e-15
                        tied = abs(candidate_best - current_best) <= 1e-15
                        if better or (tied and (candidate_hash < current_hash or (candidate_hash == current_hash and int(start_index) < int(best_meta_global["start_index"])))):
                            best_candidate_global = dict(best_candidate)
                            best_meta_global = dict(start_meta)

                if best_candidate_global is None or best_meta_global is None:
                    raise RuntimeError("optimizer returned no candidate evaluations")

                row = dict(best_candidate_global["row"])
                point_record = dict(best_candidate_global["point"])
                seed_objective = float(best_meta_global["seed_objective"])
                best_objective = float(best_meta_global["best_objective"])
                refine_meta = {
                    "mode": "optimize",
                    "method": "nelder_mead",
                    "objective_key": str(objective_key),
                    "n_eval": int(n_eval_total),
                    "converged": bool(best_meta_global.get("converged", False)),
                    "stop_reason": str(best_meta_global.get("stop_reason", "max_eval")),
                    "seed_objective": float(seed_objective),
                    "best_objective": float(best_objective),
                    "multistart_k": int(len(starts)),
                    "opt_init": str(opt_init),
                    "opt_seed": int(opt_seed),
                    "best_start_index": int(best_meta_global.get("start_index", 0)),
                }
                row["refine_meta"] = dict(refine_meta)
                point_record["refine_meta"] = dict(refine_meta)
                row["optimize_start_params_hash"] = str(optimize_start_hash)
                point_record["optimize_start_params"] = dict(optimize_start_params)
                row["opt_multistart"] = int(len(starts))
                row["opt_seed"] = int(opt_seed)
                row["opt_init"] = str(opt_init)
                row["opt_best_start_index"] = int(best_meta_global.get("start_index", 0))
                row["opt_start_points_digest"] = str(start_points_digest)
                point_record["opt_multistart"] = int(row["opt_multistart"])
                point_record["opt_seed"] = int(row["opt_seed"])
                point_record["opt_init"] = str(row["opt_init"])
                point_record["opt_best_start_index"] = int(row["opt_best_start_index"])
                point_record["opt_start_points_digest"] = str(row["opt_start_points_digest"])
        else:
            row, point_record = _eval_once(params)
        row.setdefault("status", "ok")
        point_record.setdefault("status", "ok")
        error_obj = None
    except (Exception, SystemExit) as exc:  # pragma: no cover - exercised by integration tests
        err_type = type(exc).__name__
        err_msg = str(exc).strip()[:500]
        error_obj = {
            "type": str(err_type),
            "message": str(err_msg),
            "where": "evaluate_point",
        }
        row = {
            "model": str(ctx["model_name"]),
            "chi2_cmb": float("nan"),
            "chi2_total": float("nan"),
            "drift_pass": False,
            "drift_required_pass": False,
            "invariants_ok": False,
            "status": "error",
        }
        row.update(
            {
                "H0": float(params.get("H0", float("nan"))),
                "Omega_m": float(params.get("Omega_m", float("nan"))),
                "p": float(params.get("p", float("nan"))),
                "z_transition": float(params.get("z_transition", float("nan"))),
            }
        )
        point_record = {
            "model": str(ctx["model_name"]),
            "params": params,
            "chi2_total": None,
            "chi2_parts": {},
            "drift_pass": False,
            "drift_required_pass": False,
            "drift": {},
            "invariants_ok": False,
            "predicted": {},
            "status": "error",
            "error": error_obj,
            "microphysics": {
                "mode": "none" if str(ctx["microphysics_mode"]) == "none" else "knobs",
                "z_star_scale": float(params.get("z_star_scale", 1.0)),
                "r_s_scale": float(params.get("r_s_scale", 1.0)),
                "r_d_scale": float(params.get("r_d_scale", 1.0)),
            },
            "microphysics_knobs": {
                "z_star_scale": float(params.get("z_star_scale", 1.0)),
                "r_s_scale": float(params.get("r_s_scale", 1.0)),
                "r_d_scale": float(params.get("r_d_scale", 1.0)),
            },
            "microphysics_hard_ok": False,
            "microphysics_plausible_ok": False,
            "microphysics_penalty": float("nan"),
            "microphysics_max_rel_dev": float("nan"),
            "microphysics_notes": [f"{err_type}: {err_msg}"],
        }

    output_params = _canonical_params(_as_mapping(point_record.get("params")))
    output_params_hash = _params_hash(output_params) if output_params else params_hash

    row.setdefault("deformation_family", str(ctx["model_name"]))
    row["params_hash"] = output_params_hash
    row["sample_index"] = int(sample_index)
    row["plan_point_id"] = plan_point_id
    row["plan_point_index"] = int(plan_point_index)
    row["plan_source_sha256"] = plan_source_sha256
    row["scan_config_sha256"] = scan_config_sha256
    if plan_slice_i is not None and plan_slice_n is not None:
        row["plan_slice_i"] = int(plan_slice_i)
        row["plan_slice_n"] = int(plan_slice_n)
    if error_obj is not None:
        row["error"] = error_obj

    point_record.setdefault("deformation_family", str(ctx["model_name"]))
    point_record["params_hash"] = output_params_hash
    point_record["sample_index"] = int(sample_index)
    point_record["plan_point_id"] = plan_point_id
    point_record["plan_point_index"] = int(plan_point_index)
    point_record["plan_source_sha256"] = plan_source_sha256
    point_record["scan_config_sha256"] = scan_config_sha256
    if plan_slice_i is not None and plan_slice_n is not None:
        point_record["plan_slice_i"] = int(plan_slice_i)
        point_record["plan_slice_n"] = int(plan_slice_n)
    if error_obj is not None:
        point_record["error"] = error_obj
    _apply_overlay_and_objective(row, point_record)
    return {
        "row": row,
        "point": point_record,
        "sample_index": int(sample_index),
        "params_hash": output_params_hash,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--model",
        "--deformation",
        dest="model",
        choices=sorted(_MODEL_KEYS.keys()),
        required=True,
        help="History/deformation family (alias: --deformation).",
    )
    ap.add_argument(
        "--grid",
        action="append",
        default=[],
        help="Parameter specification KEY=SPEC. Grid mode: SPEC is comma list or start:stop:step. Random/MH mode: SPEC is min:max.",
    )
    ap.add_argument(
        "--sampler",
        "--sample",
        dest="sampler",
        choices=["grid", "random", "mh", "mh_adaptive", "halton", "lhs"],
        default="grid",
    )
    ap.add_argument("--seed", "--sampler-seed", dest="seed", type=int, default=0)
    ap.add_argument("--plan", type=Path, default=None, help="Optional refine plan JSON; evaluates explicit points list.")
    ap.add_argument(
        "--plan-slice",
        type=str,
        default=None,
        help="Optional plan shard selector I/N (example: 0/8); only valid with --plan in non-MCMC mode.",
    )
    ap.add_argument(
        "--optimize",
        choices=list(_OPTIMIZE_CHOICES),
        default="none",
        help="Optional local refine optimizer for --plan points (default: none).",
    )
    ap.add_argument(
        "--opt-objective-key",
        type=str,
        default="chi2_total",
        help="Objective key path for --optimize mode (default: chi2_total).",
    )
    ap.add_argument(
        "--opt-multistart",
        type=int,
        default=1,
        help="Number of deterministic optimizer starts for --optimize nelder_mead (default: 1).",
    )
    ap.add_argument(
        "--opt-init",
        choices=list(_OPT_MULTISTART_INIT_CHOICES),
        default="random",
        help="Start-point initializer for --opt-multistart (default: random).",
    )
    ap.add_argument(
        "--opt-seed",
        type=int,
        default=0,
        help="Deterministic seed used for --opt-multistart initialization (default: 0).",
    )
    ap.add_argument(
        "--chi2-objective",
        choices=["cmb", "joint"],
        default="cmb",
        help=(
            "Scalar objective used by scan scoring paths. "
            "cmb keeps legacy chi2_total behavior; joint uses chi2_total + rsd_chi2_weight*rsd_chi2."
        ),
    )
    ap.add_argument(
        "--rsd-chi2-field",
        type=str,
        default="",
        help=(
            "Optional RSD chi2 field for --chi2-objective joint. "
            "If omitted, auto-detect priority is rsd_chi2_total -> rsd_chi2 -> rsd_chi2_min."
        ),
    )
    ap.add_argument(
        "--rsd-chi2-weight",
        type=float,
        default=1.0,
        help="Weight multiplier for RSD term in joint objective (default: 1.0).",
    )
    ap.add_argument("--opt-max-eval", type=int, default=200, help="Maximum optimizer objective evaluations per plan seed.")
    ap.add_argument(
        "--opt-step-frac",
        type=float,
        default=0.05,
        help="Initial simplex step fraction of parameter span per dimension (default: 0.05).",
    )
    ap.add_argument("--opt-tol-f", type=float, default=1e-9, help="Optimizer stop tolerance on objective spread.")
    ap.add_argument("--opt-tol-x", type=float, default=1e-9, help="Optimizer stop tolerance on simplex size.")
    ap.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume from existing output JSONL. In --plan mode dedupe is keyed by "
            "plan_point_id + plan_source_sha256; otherwise dedupe uses params_hash."
        ),
    )
    ap.add_argument(
        "--resume-mode",
        choices=["dedupe", "cache"],
        default=None,
        help=(
            "Resume behavior for non-plan samplers: dedupe skips repeated params_hash; "
            "cache reuses evaluations while still emitting points."
        ),
    )
    ap.add_argument("--jobs", type=int, default=1, help="Parallel workers for evaluation (ordered map; default 1).")
    ap.add_argument("--dry-run", action="store_true", help="Print planned point counts/metadata and exit without evaluation.")
    ap.add_argument("--n-samples", type=int, default=0, help="Required in --sampler random/halton/lhs modes")
    ap.add_argument("--n-steps", type=int, default=0, help="Required in --sampler mh mode")
    ap.add_argument("--burn", type=int, default=0)
    ap.add_argument("--thin", type=int, default=1)
    ap.add_argument("--mh-steps", type=int, default=None, help="Adaptive/legacy MH total steps (overrides --n-steps)")
    ap.add_argument("--mh-burnin", type=int, default=None, help="Adaptive/legacy MH burn-in (overrides --burn)")
    ap.add_argument("--mh-thin", type=int, default=None, help="Adaptive/legacy MH thinning (overrides --thin)")
    ap.add_argument("--mh-chains", type=int, default=1, help="Number of MH/MH-adaptive chains")
    ap.add_argument("--mh-target-accept", type=float, default=0.25, help="Adaptive MH target acceptance rate")
    ap.add_argument("--mh-adapt-every", type=int, default=25, help="Adaptive MH update interval (steps)")
    ap.add_argument("--mh-init-scale", type=float, default=0.1, help="Adaptive MH initial proposal scale in transformed space")
    ap.add_argument(
        "--mh-energy",
        choices=["chi2_total", "chi2_total_plus_plausibility"],
        default=None,
        help="MH energy objective; default auto-selects plausibility-augmented mode when available.",
    )
    ap.add_argument("--halton-skip", type=int, default=0, help="Number of initial Halton points to skip")
    ap.add_argument("--halton-scramble", action="store_true", help="Enable deterministic per-base digit scrambling for Halton")
    ap.add_argument("--bounds-json", type=Path, default=None, help="Optional JSON bounds overrides for non-grid samplers.")
    ap.add_argument("--seed-points-jsonl", type=Path, default=None, help="Optional JSONL seed points evaluated before sampler draws.")
    ap.add_argument(
        "--step-scale",
        action="append",
        default=[],
        help="MH proposal step KEY=VALUE. Defaults to 10%% of parameter span.",
    )

    ap.add_argument("--cmb", type=Path, required=False, help="Compressed CMB priors CSV (required unless --toy)")
    ap.add_argument("--cmb-cov", type=Path, default=None, help="Optional covariance file (.cov/.npz)")
    ap.add_argument("--cmb-bridge-z", type=float, default=None, help="Required for non-LCDM models")

    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)
    ap.add_argument("--Y-p", "--Y_p", dest="Y_p", type=float, default=None, help="Optional primordial helium fraction knob")
    ap.add_argument(
        "--microphysics",
        choices=["none", "knobs"],
        default="none",
        help="Diagnostic microphysics mode: none (default) or knobs.",
    )
    ap.add_argument("--z-star-scale-min", type=float, default=0.98)
    ap.add_argument("--z-star-scale-max", type=float, default=1.02)
    ap.add_argument("--r-s-scale-min", type=float, default=0.95)
    ap.add_argument("--r-s-scale-max", type=float, default=1.05)
    ap.add_argument("--r-d-scale-min", type=float, default=0.95)
    ap.add_argument("--r-d-scale-max", type=float, default=1.05)
    ap.add_argument(
        "--gaussian-prior",
        action="append",
        default=[],
        help="Optional Gaussian prior term NAME=MU,SIGMA for early knobs (repeatable).",
    )
    ap.add_argument(
        "--bbn-prior",
        choices=list(BBN_PRIOR_MODES),
        default="none",
        help="Optional BBN-inspired prior mode for omega_b_h2 (default: none).",
    )

    ap.add_argument("--require-positive-drift", action="store_true")
    ap.add_argument(
        "--drift-precheck",
        choices=list(_DRIFT_PRECHECK_CHOICES),
        default="none",
        help="History-only drift sign gate before heavy early-time/CMB evaluation (default: none).",
    )
    ap.add_argument("--drift-z-min", type=float, default=2.0)
    ap.add_argument("--drift-z-max", type=float, default=5.0)
    ap.add_argument("--drift-z-n", type=int, default=61)
    ap.add_argument(
        "--drift-z-list",
        type=str,
        default="2,3,4,5",
        help="Comma-separated redshifts for per-point drift metrics in JSONL (default: 2,3,4,5).",
    )
    ap.add_argument(
        "--no-drift-metrics",
        action="store_true",
        help="Disable per-point drift metrics block in JSONL (keeps legacy drift_pass fields).",
    )
    ap.add_argument(
        "--rsd-overlay",
        action="store_true",
        help="Optional additive structure-formation proxy (RSD fσ8 overlay) per record.",
    )
    ap.add_argument(
        "--rsd-data",
        type=Path,
        default=DEFAULT_RSD_DATA_PATH,
        help="RSD fσ8 CSV path (default: data/structure/fsigma8_gold2017_plus_zhao2018.csv).",
    )
    ap.add_argument(
        "--rsd-ap-correction",
        choices=["none", "approx"],
        default="none",
        help="RSD AP-like correction mode for overlay metadata (default: none).",
    )
    ap.add_argument(
        "--rsd-mode",
        choices=[
            "profile_sigma8_0",
            "nuisance_sigma8",
            "nuisance",
            "profile",
            "derived_As",
            "derived_as",
            "derived",
        ],
        default="profile_sigma8_0",
        help=(
            "RSD overlay amplitude mode. profile_sigma8_0 (nuisance profiling) is default; "
            "derived_As uses As/ns transfer bridge."
        ),
    )
    ap.add_argument(
        "--rsd-transfer-model",
        choices=["bbks", "eh98", "eh98_nowiggle"],
        default="bbks",
        help="Transfer backend for --rsd-mode derived_As (default: bbks).",
    )
    ap.add_argument(
        "--rsd-ns",
        type=float,
        default=1.0,
        help="Primordial tilt n_s for --rsd-mode derived_As (dimensionless).",
    )
    ap.add_argument(
        "--rsd-k-pivot",
        "--rsd-k0-mpc",
        dest="rsd_k_pivot",
        type=float,
        default=0.05,
        help="Primordial pivot k in 1/Mpc for --rsd-mode derived_As (default: 0.05).",
    )

    ap.add_argument("--n-grid", type=int, default=6000, help="Comoving-distance interpolation steps for bridged models")
    ap.add_argument(
        "--integrator",
        choices=["trap", "adaptive_simpson"],
        default="trap",
        help="Integration method for early-time distance/sound-horizon integrals (default: trap).",
    )
    ap.add_argument(
        "--recombination",
        choices=["fit", "peebles3"],
        default="fit",
        help="Recombination redshift method for compressed-CMB diagnostics (default: fit).",
    )
    ap.add_argument(
        "--drag-method",
        choices=["eh98", "ode"],
        default="eh98",
        help="Drag-redshift helper method for diagnostics metadata (default: eh98).",
    )
    ap.add_argument("--recombination-max-steps", type=int, default=4096)
    ap.add_argument("--recombination-rtol", type=float, default=1e-6)
    ap.add_argument("--recombination-atol", type=float, default=1e-10)
    ap.add_argument("--dip-zlo", type=float, default=DEFAULT_DIP_Z_LO, help="Dip window lower redshift edge (dip_bump_window model).")
    ap.add_argument("--dip-zhi", type=float, default=DEFAULT_DIP_Z_HI, help="Dip window upper redshift edge (dip_bump_window model).")
    ap.add_argument("--bump-zlo", type=float, default=DEFAULT_BUMP_Z_LO, help="Bump window lower redshift edge (dip_bump_window model).")
    ap.add_argument("--bump-zhi", type=float, default=DEFAULT_BUMP_Z_HI, help="Bump window upper redshift edge (dip_bump_window model).")
    ap.add_argument("--window-w", type=float, default=DEFAULT_WINDOW_W, help="Shared logistic edge width for dip/bump windows.")
    ap.add_argument(
        "--factor-floor",
        type=float,
        default=DEFAULT_FACTOR_FLOOR,
        help="Minimum allowed multiplicative deformation factor floor for dip_bump_window.",
    )
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="out_dir",
        type=Path,
        default=None,
        help="Output directory (CLI > GSC_OUTDIR > default artifacts/release).",
    )
    ap.add_argument(
        "--points-jsonl-name",
        type=str,
        default="e2_scan_points.jsonl",
        help="Output JSONL filename under --out-dir (supports .jsonl or .jsonl.gz; default: e2_scan_points.jsonl).",
    )
    ap.add_argument("--toy", action="store_true", help="Testing-only fast toy backend (stdlib-only; bypasses CMB dataset loading).")

    args = ap.parse_args()
    plan_slice = _parse_plan_slice(args.plan_slice)

    if int(args.jobs) <= 0:
        raise SystemExit("--jobs must be >= 1")
    points_jsonl_name = str(args.points_jsonl_name).strip()
    if not points_jsonl_name:
        raise SystemExit("--points-jsonl-name must be non-empty")
    if Path(points_jsonl_name).name != points_jsonl_name:
        raise SystemExit("--points-jsonl-name must be a filename without directory separators")
    if not (points_jsonl_name.endswith(".jsonl") or points_jsonl_name.endswith(".jsonl.gz")):
        raise SystemExit("--points-jsonl-name must end with .jsonl or .jsonl.gz")
    if int(args.recombination_max_steps) <= 0:
        raise SystemExit("--recombination-max-steps must be > 0")
    if not (math.isfinite(float(args.recombination_rtol)) and float(args.recombination_rtol) > 0.0):
        raise SystemExit("--recombination-rtol must be finite and > 0")
    if not (math.isfinite(float(args.recombination_atol)) and float(args.recombination_atol) > 0.0):
        raise SystemExit("--recombination-atol must be finite and > 0")
    if not math.isfinite(float(args.rsd_chi2_weight)):
        raise SystemExit("--rsd-chi2-weight must be finite")
    args.rsd_chi2_weight = float(args.rsd_chi2_weight)
    args.rsd_chi2_field = str(args.rsd_chi2_field).strip()
    args.rsd_mode = _canonical_rsd_mode(str(args.rsd_mode))
    args.rsd_transfer_model = _canonical_rsd_transfer_model(str(args.rsd_transfer_model))
    _validate_joint_objective_prereqs(args)
    rsd_overlay_settings = _resolve_scan_rsd_overlay_settings(args)
    chi2_objective = str(args.chi2_objective).strip().lower()
    rsd_chi2_field = str(args.rsd_chi2_field).strip()
    rsd_chi2_weight = float(args.rsd_chi2_weight)
    opt_objective_key_effective = _effective_opt_objective_key(
        chi2_objective=chi2_objective,
        requested_key=str(args.opt_objective_key),
    )
    if bool(rsd_overlay_settings.get("enabled", False)) and not bool(rsd_overlay_settings.get("dataset_available", False)):
        print(
            "[warn] --rsd-overlay enabled but dataset unavailable; records will carry rsd_overlay_ok=false "
            f"(reason={rsd_overlay_settings.get('dataset_missing_reason', 'dataset_missing')})",
            file=sys.stderr,
        )

    plan_mode = bool(args.plan is not None and not _is_mcmc_sampler(str(args.sampler)))
    if plan_slice is not None and not plan_mode:
        raise SystemExit("--plan-slice requires --plan with a non-MCMC sampler mode")
    if str(args.optimize) != "none" and not plan_mode:
        raise SystemExit("--optimize requires --plan with a non-MCMC sampler mode")
    if int(args.opt_max_eval) <= 0:
        raise SystemExit("--opt-max-eval must be > 0")
    if not (math.isfinite(float(args.opt_step_frac)) and float(args.opt_step_frac) > 0.0):
        raise SystemExit("--opt-step-frac must be finite and > 0")
    if not (math.isfinite(float(args.opt_tol_f)) and float(args.opt_tol_f) >= 0.0):
        raise SystemExit("--opt-tol-f must be finite and >= 0")
    if not (math.isfinite(float(args.opt_tol_x)) and float(args.opt_tol_x) >= 0.0):
        raise SystemExit("--opt-tol-x must be finite and >= 0")
    if int(args.opt_multistart) <= 0:
        raise SystemExit("--opt-multistart must be >= 1")
    args.opt_multistart = int(args.opt_multistart)
    args.opt_init = _canonical_opt_init(str(args.opt_init))
    args.opt_seed = int(args.opt_seed)
    try:
        args.bbn_prior = canonical_bbn_prior_mode(str(args.bbn_prior))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    resume_mode = _effective_resume_mode(sampler=str(args.sampler), requested=args.resume_mode)

    mh_steps = int(args.mh_steps) if args.mh_steps is not None else int(args.n_steps)
    mh_burnin = int(args.mh_burnin) if args.mh_burnin is not None else int(args.burn)
    mh_thin = int(args.mh_thin) if args.mh_thin is not None else int(args.thin)
    mh_chains = int(args.mh_chains)
    if mh_steps < 0:
        raise SystemExit("--mh-steps/--n-steps must be >= 0")
    if mh_burnin < 0:
        raise SystemExit("--mh-burnin/--burn must be >= 0")
    if mh_thin <= 0:
        raise SystemExit("--mh-thin/--thin must be > 0")
    if mh_chains <= 0:
        raise SystemExit("--mh-chains must be >= 1")
    if not (math.isfinite(float(args.mh_target_accept)) and 0.0 < float(args.mh_target_accept) < 1.0):
        raise SystemExit("--mh-target-accept must be finite and in (0,1)")
    if int(args.mh_adapt_every) <= 0:
        raise SystemExit("--mh-adapt-every must be > 0")
    if not (math.isfinite(float(args.mh_init_scale)) and float(args.mh_init_scale) > 0.0):
        raise SystemExit("--mh-init-scale must be finite and > 0")

    if args.cmb is None and not bool(args.toy):
        raise SystemExit("--cmb is required unless --toy is set")
    if args.model != "lcdm" and args.cmb_bridge_z is None and not bool(args.toy):
        raise SystemExit("--cmb-bridge-z is required for non-LCDM models (unless --toy)")

    if args.cmb is not None and _is_chw2018_distance_priors_csv(args.cmb) and args.cmb_cov is None and not bool(args.toy):
        raise SystemExit("CHW2018 distance priors require --cmb-cov (strict E1.1 mode).")

    if not plan_mode and not bool(args.toy):
        # Keep the legacy behavior for sampler-driven non-toy scans.
        _require_numpy_or_die()

    grid_specs = _parse_grid_kv(args.grid)
    if not plan_mode:
        _validate_grid_specs_for_model(model_name=str(args.model), grid_specs=grid_specs)
    microphysics_bounds = _microphysics_bounds_from_namespace(args)
    if not plan_mode:
        required_keys, early_scan_keys, micro_scan_keys = _split_param_keys(
            model_name=str(args.model),
            grid_specs=grid_specs,
            microphysics_mode=str(args.microphysics),
        )
        if str(args.microphysics) == "none":
            unexpected_micro = [k for k in _MICROPHYSICS_SCAN_KEYS if k in grid_specs]
            if unexpected_micro:
                raise SystemExit(
                    f"--grid includes microphysics keys {unexpected_micro} but --microphysics is 'none'"
                )
    else:
        required_keys = tuple(_MODEL_KEYS[str(args.model)])
        early_scan_keys = tuple()
        micro_scan_keys = tuple()
    drift_z_list = _parse_drift_z_list(args.drift_z_list)
    gaussian_priors = _parse_gaussian_priors(args.gaussian_prior)
    model_hyper = _dip_bump_hyperparams_from_namespace(args)
    if plan_mode and args.bounds_json is not None:
        raise SystemExit("--bounds-json cannot be combined with --plan")
    if plan_mode and args.seed_points_jsonl is not None:
        raise SystemExit("--seed-points-jsonl cannot be combined with --plan")
    if not plan_mode:
        bounds_overrides, bounds_overrides_path = _load_bounds_overrides(args.bounds_json)
        seed_points_raw, seed_points_path = _load_seed_points(args.seed_points_jsonl)
        if args.sampler == "grid":
            if bounds_overrides is not None:
                raise SystemExit("--bounds-json is only supported for non-grid samplers")
            if seed_points_raw:
                raise SystemExit("--seed-points-jsonl is only supported for non-grid samplers")
    else:
        bounds_overrides = None
        bounds_overrides_path = None
        seed_points_raw = []
        seed_points_path = None
    early = early_time_params_from_namespace(args, require=True, context="phase2_e2_scan")
    assert early is not None
    early_defaults: Dict[str, Optional[float]] = {
        "omega_b_h2": float(early.omega_b_h2),
        "omega_c_h2": float(early.omega_c_h2),
        "N_eff": float(early.N_eff),
        "Tcmb_K": float(early.Tcmb_K),
        "Y_p": None if args.Y_p is None else float(args.Y_p),
    }
    if early_defaults["Y_p"] is not None:
        y_p_val = float(early_defaults["Y_p"])
        if not (0.0 <= y_p_val < 1.0 and math.isfinite(y_p_val)):
            raise SystemExit("--Y-p must be finite and in [0,1)")

    plan_points_for_mode: List[Dict[str, Any]] = []
    plan_payload_for_mode: Dict[str, Any] = {}
    plan_source_sha_for_mode = ""
    if plan_mode:
        assert args.plan is not None
        plan_points_for_mode, plan_payload_for_mode, plan_source_sha_for_mode = _load_scan_plan(args.plan)
        if not plan_points_for_mode:
            raise SystemExit("--plan contains no valid points")

    out_root = resolve_outdir(args.out_dir, v101_dir=V101_DIR)
    out_root.mkdir(parents=True, exist_ok=True)
    points_csv = out_root / "e2_scan_points.csv"
    points_jsonl = out_root / str(points_jsonl_name)
    summary_json = out_root / "e2_scan_summary.json"
    scan_config_payload, scan_config_sha256 = _build_scan_config_payload(
        args=args,
        plan_source_sha256=plan_source_sha_for_mode if plan_mode else None,
        rsd_data_sha256=(
            str(rsd_overlay_settings.get("dataset_sha256"))
            if rsd_overlay_settings.get("dataset_sha256") is not None
            else None
        ),
        rsd_data_id=str(rsd_overlay_settings.get("dataset_id", "")),
        rsd_overlay_settings=rsd_overlay_settings,
    )
    existing_points, existing_hashes = _load_existing_points(points_jsonl) if bool(args.resume) else ([], set())

    ds = None
    if not plan_mode and not bool(args.toy):
        if args.cmb is None:
            raise RuntimeError("Internal error: --cmb is required when not in toy mode")
        ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb")
    z_bridge = float(args.cmb_bridge_z) if args.cmb_bridge_z is not None else None

    eval_cache: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
    if bool(args.resume) and resume_mode == "cache":
        for point in existing_points:
            ph = _extract_params_hash_from_record(point)
            if not ph:
                continue
            row_cache = _point_record_to_row(point)
            eval_cache[ph] = (row_cache, dict(point))

    def _evaluate_raw(params: Mapping[str, float]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if bool(args.toy):
            return _evaluate_point_toy(
                model_name=str(args.model),
                params=params,
                early_defaults=early_defaults,
                gaussian_priors=gaussian_priors,
                bbn_prior_mode=str(args.bbn_prior),
                drift_z_min=float(args.drift_z_min),
                drift_z_max=float(args.drift_z_max),
                drift_z_n=int(args.drift_z_n),
                drift_z_list=drift_z_list,
                include_drift_metrics=not bool(args.no_drift_metrics),
                require_positive_drift=bool(args.require_positive_drift),
                drift_precheck_spec=str(args.drift_precheck),
                microphysics_mode=str(args.microphysics),
                recombination_method=str(args.recombination),
                drag_method=str(args.drag_method),
                recombination_rtol=float(args.recombination_rtol),
                recombination_atol=float(args.recombination_atol),
                recombination_max_steps=int(args.recombination_max_steps),
                sampler=str(args.sampler),
                seed=int(args.seed),
            )
        if ds is None:
            raise RuntimeError("Internal error: dataset unavailable in non-toy evaluation path")
        return _evaluate_point(
            model_name=str(args.model),
            params=params,
            dataset=ds,
            early_defaults=early_defaults,
            gaussian_priors=gaussian_priors,
            bbn_prior_mode=str(args.bbn_prior),
            z_bridge=z_bridge,
            drift_z_min=float(args.drift_z_min),
            drift_z_max=float(args.drift_z_max),
            drift_z_n=int(args.drift_z_n),
            drift_z_list=drift_z_list,
            include_drift_metrics=not bool(args.no_drift_metrics),
            require_positive_drift=bool(args.require_positive_drift),
            drift_precheck_spec=str(args.drift_precheck),
            n_grid=int(args.n_grid),
            integrator=str(args.integrator),
            recombination_method=str(args.recombination),
            drag_method=str(args.drag_method),
            recombination_rtol=float(args.recombination_rtol),
            recombination_atol=float(args.recombination_atol),
            recombination_max_steps=int(args.recombination_max_steps),
            model_hyper=model_hyper,
            microphysics_mode=str(args.microphysics),
            sampler=str(args.sampler),
            seed=int(args.seed),
        )

    def _apply_scan_objective_fields(row: Dict[str, Any], point_record: Dict[str, Any]) -> None:
        _apply_joint_objective_fields(
            row=row,
            point_record=point_record,
            chi2_objective=str(chi2_objective),
            rsd_chi2_field=str(rsd_chi2_field),
            rsd_chi2_weight=float(rsd_chi2_weight),
        )

    def _evaluate_cached(params: Mapping[str, float]) -> Tuple[Dict[str, Any], Dict[str, Any], bool]:
        params_hash = _params_hash(params)
        cached = eval_cache.get(params_hash)
        if cached is not None:
            row_cached = copy.deepcopy(cached[0])
            point_cached = copy.deepcopy(cached[1])
            if "rsd_overlay_ok" not in row_cached or "rsd_overlay_ok" not in point_cached:
                _apply_rsd_overlay_fields(
                    row=row_cached,
                    point_record=point_cached,
                    rsd_settings=rsd_overlay_settings,
                )
            _apply_scan_objective_fields(row_cached, point_cached)
            return row_cached, point_cached, True
        try:
            row, point_record = _evaluate_raw(params)
        except (Exception, SystemExit) as exc:  # pragma: no cover - error payload path is smoke-covered
            err_type = type(exc).__name__
            err_msg = str(exc).strip()[:500]
            try:
                micro_scales = _microphysics_scales_from_params(params=params, mode=str(args.microphysics))
                micro_payload, micro_audit = _microphysics_payload_and_audit(scales=micro_scales, mode=str(args.microphysics))
            except Exception:
                micro_payload = {
                    "mode": "none" if str(args.microphysics) == "none" else "knobs",
                    "z_star_scale": float(params.get("z_star_scale", 1.0)),
                    "r_s_scale": float(params.get("r_s_scale", 1.0)),
                    "r_d_scale": float(params.get("r_d_scale", 1.0)),
                }
                micro_audit = {
                    "microphysics_knobs": {
                        "z_star_scale": float(params.get("z_star_scale", 1.0)),
                        "r_s_scale": float(params.get("r_s_scale", 1.0)),
                        "r_d_scale": float(params.get("r_d_scale", 1.0)),
                    },
                    "microphysics_hard_ok": False,
                    "microphysics_plausible_ok": False,
                    "microphysics_penalty": float("nan"),
                    "microphysics_max_rel_dev": float("nan"),
                    "microphysics_notes": [f"{err_type}: {err_msg}"],
                }
            point_params = {k: float(v) for k, v in sorted(params.items())}
            row = {
                "model": str(args.model),
                "chi2_cmb": float("nan"),
                "chi2_total": float("nan"),
                "drift_pass": False,
                "drift_required_pass": False,
                "invariants_ok": False,
                "status": "error",
                "error": {"type": err_type, "message": err_msg, "where": "evaluate_cached"},
                "microphysics_mode": str(micro_payload.get("mode", "none")),
                "z_star_scale": float(micro_payload.get("z_star_scale", 1.0)),
                "r_s_scale": float(micro_payload.get("r_s_scale", 1.0)),
                "r_d_scale": float(micro_payload.get("r_d_scale", 1.0)),
                "microphysics_plausible_ok": bool(micro_audit.get("microphysics_plausible_ok", False)),
                "microphysics_penalty": float(micro_audit.get("microphysics_penalty", 0.0)),
                "microphysics_max_rel_dev": float(micro_audit.get("microphysics_max_rel_dev", 0.0)),
                "recombination_method": str(args.recombination),
                "recomb_converged": False,
                "drag_method": str(args.drag_method),
                "cmb_num_method": str(args.integrator),
                "cmb_num_n_eval_dm": 0,
                "cmb_num_err_dm": None,
                "cmb_num_n_eval_rs": 0,
                "cmb_num_err_rs": None,
                "cmb_num_n_eval_rs_drag": 0,
                "cmb_num_err_rs_drag": None,
                "cmb_num_rtol": float(args.recombination_rtol),
                "cmb_num_atol": float(args.recombination_atol),
            }
            point_record = {
                "model": str(args.model),
                "params": point_params,
                "chi2_total": None,
                "chi2_parts": {},
                "drift_pass": False,
                "drift_required_pass": False,
                "drift": {},
                "invariants_ok": False,
                "predicted": {},
                "status": "error",
                "error": {"type": err_type, "message": err_msg, "where": "evaluate_cached"},
                "microphysics": dict(micro_payload),
                "microphysics_knobs": dict(micro_audit.get("microphysics_knobs") or {}),
                "microphysics_hard_ok": bool(micro_audit.get("microphysics_hard_ok", False)),
                "microphysics_plausible_ok": bool(micro_audit.get("microphysics_plausible_ok", False)),
                "microphysics_penalty": float(micro_audit.get("microphysics_penalty", 0.0)),
                "microphysics_max_rel_dev": float(micro_audit.get("microphysics_max_rel_dev", 0.0)),
                "microphysics_notes": list(micro_audit.get("microphysics_notes") or []),
                "recombination_method": str(args.recombination),
                "recomb_converged": False,
                "drag_method": str(args.drag_method),
                "cmb_num_method": str(args.integrator),
                "cmb_num_n_eval_dm": 0,
                "cmb_num_err_dm": None,
                "cmb_num_n_eval_rs": 0,
                "cmb_num_err_rs": None,
                "cmb_num_n_eval_rs_drag": 0,
                "cmb_num_err_rs_drag": None,
                "cmb_num_rtol": float(args.recombination_rtol),
                "cmb_num_atol": float(args.recombination_atol),
            }
        if "rsd_overlay_ok" not in row or "rsd_overlay_ok" not in point_record:
            _apply_rsd_overlay_fields(
                row=row,
                point_record=point_record,
                rsd_settings=rsd_overlay_settings,
            )
        _apply_scan_objective_fields(row, point_record)
        eval_cache[params_hash] = (copy.deepcopy(row), copy.deepcopy(point_record))
        return row, point_record, False

    rows: List[Dict[str, Any]] = []
    points: List[Dict[str, Any]] = []
    sampler_meta: Dict[str, Any] = {
        "sampler": str(args.sampler),
        "seed": int(args.seed),
        "resume_mode": str(resume_mode),
        "toy": bool(args.toy),
        "drift_precheck_spec": str(args.drift_precheck),
        "optimize": str(args.optimize),
        "chi2_objective": str(chi2_objective),
        "opt_objective_key": str(opt_objective_key_effective),
        "rsd_chi2_field": str(rsd_chi2_field or "auto"),
        "rsd_chi2_weight": float(rsd_chi2_weight),
        "opt_max_eval": int(args.opt_max_eval),
        "opt_step_frac": float(args.opt_step_frac),
        "opt_tol_f": float(args.opt_tol_f),
        "opt_tol_x": float(args.opt_tol_x),
        "early_scan_keys": list(early_scan_keys),
        "micro_scan_keys": list(micro_scan_keys),
        "microphysics_mode": str(args.microphysics),
        "microphysics_bounds": {
            k: [float(v[0]), float(v[1])]
            for k, v in sorted(microphysics_bounds.items())
        },
        "integrator": str(args.integrator),
        "recombination_method": str(args.recombination),
        "drag_method": str(args.drag_method),
        "recombination_rtol": float(args.recombination_rtol),
        "recombination_atol": float(args.recombination_atol),
        "recombination_max_steps": int(args.recombination_max_steps),
        "scan_config_schema": _SCAN_CONFIG_SCHEMA,
        "scan_config_sha256": str(scan_config_sha256),
        "rsd_overlay_enabled": bool(rsd_overlay_settings.get("enabled", False)),
        "rsd_data_id": str(rsd_overlay_settings.get("dataset_id", "")),
        "rsd_data_sha256": str(rsd_overlay_settings.get("dataset_sha256") or ""),
        "rsd_data_available": bool(rsd_overlay_settings.get("dataset_available", False)),
        "rsd_ap_correction": str(rsd_overlay_settings.get("ap_mode", "none")),
        "rsd_mode": str(rsd_overlay_settings.get("scan_mode", "profile_sigma8_0")),
        "rsd_transfer_model": (
            str(rsd_overlay_settings.get("transfer_model", "bbks"))
            if bool(rsd_overlay_settings.get("uses_primordial_knobs", False))
            else None
        ),
        "rsd_primordial_ns": (
            _finite_float(rsd_overlay_settings.get("primordial_ns"))
            if bool(rsd_overlay_settings.get("uses_primordial_knobs", False))
            else None
        ),
        "rsd_primordial_k_pivot_mpc": (
            _finite_float(rsd_overlay_settings.get("primordial_k_pivot_mpc"))
            if bool(rsd_overlay_settings.get("uses_primordial_knobs", False))
            else None
        ),
    }
    if str(args.model) == "dip_bump_window":
        sampler_meta["model_hyper"] = {
            "z_dip_lo": float(model_hyper["z_dip_lo"]),
            "z_dip_hi": float(model_hyper["z_dip_hi"]),
            "z_bump_lo": float(model_hyper["z_bump_lo"]),
            "z_bump_hi": float(model_hyper["z_bump_hi"]),
            "w": float(model_hyper["w"]),
            "factor_floor": float(model_hyper["factor_floor"]),
        }
    if str(args.optimize) == "nelder_mead":
        sampler_meta["opt_multistart"] = int(args.opt_multistart)
        if int(args.opt_multistart) > 1:
            sampler_meta["opt_init"] = str(args.opt_init)
            sampler_meta["opt_seed"] = int(args.opt_seed)
    if str(args.bbn_prior) != "none":
        sampler_meta["bbn_prior"] = str(args.bbn_prior)

    def _materialize_sample(
        *,
        base_row: Mapping[str, Any],
        base_point: Mapping[str, Any],
        index: int,
        detail: Optional[Mapping[str, Any]] = None,
        dim: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        row = dict(base_row)
        point_record = dict(base_point)
        row["sample_index"] = int(index)
        point_record["sample_index"] = int(index)
        row.setdefault("deformation_family", str(args.model))
        point_record.setdefault("deformation_family", str(args.model))
        sampler_block: Dict[str, Any] = {
            "kind": str(args.sampler),
            "seed": int(args.seed),
            "index": int(index),
            "dim": None if dim is None else int(dim),
            "detail": _to_json_safe(detail or {}),
        }
        point_record["sampler"] = sampler_block
        return row, point_record

    dedupe_enabled = resume_mode == "dedupe"
    seen_hashes: set[str] = set()
    sample_index = 0
    seed_points_loaded = len(seed_points_raw)
    seed_points_used = 0
    seed_points_skipped_dupe = 0
    generated_duplicates = 0

    def _add_sample(
        *,
        params: Mapping[str, float],
        detail: Optional[Mapping[str, Any]],
        dim: Optional[int],
        is_seed_point: bool,
        force_emit: bool = False,
        extra_fields: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        nonlocal sample_index, seed_points_used, seed_points_skipped_dupe, generated_duplicates
        params_hash = _params_hash(params)
        if dedupe_enabled and bool(args.resume) and params_hash in existing_hashes and not force_emit:
            if is_seed_point:
                seed_points_skipped_dupe += 1
            else:
                generated_duplicates += 1
            return False
        if dedupe_enabled and params_hash in seen_hashes and not force_emit:
            if is_seed_point:
                seed_points_skipped_dupe += 1
            else:
                generated_duplicates += 1
            return False
        if dedupe_enabled:
            seen_hashes.add(params_hash)
        row_base, point_base, cache_hit = _evaluate_cached(params)
        row, point_record = _materialize_sample(
            base_row=row_base,
            base_point=point_base,
            index=sample_index,
            detail=detail,
            dim=dim,
        )
        row["params_hash"] = params_hash
        row.setdefault("status", "ok")
        row["cache_hit"] = bool(cache_hit)
        row["scan_config_sha256"] = str(scan_config_sha256)
        point_record["params_hash"] = params_hash
        point_record.setdefault("status", "ok")
        point_record["cache_hit"] = bool(cache_hit)
        point_record["scan_config_sha256"] = str(scan_config_sha256)
        _apply_rsd_overlay_fields(
            row=row,
            point_record=point_record,
            rsd_settings=rsd_overlay_settings,
        )
        _apply_scan_objective_fields(row, point_record)
        if extra_fields:
            for k, v in extra_fields.items():
                row[str(k)] = _to_json_safe(v)
                point_record[str(k)] = _to_json_safe(v)
        sample_index += 1
        rows.append(row)
        points.append(point_record)
        if is_seed_point:
            seed_points_used += 1
        return True

    def _prepare_seed_points(bounds: Mapping[str, Tuple[float, float]]) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        if not seed_points_raw:
            return prepared
        for entry in seed_points_raw:
            raw_params = entry["params"]
            params: Dict[str, float] = {}
            missing = [k for k in sorted(bounds.keys()) if k not in raw_params]
            if missing:
                raise SystemExit(
                    f"--seed-points-jsonl missing required keys {missing} at {entry['source_file']}:{entry['source_line']}"
                )
            for key in sorted(bounds.keys()):
                lo, hi = bounds[key]
                val = _finite_float(raw_params.get(key))
                if val is None:
                    raise SystemExit(
                        f"--seed-points-jsonl non-finite value for {key!r} at {entry['source_file']}:{entry['source_line']}"
                    )
                fv = float(val)
                if fv < float(lo) or fv > float(hi):
                    raise SystemExit(
                        f"--seed-points-jsonl value for {key!r} out of bounds [{lo}, {hi}] at {entry['source_file']}:{entry['source_line']}"
                    )
                params[key] = fv
            prepared.append(
                {
                    "params": params,
                    "source_file": str(entry["source_file"]),
                    "source_line": int(entry["source_line"]),
                }
            )
        return prepared

    if bool(args.resume) and existing_points:
        for point in existing_points:
            points.append(point)
            rows.append(_point_record_to_row(point))
        sample_index = len(points)

    rows_before_scan = len(rows)

    if plan_mode:
        assert args.plan is not None
        plan_points = list(plan_points_for_mode)
        plan_payload = dict(plan_payload_for_mode)
        plan_source_sha = str(plan_source_sha_for_mode)
        sampler_meta["sampler"] = "plan"
        sampler_meta["plan_mode"] = True
        sampler_meta["plan_file"] = str(Path(args.plan).expanduser().resolve())
        sampler_meta["plan_sha256"] = _sha256_file(Path(args.plan).expanduser().resolve())
        sampler_meta["plan_version"] = str(plan_payload.get("plan_version", ""))
        sampler_meta["jobs"] = int(args.jobs)
        sampler_meta["resume"] = bool(args.resume)
        if not plan_points:
            raise SystemExit("--plan contains no valid points")

        tasks: List[Dict[str, Any]] = []
        skipped_resume = 0
        local_plan_ids: set[str] = set()
        existing_plan_ids: set[str] = set()
        expected_plan_source = str(plan_source_sha or "").strip()
        if bool(args.resume):
            for point in existing_points:
                point_id = point.get("plan_point_id")
                if point_id is None:
                    continue
                point_source = str(point.get("plan_source_sha256", "") or "").strip()
                if expected_plan_source:
                    if point_source != expected_plan_source:
                        continue
                elif point_source:
                    continue
                if not _is_completed_plan_status(point):
                    continue
                existing_plan_ids.add(str(point_id))
        slice_total = 0
        for idx, item in enumerate(plan_points):
            if plan_slice is not None:
                slice_i, slice_n = plan_slice
                if int(idx) % int(slice_n) != int(slice_i):
                    continue
                slice_total += 1
            plan_pid = str(item.get("plan_point_id", f"plan_p{idx:06d}"))
            if plan_pid in local_plan_ids:
                raise SystemExit(f"--plan contains duplicate plan_point_id: {plan_pid}")
            local_plan_ids.add(plan_pid)
            if bool(args.resume) and plan_pid in existing_plan_ids:
                skipped_resume += 1
                continue
            params = _canonical_params(_as_mapping(item.get("params")))
            if not params:
                continue
            ph = _params_hash(params)
            task_sample_index = int(sample_index + len(tasks))
            if plan_slice is not None:
                task_sample_index = int(idx)
            tasks.append(
                {
                    "sample_index": int(task_sample_index),
                    "params": params,
                    "params_hash": ph,
                    "plan_point_id": str(plan_pid),
                    "plan_point_index": int(item.get("plan_point_index", idx)),
                    "plan_source_sha256": str(plan_source_sha) if plan_source_sha else None,
                    "plan_slice_i": None if plan_slice is None else int(plan_slice[0]),
                    "plan_slice_n": None if plan_slice is None else int(plan_slice[1]),
                }
            )

        sampler_meta["plan_points_total"] = int(len(plan_points))
        if plan_slice is not None:
            sampler_meta["plan_slice"] = f"{int(plan_slice[0])}/{int(plan_slice[1])}"
            sampler_meta["plan_slice_i"] = int(plan_slice[0])
            sampler_meta["plan_slice_n"] = int(plan_slice[1])
            sampler_meta["plan_points_in_slice"] = int(slice_total)
        sampler_meta["plan_points_after_resume"] = int(len(tasks))
        sampler_meta["plan_points_skipped_resume"] = int(skipped_resume)

        if plan_slice is not None:
            print(
                (
                    "[plan] slice={slice_i}/{slice_n} total_points={total} "
                    "slice_points={slice_points} pending={pending} resume={resume} jobs={jobs} out={out}"
                ).format(
                    slice_i=int(plan_slice[0]),
                    slice_n=int(plan_slice[1]),
                    total=int(len(plan_points)),
                    slice_points=int(slice_total),
                    pending=int(len(tasks)),
                    resume=bool(args.resume),
                    jobs=int(args.jobs),
                    out=str(points_jsonl),
                ),
                file=sys.stderr,
            )

        if bool(args.dry_run):
            dry = {
                "mode": "dry_run",
                "sampler_config": sampler_meta,
                "n_existing_points": int(len(existing_points)),
                "n_pending_points": int(len(tasks)),
                "points_jsonl": str(points_jsonl),
                "summary_json": str(summary_json),
            }
            print(json.dumps(_to_json_safe(dry), indent=2, sort_keys=True))
            return

        context = _build_plan_eval_context(
            args=args,
            scan_config_sha256=str(scan_config_sha256),
            chi2_objective=str(chi2_objective),
            rsd_chi2_field=str(rsd_chi2_field),
            rsd_chi2_weight=float(rsd_chi2_weight),
            opt_objective_key_effective=str(opt_objective_key_effective),
            early_defaults=early_defaults,
            gaussian_priors=gaussian_priors,
            z_bridge=z_bridge,
            drift_z_list=drift_z_list,
            model_hyper=model_hyper,
            microphysics_bounds=microphysics_bounds,
            rsd_overlay_settings=rsd_overlay_settings,
        )
        if int(args.jobs) == 1:
            _plan_worker_init(context)
            results = [_evaluate_plan_task(task) for task in tasks]
        else:
            with mp.Pool(processes=int(args.jobs), initializer=_plan_worker_init, initargs=(context,)) as pool:
                results = pool.map(_evaluate_plan_task, tasks)

        results = sorted(
            results,
            key=lambda r: (
                int(_as_mapping(r.get("point")).get("plan_point_index", -1)),
                int(r.get("sample_index", -1)),
                str(_as_mapping(r.get("point")).get("plan_point_id", "")),
            ),
        )
        new_rows = [dict(r["row"]) for r in results]
        new_points = [dict(r["point"]) for r in results]
        rows.extend(new_rows)
        points.extend(new_points)

        if bool(args.resume) and points_jsonl.is_file():
            _append_points_jsonl(points_jsonl, new_points)
        else:
            _write_points_jsonl(points_jsonl, points)
        _write_scan_config_sidecar(
            points_jsonl=points_jsonl,
            scan_config=scan_config_payload,
            scan_config_sha256=str(scan_config_sha256),
        )

        sampler_meta["n_evaluated"] = int(len(new_rows))
        sampler_meta["n_error"] = int(sum(1 for r in new_rows if str(r.get("status")) == "error"))
        sampler_meta["n_ok"] = int(sum(1 for r in new_rows if str(r.get("status")) == "ok"))
        sampler_meta["n_skipped_drift"] = int(
            sum(1 for r in new_rows if str(r.get("status")) == "skipped_drift")
        )

    elif args.sampler == "grid":
        params_iter = _iter_param_points_grid(
            model_name=str(args.model),
            grid_specs=grid_specs,
            microphysics_mode=str(args.microphysics),
        )
        dim = int(len(required_keys) + len(early_scan_keys) + len(_MICROPHYSICS_SCAN_KEYS if str(args.microphysics) == "knobs" else ()))
        for params in params_iter:
            _add_sample(
                params=params,
                detail={"mode": "grid"},
                dim=dim,
                is_seed_point=False,
            )
        sampler_meta["n_evaluated"] = len(rows)

    elif args.sampler == "random":
        if int(args.n_samples) < 0:
            raise SystemExit("--n-samples must be >= 0 in random mode")
        base_bounds = _build_sampling_bounds(
            model_name=str(args.model),
            grid_specs=grid_specs,
            microphysics_mode=str(args.microphysics),
            microphysics_bounds=microphysics_bounds,
        )
        bounds = _apply_bounds_overrides(base_bounds, bounds_overrides)
        seed_points = _prepare_seed_points(bounds)
        if int(args.n_samples) == 0 and not seed_points:
            raise SystemExit("--n-samples must be > 0 in random mode when no seed points are provided")
        params_iter = iter_random_points(bounds, n=int(args.n_samples), seed=int(args.seed))
        dim = int(len(bounds))
        for seed in seed_points:
            _add_sample(
                params=seed["params"],
                detail={
                    "mode": "seed",
                    "seed_point": True,
                    "seed_source_file": seed["source_file"],
                    "seed_source_line": int(seed["source_line"]),
                },
                dim=dim,
                is_seed_point=True,
            )
        for params in params_iter:
            _add_sample(
                params=params,
                detail={"mode": "uniform", "seed_point": False},
                dim=dim,
                is_seed_point=False,
            )
        sampler_meta["bounds"] = {k: [float(v[0]), float(v[1])] for k, v in sorted(bounds.items())}
        sampler_meta["bounds_default"] = {k: [float(v[0]), float(v[1])] for k, v in sorted(base_bounds.items())}
        sampler_meta["n_requested"] = int(args.n_samples)
        sampler_meta["n_evaluated"] = len(rows)

    elif args.sampler == "halton":
        if int(args.n_samples) < 0:
            raise SystemExit("--n-samples must be >= 0 in halton mode")
        if int(args.halton_skip) < 0:
            raise SystemExit("--halton-skip must be >= 0")
        base_bounds = _build_sampling_bounds(
            model_name=str(args.model),
            grid_specs=grid_specs,
            microphysics_mode=str(args.microphysics),
            microphysics_bounds=microphysics_bounds,
        )
        bounds = _apply_bounds_overrides(base_bounds, bounds_overrides)
        seed_points = _prepare_seed_points(bounds)
        if int(args.n_samples) == 0 and not seed_points:
            raise SystemExit("--n-samples must be > 0 in halton mode when no seed points are provided")
        dim = int(len(bounds))
        bases = halton_bases(dim)
        params_iter = iter_halton_points(
            bounds,
            n=int(args.n_samples),
            seed=int(args.seed),
            scramble=bool(args.halton_scramble),
            skip=int(args.halton_skip),
        )
        for seed in seed_points:
            _add_sample(
                params=seed["params"],
                detail={
                    "mode": "seed",
                    "seed_point": True,
                    "seed_source_file": seed["source_file"],
                    "seed_source_line": int(seed["source_line"]),
                },
                dim=dim,
                is_seed_point=True,
            )
        for params in params_iter:
            _add_sample(
                params=params,
                detail={
                    "mode": "halton",
                    "seed_point": False,
                    "bases": [int(v) for v in bases],
                    "skip": int(args.halton_skip),
                    "scramble": bool(args.halton_scramble),
                },
                dim=dim,
                is_seed_point=False,
            )
        sampler_meta["bounds"] = {k: [float(v[0]), float(v[1])] for k, v in sorted(bounds.items())}
        sampler_meta["bounds_default"] = {k: [float(v[0]), float(v[1])] for k, v in sorted(base_bounds.items())}
        sampler_meta["bases"] = [int(v) for v in bases]
        sampler_meta["skip"] = int(args.halton_skip)
        sampler_meta["scramble"] = bool(args.halton_scramble)
        sampler_meta["n_requested"] = int(args.n_samples)
        sampler_meta["n_evaluated"] = len(rows)

    elif args.sampler == "lhs":
        if int(args.n_samples) < 0:
            raise SystemExit("--n-samples must be >= 0 in lhs mode")
        base_bounds = _build_sampling_bounds(
            model_name=str(args.model),
            grid_specs=grid_specs,
            microphysics_mode=str(args.microphysics),
            microphysics_bounds=microphysics_bounds,
        )
        bounds = _apply_bounds_overrides(base_bounds, bounds_overrides)
        seed_points = _prepare_seed_points(bounds)
        if int(args.n_samples) == 0 and not seed_points:
            raise SystemExit("--n-samples must be > 0 in lhs mode when no seed points are provided")
        dim = int(len(bounds))
        params_iter = iter_lhs_points(bounds, n=int(args.n_samples), seed=int(args.seed))
        for seed in seed_points:
            _add_sample(
                params=seed["params"],
                detail={
                    "mode": "seed",
                    "seed_point": True,
                    "seed_source_file": seed["source_file"],
                    "seed_source_line": int(seed["source_line"]),
                },
                dim=dim,
                is_seed_point=True,
            )
        for params in params_iter:
            _add_sample(
                params=params,
                detail={"mode": "center", "seed_point": False},
                dim=dim,
                is_seed_point=False,
            )
        sampler_meta["bounds"] = {k: [float(v[0]), float(v[1])] for k, v in sorted(bounds.items())}
        sampler_meta["bounds_default"] = {k: [float(v[0]), float(v[1])] for k, v in sorted(base_bounds.items())}
        sampler_meta["lhs_mode"] = "center"
        sampler_meta["n_requested"] = int(args.n_samples)
        sampler_meta["n_evaluated"] = len(rows)

    else:  # args.sampler in {"mh", "mh_adaptive"}
        base_bounds = _build_sampling_bounds(
            model_name=str(args.model),
            grid_specs=grid_specs,
            microphysics_mode=str(args.microphysics),
            microphysics_bounds=microphysics_bounds,
        )
        bounds = _apply_bounds_overrides(base_bounds, bounds_overrides)
        dim = int(len(bounds))
        seed_points = _prepare_seed_points(bounds)

        plan_chain_starts: List[Dict[str, float]] = []
        plan_start_source_sha = ""
        if args.plan is not None:
            plan_points, plan_payload, plan_start_source_sha = _load_scan_plan(args.plan)
            sampler_meta["mh_start_plan_file"] = str(Path(args.plan).expanduser().resolve())
            sampler_meta["mh_start_plan_sha256"] = _sha256_file(Path(args.plan).expanduser().resolve())
            sampler_meta["mh_start_plan_version"] = str(plan_payload.get("plan_version", ""))
            for item in plan_points:
                raw = _canonical_params(_as_mapping(item.get("params")))
                if not raw:
                    continue
                missing = [k for k in sorted(bounds.keys()) if k not in raw]
                if missing:
                    continue
                params: Dict[str, float] = {}
                valid = True
                for key in sorted(bounds.keys()):
                    lo, hi = bounds[key]
                    value = float(raw[key])
                    if value < lo or value > hi:
                        valid = False
                        break
                    params[key] = value
                if valid:
                    plan_chain_starts.append(params)

        chain_starts: List[Dict[str, float]] = []
        if plan_chain_starts:
            chain_starts.extend(plan_chain_starts)
        elif seed_points:
            chain_starts.extend([dict(s["params"]) for s in seed_points])
        if not chain_starts:
            rng_starts = iter_random_points(bounds, n=max(mh_chains, 1), seed=int(args.seed) + 100003)
            chain_starts.extend(list(rng_starts))

        if len(chain_starts) < mh_chains:
            extra_needed = mh_chains - len(chain_starts)
            rng_extra = iter_random_points(bounds, n=extra_needed, seed=int(args.seed) + 200003)
            chain_starts.extend(list(rng_extra))
        chain_starts = [dict(v) for v in chain_starts[:mh_chains]]

        if mh_steps == 0 and not chain_starts:
            raise SystemExit("--mh-steps/--n-steps must be > 0 in MH modes when no starts are available")

        energy_mode = _resolve_energy_mode(
            requested="" if args.mh_energy is None else str(args.mh_energy),
            include_plausibility_if_available=True,
        )

        accepted_total = 0
        steps_total = 0
        emitted_total = 0
        chain_acceptance: List[float] = []

        if args.sampler == "mh":
            step_overrides = _parse_step_scale_kv(args.step_scale)
            step_scales: Dict[str, float] = {}
            for key in sorted(bounds.keys()):
                lo, hi = bounds[key]
                span = float(hi - lo)
                default_step = 0.1 * span if span > 0.0 else 1e-6
                step_scales[key] = float(step_overrides.get(key, default_step))
                if not (math.isfinite(step_scales[key]) and step_scales[key] > 0.0):
                    raise SystemExit(f"Invalid MH step scale for {key!r}: {step_scales[key]!r}")

            for chain_id, start in enumerate(chain_starts):
                start_local = {k: float(start[k]) for k in sorted(bounds.keys())}

                def _logp(params: Mapping[str, float]) -> float:
                    row, _, _ = _evaluate_cached(params)
                    energy = _energy_from_row(
                        row,
                        energy_mode=energy_mode,
                        chi2_objective=str(chi2_objective),
                        include_plausibility_if_available=True,
                    )
                    if not math.isfinite(energy):
                        return float("-inf")
                    return -0.5 * float(energy)

                if mh_steps > 0:
                    mh = run_metropolis_hastings(
                        logp=_logp,
                        start=start_local,
                        step_scales=step_scales,
                        n_steps=mh_steps,
                        seed=int(args.seed) + 1009 * int(chain_id),
                        burn=mh_burnin,
                        thin=mh_thin,
                        bounds=bounds,
                    )
                    chain_samples = mh.samples
                    chain_accepted_steps = int(mh.accepted_steps)
                    chain_accept_rate = float(mh.acceptance_rate)
                else:
                    chain_samples = []
                    chain_accepted_steps = 0
                    chain_accept_rate = 0.0

                accepted_total += chain_accepted_steps
                steps_total += int(mh_steps)
                chain_acceptance.append(chain_accept_rate)

                for emit_idx, params in enumerate(chain_samples):
                    step_index = int(mh_burnin + emit_idx * mh_thin)
                    _add_sample(
                        params=params,
                        detail={
                            "mode": "mh",
                            "chain_id": int(chain_id),
                            "step_index": int(step_index),
                            "seed_point": False,
                            "burn": int(mh_burnin),
                            "thin": int(mh_thin),
                        },
                        dim=dim,
                        is_seed_point=False,
                        force_emit=not dedupe_enabled,
                        extra_fields={
                            "sampler_name": "mh",
                            "chain_id": int(chain_id),
                            "step_index": int(step_index),
                            "burnin": bool(step_index < mh_burnin),
                            "thinned_emit": True,
                            "target_accept": float(args.mh_target_accept),
                            "adapt_every": int(args.mh_adapt_every),
                            "mh_energy_mode": str(energy_mode),
                            "cache_hit": bool(resume_mode == "cache"),
                        },
                    )
                    emitted_total += 1

            sampler_meta.update(
                {
                    "bounds": {k: [float(v[0]), float(v[1])] for k, v in sorted(bounds.items())},
                    "bounds_default": {k: [float(v[0]), float(v[1])] for k, v in sorted(base_bounds.items())},
                    "step_scales": {k: float(v) for k, v in sorted(step_scales.items())},
                    "mh_steps": int(mh_steps),
                    "mh_burnin": int(mh_burnin),
                    "mh_thin": int(mh_thin),
                    "mh_chains": int(mh_chains),
                    "accepted_steps": int(accepted_total),
                    "acceptance_rate": (float(accepted_total) / float(steps_total)) if steps_total > 0 else 0.0,
                    "chain_acceptance": [float(v) for v in chain_acceptance],
                    "mh_energy_mode": str(energy_mode),
                    "n_evaluated": int(len(rows) - rows_before_scan),
                }
            )
        else:
            for chain_id, start in enumerate(chain_starts):
                chain_seed = int(args.seed) + 4099 * int(chain_id)
                accept_rng = random.Random(chain_seed + 1_000_003)
                sampler = AdaptiveRWMHSampler(
                    bounds=bounds,
                    start=start,
                    seed=chain_seed,
                    init_scale=float(args.mh_init_scale),
                    target_accept=float(args.mh_target_accept),
                    adapt_every=int(args.mh_adapt_every),
                )
                current_params = sampler.current_point()
                current_row, current_point, _ = _evaluate_cached(current_params)
                current_energy = _energy_from_row(
                    current_row,
                    energy_mode=energy_mode,
                    chi2_objective=str(chi2_objective),
                    include_plausibility_if_available=True,
                )
                if not math.isfinite(current_energy):
                    current_energy = float("inf")

                chain_accepted = 0
                for step_idx in range(int(mh_steps)):
                    proposal = sampler.propose()
                    proposal_params = proposal.proposal
                    proposal_row, proposal_point, proposal_cache_hit = _evaluate_cached(proposal_params)
                    proposal_energy = _energy_from_row(
                        proposal_row,
                        energy_mode=energy_mode,
                        chi2_objective=str(chi2_objective),
                        include_plausibility_if_available=True,
                    )
                    if not math.isfinite(proposal_energy):
                        proposal_energy = float("inf")

                    if math.isinf(current_energy) and math.isinf(proposal_energy):
                        log_alpha = 0.0
                    else:
                        log_alpha = -0.5 * float(proposal_energy - current_energy)
                    if not math.isfinite(log_alpha):
                        log_alpha = -1.0e12
                    log_alpha = max(min(log_alpha, 1.0e12), -1.0e12)
                    alpha = 1.0 if log_alpha >= 0.0 else math.exp(log_alpha)
                    accepted = bool(accept_rng.random() < alpha)
                    sampler.record_acceptance(accepted)

                    if accepted:
                        chain_accepted += 1
                        current_params = dict(proposal_params)
                        current_row = dict(proposal_row)
                        current_point = dict(proposal_point)
                        current_energy = float(proposal_energy)

                    if step_idx >= int(mh_burnin) and ((step_idx - int(mh_burnin)) % int(mh_thin) == 0):
                        state = sampler.transform_state()
                        _add_sample(
                            params=current_params,
                            detail={
                                "mode": "mh_adaptive",
                                "chain_id": int(chain_id),
                                "step_index": int(step_idx),
                                "seed_point": False,
                            },
                            dim=dim,
                            is_seed_point=False,
                            force_emit=not dedupe_enabled,
                            extra_fields={
                                "sampler_name": "mh_adaptive",
                                "chain_id": int(chain_id),
                                "step_index": int(step_idx),
                                "burnin": bool(step_idx < int(mh_burnin)),
                                "thinned_emit": True,
                                "accepted": bool(accepted),
                                "log_alpha": float(log_alpha),
                                "energy": float(current_energy),
                                "energy_proposal": float(proposal_energy),
                                "proposal_scales": {k: float(v) for k, v in sorted(proposal.proposal_scales.items())},
                                "target_accept": float(args.mh_target_accept),
                                "adapt_every": int(args.mh_adapt_every),
                                "acceptance_window_rate": float(state.acceptance_window_rate),
                                "adaptation_round": int(state.adaptation_round),
                                "mh_energy_mode": str(energy_mode),
                                "cache_hit": bool(proposal_cache_hit),
                            },
                        )
                        emitted_total += 1

                accepted_total += int(chain_accepted)
                steps_total += int(mh_steps)
                chain_acceptance.append(float(chain_accepted) / float(mh_steps) if mh_steps > 0 else 0.0)

            sampler_meta.update(
                {
                    "bounds": {k: [float(v[0]), float(v[1])] for k, v in sorted(bounds.items())},
                    "bounds_default": {k: [float(v[0]), float(v[1])] for k, v in sorted(base_bounds.items())},
                    "mh_steps": int(mh_steps),
                    "mh_burnin": int(mh_burnin),
                    "mh_thin": int(mh_thin),
                    "mh_chains": int(mh_chains),
                    "mh_target_accept": float(args.mh_target_accept),
                    "mh_adapt_every": int(args.mh_adapt_every),
                    "mh_init_scale": float(args.mh_init_scale),
                    "accepted_steps": int(accepted_total),
                    "acceptance_rate": (float(accepted_total) / float(steps_total)) if steps_total > 0 else 0.0,
                    "chain_acceptance": [float(v) for v in chain_acceptance],
                    "mh_energy_mode": str(energy_mode),
                    "n_emitted": int(emitted_total),
                    "n_evaluated": int(len(rows) - rows_before_scan),
                }
            )

        if plan_chain_starts:
            sampler_meta["mh_starts_from_plan"] = True
            sampler_meta["mh_start_plan_points"] = int(len(plan_chain_starts))
            if plan_start_source_sha:
                sampler_meta["mh_start_plan_source_sha256"] = str(plan_start_source_sha)
        else:
            sampler_meta["mh_starts_from_plan"] = False

    sampler_meta["seed_points_loaded"] = int(seed_points_loaded)
    sampler_meta["seed_points_used"] = int(seed_points_used)
    sampler_meta["seed_points_skipped_duplicate"] = int(seed_points_skipped_dupe)
    sampler_meta["generated_points_skipped_duplicate"] = int(generated_duplicates)
    if bounds_overrides is not None:
        sampler_meta["bounds_override"] = {k: [float(v[0]), float(v[1])] for k, v in sorted(bounds_overrides.items())}
    if bounds_overrides_path is not None:
        sampler_meta["bounds_override_source"] = str(bounds_overrides_path)
    if seed_points_path is not None:
        sampler_meta["seed_points_source"] = str(seed_points_path)

    if not rows:
        raise SystemExit("No points were evaluated (empty parameter set)")

    if str(chi2_objective) == "joint":
        joint_ok_rows = 0
        for row in rows:
            status = str(row.get("status", "ok")).strip().lower()
            if status != "ok":
                continue
            if _finite_float(row.get("chi2_total")) is None:
                continue
            if _finite_float(row.get("chi2_joint_total")) is None:
                continue
            joint_ok_rows += 1
        if joint_ok_rows <= 0:
            requested_hint = str(rsd_chi2_field) if str(rsd_chi2_field) else "<auto>"
            print(
                "MISSING_RSD_CHI2_FIELD_FOR_JOINT_OBJECTIVE: no finite RSD chi2 values were available "
                f"for eligible rows (requested={requested_hint}).",
                file=sys.stderr,
            )
            raise SystemExit(2)

    _write_points_csv(points_csv, rows)
    if not plan_mode:
        _write_points_jsonl(points_jsonl, points)
        _write_scan_config_sidecar(
            points_jsonl=points_jsonl,
            scan_config=scan_config_payload,
            scan_config_sha256=str(scan_config_sha256),
        )

    summary = {
        "n_total": int(len(rows)),
        "n_drift_pass": int(sum(1 for r in rows if bool(r.get("drift_pass")))),
        "n_drift_required_pass": int(sum(1 for r in rows if bool(r.get("drift_required_pass")))),
        "n_invariants_ok": int(sum(1 for r in rows if bool(r.get("invariants_ok")))),
        "best_overall": _select_best(
            rows,
            drift_pass=None,
            objective_key="chi2_joint_total" if str(chi2_objective) == "joint" else "chi2_total",
        ),
        "best_drift_pass": _select_best(
            rows,
            drift_pass=True,
            objective_key="chi2_joint_total" if str(chi2_objective) == "joint" else "chi2_total",
        ),
        "best_drift_fail": _select_best(
            rows,
            drift_pass=False,
            objective_key="chi2_joint_total" if str(chi2_objective) == "joint" else "chi2_total",
        ),
        "config": {
            "model": str(args.model),
            "sample": "plan" if plan_mode else str(args.sampler),
            "sampler": "plan" if plan_mode else str(args.sampler),
            "seed": int(args.seed),
            "jobs": int(args.jobs),
            "resume": bool(args.resume),
            "resume_mode": str(resume_mode),
            "plan": None if args.plan is None else str(Path(args.plan).expanduser().resolve()),
            "toy": bool(args.toy),
            "integrator": str(args.integrator),
            "recombination_method": str(args.recombination),
            "drag_method": str(args.drag_method),
            "recombination_rtol": float(args.recombination_rtol),
            "recombination_atol": float(args.recombination_atol),
            "recombination_max_steps": int(args.recombination_max_steps),
            "mh": {
                "steps": int(mh_steps),
                "burnin": int(mh_burnin),
                "thin": int(mh_thin),
                "chains": int(mh_chains),
                "target_accept": float(args.mh_target_accept),
                "adapt_every": int(args.mh_adapt_every),
                "init_scale": float(args.mh_init_scale),
                "energy_mode": _resolve_energy_mode(
                    requested="" if args.mh_energy is None else str(args.mh_energy),
                    include_plausibility_if_available=True,
                ),
            },
            "microphysics_mode": str(args.microphysics),
            "microphysics_bounds": {
                k: [float(v[0]), float(v[1])]
                for k, v in sorted(microphysics_bounds.items())
            },
            "sampler_config": _to_json_safe(sampler_meta),
            "require_positive_drift": bool(args.require_positive_drift),
            "chi2_objective": str(chi2_objective),
            "rsd_chi2_field": (
                str(rsd_chi2_field) if str(chi2_objective) == "joint" and str(rsd_chi2_field) else None
            ),
            "rsd_chi2_weight": float(rsd_chi2_weight) if str(chi2_objective) == "joint" else None,
            "drift_precheck": str(args.drift_precheck),
            "drift_z_min": float(args.drift_z_min),
            "drift_z_max": float(args.drift_z_max),
            "drift_z_n": int(args.drift_z_n),
            "drift_z_list": [float(v) for v in drift_z_list],
            "drift_metrics_enabled": bool(not args.no_drift_metrics),
            "rsd_overlay": {
                "enabled": bool(rsd_overlay_settings.get("enabled", False)),
                "dataset_id": str(rsd_overlay_settings.get("dataset_id", "")),
                "dataset_sha256": str(rsd_overlay_settings.get("dataset_sha256") or ""),
                "dataset_available": bool(rsd_overlay_settings.get("dataset_available", False)),
                "dataset_missing_reason": (
                    None
                    if rsd_overlay_settings.get("dataset_missing_reason") is None
                    else str(rsd_overlay_settings.get("dataset_missing_reason"))
                ),
                "ap_correction": str(rsd_overlay_settings.get("ap_mode", "none")),
                "mode": str(rsd_overlay_settings.get("scan_mode", "profile_sigma8_0")),
                "transfer_model": (
                    str(rsd_overlay_settings.get("transfer_model", "bbks"))
                    if bool(rsd_overlay_settings.get("uses_primordial_knobs", False))
                    else None
                ),
                "primordial_ns": (
                    _finite_float(rsd_overlay_settings.get("primordial_ns"))
                    if bool(rsd_overlay_settings.get("uses_primordial_knobs", False))
                    else None
                ),
                "primordial_k_pivot_mpc": (
                    _finite_float(rsd_overlay_settings.get("primordial_k_pivot_mpc"))
                    if bool(rsd_overlay_settings.get("uses_primordial_knobs", False))
                    else None
                ),
            },
            "cmb": None if args.cmb is None else str(args.cmb),
            "cmb_cov": None if args.cmb_cov is None else str(args.cmb_cov),
            "cmb_bridge_z": None if z_bridge is None else float(z_bridge),
            "grid": {k: str(v) for k, v in sorted(grid_specs.items())},
            "bounds_json": None if bounds_overrides_path is None else str(bounds_overrides_path),
            "seed_points_jsonl": None if seed_points_path is None else str(seed_points_path),
            "early_time": _to_json_safe(early.to_metadata(include_rd_method=False)),
            "extended_early_time_defaults": {
                "omega_b_h2": float(early_defaults["omega_b_h2"]),
                "omega_c_h2": float(early_defaults["omega_c_h2"]),
                "N_eff": float(early_defaults["N_eff"]),
                "Tcmb_K": float(early_defaults["Tcmb_K"]),
                "Y_p": None if early_defaults["Y_p"] is None else float(early_defaults["Y_p"]),
                "Y_p_used": False,
            },
            "microphysics": {
                "mode": str(args.microphysics),
                "z_star_scale": 1.0,
                "r_s_scale": 1.0,
                "r_d_scale": 1.0,
                "microphysics_hard_ok": True,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.0,
                "microphysics_notes": [],
            },
            "microphysics_specs": {
                key: {
                    "kind": str(spec.kind),
                    "default": float(spec.default),
                    "hard_min": float(spec.hard_min),
                    "hard_max": float(spec.hard_max),
                    "plausible_min": float(spec.plausible_min),
                    "plausible_max": float(spec.plausible_max),
                }
                for key, spec in sorted(KNOB_SPECS.items())
            },
            "model_hyper": {
                "dip_bump_window": (
                    {
                        "z_dip_lo": float(model_hyper["z_dip_lo"]),
                        "z_dip_hi": float(model_hyper["z_dip_hi"]),
                        "z_bump_lo": float(model_hyper["z_bump_lo"]),
                        "z_bump_hi": float(model_hyper["z_bump_hi"]),
                        "w": float(model_hyper["w"]),
                        "factor_floor": float(model_hyper["factor_floor"]),
                    }
                    if str(args.model) == "dip_bump_window"
                    else None
                ),
                "logh_two_window": None,
            },
            "gaussian_priors": {
                k: {"mu": float(v[0]), "sigma": float(v[1])}
                for k, v in sorted(gaussian_priors.items())
            },
            "input_checksums": {
                "cmb_csv_sha256": _sha256_file(None if args.cmb is None else Path(args.cmb)),
                "cmb_cov_sha256": _sha256_file(Path(args.cmb_cov)) if args.cmb_cov is not None else None,
                "bounds_json_sha256": _sha256_file(bounds_overrides_path),
                "seed_points_jsonl_sha256": _sha256_file(seed_points_path),
                "rsd_data_sha256": (
                    str(rsd_overlay_settings.get("dataset_sha256"))
                    if bool(rsd_overlay_settings.get("enabled", False))
                    else None
                ),
            },
            "scan_config_schema": _SCAN_CONFIG_SCHEMA,
            "scan_config_sha256": str(scan_config_sha256),
            "scan_config_sidecar": str(_scan_config_sidecar_path(points_jsonl)),
            "outputs": {
                "points_csv": str(points_csv),
                "points_jsonl": str(points_jsonl),
                "summary_json": str(summary_json),
            },
            "generated_utc": _now_utc(),
        },
    }
    if str(args.bbn_prior) != "none":
        summary["config"]["bbn_prior"] = str(args.bbn_prior)
    if str(args.optimize) == "nelder_mead":
        summary["config"]["opt_multistart"] = int(args.opt_multistart)
        if int(args.opt_multistart) > 1:
            summary["config"]["opt_init"] = str(args.opt_init)
            summary["config"]["opt_seed"] = int(args.opt_seed)
    summary_json.write_text(json.dumps(_to_json_safe(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"[ok] wrote {points_csv}")
    print(f"[ok] wrote {points_jsonl}")
    print(f"[ok] wrote {summary_json}")


if __name__ == "__main__":
    main()
