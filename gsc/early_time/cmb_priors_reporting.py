"""Batch reporting helpers for Phase 2 compressed CMB priors outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from ..datasets.cmb_priors import CMBPriorsDataset
from ..datasets.cmb_priors_driver import CMBPriorsLikelihood
from ..measurement_model import (
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
)
from .cmb_priors_driver import CMBPriorsDriverConfig
from .numerics_invariants import (
    DEFAULT_REQUIRED_CHECK_IDS,
    INVARIANTS_SCHEMA_VERSION as MODEL_INVARIANTS_SCHEMA_VERSION,
    run_early_time_invariants,
)
from .params import EarlyTimeParams


SCHEMA_VERSION = "phase2.m4.cmb_priors_report.v1"
INVARIANTS_SCHEMA_VERSION = "phase2.m8.early_time_invariants_report.v1"


@dataclass(frozen=True)
class CMBPriorsBatchConfig:
    omega_b_h2: float
    omega_c_h2: float
    N_eff: float = 3.046
    Tcmb_K: float = 2.7255
    mode: str | None = None
    z_bridge: float | None = None


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_git_commit(repo_root: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or None
    except Exception:
        return None


def _load_json(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"bestfit JSON must be an object: {path}")
    return obj


def _iter_bestfit_files(fit_dir: Path) -> List[Path]:
    files = sorted(p for p in fit_dir.glob("*_bestfit.json") if p.is_file())
    if not files:
        raise ValueError(f"No *_bestfit.json files found under: {fit_dir}")
    return files


def _build_model(model_name: str, params: Mapping[str, float]):
    if "H0" not in params:
        raise ValueError("bestfit params must include H0")
    h0_si = H0_to_SI(float(params["H0"]))
    if model_name == "lcdm":
        om = float(params["Omega_m"])
        return FlatLambdaCDMHistory(H0=h0_si, Omega_m=om, Omega_Lambda=(1.0 - om))
    if model_name == "gsc_powerlaw":
        return PowerLawHistory(H0=h0_si, p=float(params["p"]))
    if model_name == "gsc_transition":
        om = float(params["Omega_m"])
        return GSCTransitionHistory(
            H0=h0_si,
            Omega_m=om,
            Omega_Lambda=(1.0 - om),
            p=float(params["p"]),
            z_transition=float(params["z_transition"]),
        )
    raise ValueError(f"Unsupported bestfit model: {model_name!r}")


def _resolve_mode(*, cfg_mode: str | None, fit_payload: Mapping[str, Any]) -> str:
    if cfg_mode in ("distance_priors", "shift_params"):
        return str(cfg_mode)
    cmb_block = fit_payload.get("cmb") if isinstance(fit_payload, dict) else None
    mode_raw = None
    if isinstance(cmb_block, dict):
        mode_raw = cmb_block.get("mode")
    mode = str(mode_raw) if mode_raw is not None else "distance_priors"
    if mode == "theta_star":
        return "shift_params"
    if mode in ("distance_priors", "shift_params"):
        return mode
    return "distance_priors"


def _resolve_bridge_z(
    *,
    cfg_bridge_z: float | None,
    fit_payload: Mapping[str, Any],
    model_name: str,
) -> float | None:
    if model_name == "lcdm":
        return None
    if cfg_bridge_z is not None:
        return float(cfg_bridge_z)
    cmb_block = fit_payload.get("cmb") if isinstance(fit_payload, dict) else None
    if isinstance(cmb_block, dict):
        value = cmb_block.get("bridge_z")
        if value is not None:
            return float(value)
    return None


def _as_float_mapping(payload: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k, v in payload.items():
        out[str(k)] = float(v)
    return out


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    return str(value)


def evaluate_fit_dir_cmb_priors(
    *,
    fit_dir: Path,
    priors: CMBPriorsDataset,
    config: CMBPriorsBatchConfig,
    repo_root: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    fit_dir = fit_dir.expanduser().resolve()
    files = _iter_bestfit_files(fit_dir)

    models: List[Dict[str, Any]] = []
    table_rows: List[Dict[str, Any]] = []

    for bestfit_path in files:
        payload = _load_json(bestfit_path)
        model_name = str(payload.get("model") or "").strip()
        if not model_name:
            raise ValueError(f"bestfit JSON missing model field: {bestfit_path}")

        best = payload.get("best")
        if not isinstance(best, dict):
            raise ValueError(f"bestfit JSON missing best block: {bestfit_path}")
        params_raw = best.get("params")
        if not isinstance(params_raw, dict):
            raise ValueError(f"bestfit JSON missing best.params object: {bestfit_path}")

        params = _as_float_mapping(params_raw)
        model = _build_model(model_name, params)

        mode = _resolve_mode(cfg_mode=config.mode, fit_payload=payload)
        z_bridge = _resolve_bridge_z(cfg_bridge_z=config.z_bridge, fit_payload=payload, model_name=model_name)
        if model_name != "lcdm" and z_bridge is None:
            raise ValueError(
                f"bestfit {bestfit_path.name} requires bridge_z for non-LCDM model {model_name!r}"
            )

        early_time = EarlyTimeParams(
            omega_b_h2=float(config.omega_b_h2),
            omega_c_h2=float(config.omega_c_h2),
            N_eff=float(config.N_eff),
            Tcmb_K=float(config.Tcmb_K),
        )

        driver_cfg = CMBPriorsDriverConfig(
            **early_time.to_cmb_driver_kwargs(),
            mode=mode,
            z_bridge=z_bridge,
            H0_km_s_Mpc=float(params["H0"]) if model_name == "lcdm" else None,
            Omega_m=float(params["Omega_m"]) if model_name == "lcdm" else None,
        )

        like = CMBPriorsLikelihood(priors=priors, driver_config=driver_cfg)
        evaluation = like.evaluate(model)
        result = like.chi2_from_evaluation(evaluation)

        model_id = bestfit_path.name.replace("_bestfit.json", "")
        per_model_rows: List[Dict[str, Any]] = []
        for pr in priors.priors:
            pred = float(evaluation.predicted_for_keys[pr.name])
            sigma_eff = math.sqrt(float(pr.sigma) ** 2 + float(pr.sigma_theory) ** 2)
            pull = (pred - float(pr.value)) / sigma_eff if sigma_eff > 0.0 else float("nan")
            row = {
                "model_id": model_id,
                "bestfit_file": str(bestfit_path),
                "key": str(pr.name),
                "prior": float(pr.value),
                "sigma": float(pr.sigma),
                "sigma_theory": float(pr.sigma_theory),
                "pred": pred,
                "diag_pull": float(pull),
                "diag_contrib": float(pull * pull),
                "chi2_model": float(result.chi2),
                "ndof": int(result.ndof),
                "method": str(result.meta.get("method", "diag")),
            }
            per_model_rows.append(row)
            table_rows.append(dict(row))

        model_entry: Dict[str, Any] = {
            "model_id": model_id,
            "bestfit_file": str(bestfit_path),
            "model": model_name,
            "params": dict(params),
            "mode": mode,
            "bridge_z": None if z_bridge is None else float(z_bridge),
            "chi2": float(result.chi2),
            "ndof": int(result.ndof),
            "method": str(result.meta.get("method", "diag")),
            "keys_used": [str(k) for k in evaluation.predicted_for_keys.keys()],
            "predicted": {str(k): float(v) for k, v in evaluation.predicted_for_keys.items()},
            # Keep diagnostics JSON-safe without assuming all fields are numeric.
            "predicted_all": {str(k): _json_safe_value(v) for k, v in evaluation.predicted_all.items()},
            "rows": per_model_rows,
        }
        models.append(model_entry)

    chi2_total = float(sum(float(m["chi2"]) for m in models))
    ndof_total = int(sum(int(m["ndof"]) for m in models))
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": {
            "tool": "early_time_cmb_priors_report",
            "timestamp_utc": _now_utc(),
            "git_commit": _safe_git_commit(repo_root),
        },
        "fit_dir": str(fit_dir),
        "priors": {
            "name": str(priors.name),
            "keys": [str(k) for k in priors.keys],
            "cov_mode": bool(priors.cov is not None),
        },
        "config": {
            "omega_b_h2": float(config.omega_b_h2),
            "omega_c_h2": float(config.omega_c_h2),
            "N_eff": float(config.N_eff),
            "Tcmb_K": float(config.Tcmb_K),
            "mode": None if config.mode is None else str(config.mode),
            "z_bridge": None if config.z_bridge is None else float(config.z_bridge),
        },
        "summary": {
            "model_count": len(models),
            "chi2_total": chi2_total,
            "ndof_total": ndof_total,
        },
        "models": models,
    }
    return report, table_rows


def build_numerics_invariants_report(
    *,
    cmb_report: Mapping[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    models_raw = cmb_report.get("models") if isinstance(cmb_report, Mapping) else None
    checks: Dict[str, Any] = {}
    failing_model_count = 0
    violation_count = 0
    missing_required_count = 0

    if isinstance(models_raw, list):
        for idx, model in enumerate(models_raw):
            if not isinstance(model, Mapping):
                continue
            model_id = str(model.get("model_id") or f"model_{idx}")
            predicted_raw = model.get("predicted_all")
            predicted: Mapping[str, Any]
            if isinstance(predicted_raw, Mapping):
                predicted = predicted_raw
            else:
                predicted = {}
            report = run_early_time_invariants(
                predicted,
                profile="phase2.m8",
                strict=True,
                required_check_ids=DEFAULT_REQUIRED_CHECK_IDS,
            )
            checks[model_id] = report
            if not bool(report.get("ok", False)):
                failing_model_count += 1
            violations = report.get("violations")
            if isinstance(violations, list):
                violation_count += len(violations)
            missing_required = report.get("missing_required")
            if isinstance(missing_required, list):
                missing_required_count += len(missing_required)

    return {
        "schema_version": INVARIANTS_SCHEMA_VERSION,
        "generated_by": {
            "tool": "early_time_cmb_priors_report",
            "timestamp_utc": _now_utc(),
            "git_commit": _safe_git_commit(repo_root),
        },
        "source": {
            "cmb_report_schema_version": str(cmb_report.get("schema_version", "")),
            "fit_dir": _json_safe_value(cmb_report.get("fit_dir")),
        },
        "strict": True,
        "required_check_ids": list(DEFAULT_REQUIRED_CHECK_IDS),
        "model_invariants_schema_version": int(MODEL_INVARIANTS_SCHEMA_VERSION),
        "ok": failing_model_count == 0,
        "summary": {
            "model_count": len(checks),
            "failing_model_count": int(failing_model_count),
            "violation_count": int(violation_count),
            "missing_required_count": int(missing_required_count),
        },
        "checks": checks,
    }


def write_cmb_priors_report_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_numerics_invariants_report_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_cmb_priors_report_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    header = [
        "model_id",
        "bestfit_file",
        "key",
        "prior",
        "sigma",
        "sigma_theory",
        "pred",
        "diag_pull",
        "diag_contrib",
        "chi2_model",
        "ndof",
        "method",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in header})


__all__ = [
    "SCHEMA_VERSION",
    "INVARIANTS_SCHEMA_VERSION",
    "CMBPriorsBatchConfig",
    "evaluate_fit_dir_cmb_priors",
    "build_numerics_invariants_report",
    "write_cmb_priors_report_csv",
    "write_cmb_priors_report_json",
    "write_numerics_invariants_report_json",
]
