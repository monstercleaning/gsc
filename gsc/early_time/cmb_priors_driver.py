"""Reusable CMB priors driver for Phase 2 early-universe workflows."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Dict, Mapping, Optional, Protocol, Sequence

from ..datasets.base import Chi2Result, HzModel
from ..measurement_model import MPC_SI
from .cmb_microphysics_knobs import knobs_from_dict, knobs_to_dict
from .cmb_shift_params import compute_bridged_shift_params, compute_lcdm_shift_params


CMBKeyAlias = Callable[[Mapping[str, float]], float]

_SUPPORTED_MODES = {"shift_params", "distance_priors"}


class _CMBPriorsDatasetLike(Protocol):
    keys: Sequence[str]

    def chi2_from_values(self, predicted: Dict[str, float]) -> Chi2Result:  # pragma: no cover - protocol only
        ...


@dataclass
class CMBPriorsDriverConfig:
    """Configuration for the reusable CMB-priors driver."""

    omega_b_h2: float
    omega_c_h2: float
    N_eff: float = 3.046
    Tcmb_K: float = 2.7255
    mode: str = "distance_priors"
    z_bridge: float | None = None
    D_M_model_to_z_bridge_m: float | None = None
    rs_star_calibration: float = 1.0
    dm_star_calibration: float = 1.0
    integrator: str = "trap"
    integration_eps_abs: float = 1e-10
    integration_eps_rel: float = 1e-10
    recombination_method: str = "fit"
    drag_method: str = "eh98"
    recombination_rtol: float = 1e-6
    recombination_atol: float = 1e-10
    recombination_max_steps: int = 4096
    Y_p: float | None = None
    microphysics: Mapping[str, float] | None = None
    # Optional explicit LCDM params. If missing, they are inferred from model.
    H0_km_s_Mpc: float | None = None
    Omega_m: float | None = None

    def validate(self) -> None:
        if self.mode not in _SUPPORTED_MODES:
            raise ValueError(f"Unsupported CMB driver mode: {self.mode!r}")
        if not (self.omega_b_h2 > 0.0 and math.isfinite(float(self.omega_b_h2))):
            raise ValueError("omega_b_h2 must be finite and > 0")
        if not (self.omega_c_h2 >= 0.0 and math.isfinite(float(self.omega_c_h2))):
            raise ValueError("omega_c_h2 must be finite and >= 0")
        if self.z_bridge is not None and not (float(self.z_bridge) > 0.0 and math.isfinite(float(self.z_bridge))):
            raise ValueError("z_bridge must be finite and > 0 when set")
        if self.D_M_model_to_z_bridge_m is not None and not (
            float(self.D_M_model_to_z_bridge_m) >= 0.0 and math.isfinite(float(self.D_M_model_to_z_bridge_m))
        ):
            raise ValueError("D_M_model_to_z_bridge_m must be finite and >= 0 when set")
        if not (float(self.rs_star_calibration) > 0.0 and math.isfinite(float(self.rs_star_calibration))):
            raise ValueError("rs_star_calibration must be finite and > 0")
        if not (float(self.dm_star_calibration) > 0.0 and math.isfinite(float(self.dm_star_calibration))):
            raise ValueError("dm_star_calibration must be finite and > 0")
        if str(self.integrator).strip().lower() not in {"trap", "adaptive_simpson"}:
            raise ValueError("integrator must be one of: trap, adaptive_simpson")
        if not (math.isfinite(float(self.integration_eps_abs)) and float(self.integration_eps_abs) > 0.0):
            raise ValueError("integration_eps_abs must be finite and > 0")
        if not (math.isfinite(float(self.integration_eps_rel)) and float(self.integration_eps_rel) > 0.0):
            raise ValueError("integration_eps_rel must be finite and > 0")
        if str(self.recombination_method).strip().lower() not in {"fit", "peebles3"}:
            raise ValueError("recombination_method must be one of: fit, peebles3")
        if str(self.drag_method).strip().lower() not in {"eh98", "ode"}:
            raise ValueError("drag_method must be one of: eh98, ode")
        if not (math.isfinite(float(self.recombination_rtol)) and float(self.recombination_rtol) > 0.0):
            raise ValueError("recombination_rtol must be finite and > 0")
        if not (math.isfinite(float(self.recombination_atol)) and float(self.recombination_atol) > 0.0):
            raise ValueError("recombination_atol must be finite and > 0")
        if int(self.recombination_max_steps) <= 0:
            raise ValueError("recombination_max_steps must be > 0")
        if self.Y_p is not None and not (0.0 <= float(self.Y_p) < 1.0 and math.isfinite(float(self.Y_p))):
            raise ValueError("Y_p must be finite and in [0,1)")
        knobs_from_dict(self.microphysics)


@dataclass(frozen=True)
class CMBPriorsEvaluation:
    result: Chi2Result
    predicted_all: Dict[str, float]
    predicted_for_keys: Dict[str, float]


def default_cmb_key_aliases() -> Dict[str, CMBKeyAlias]:
    """Return default aliases for commonly used CMB prior key names."""
    return {
        "100theta_star": lambda pred: 100.0 * float(pred["theta_star"]),
        "100*theta_star": lambda pred: 100.0 * float(pred["theta_star"]),
        "ell_A": lambda pred: float(pred["lA"]),
        "omega_m_h2": lambda pred: float(pred["omega_b_h2"]) + float(pred["omega_c_h2"]),
    }


def _infer_h0_km_s_mpc(model: HzModel, explicit_h0_km_s_mpc: float | None) -> float:
    if explicit_h0_km_s_mpc is not None:
        return float(explicit_h0_km_s_mpc)
    h0_si = float(model.H(0.0))
    if not (h0_si > 0.0 and math.isfinite(h0_si)):
        raise ValueError("model.H(0) must be finite and > 0")
    return float(h0_si) * float(MPC_SI) / 1000.0


def _infer_omega_m(model: HzModel, explicit_omega_m: float | None) -> float:
    if explicit_omega_m is not None:
        return float(explicit_omega_m)
    inferred = getattr(model, "Omega_m", None)
    if inferred is None:
        raise ValueError("Omega_m is required for LCDM CMB priors (set config.Omega_m or model.Omega_m).")
    omega_m = float(inferred)
    if not (omega_m > 0.0 and math.isfinite(omega_m)):
        raise ValueError("Omega_m must be finite and > 0")
    return omega_m


def predict_cmb_observables(
    *,
    model: HzModel,
    config: CMBPriorsDriverConfig,
) -> Dict[str, float]:
    """Compute a superset of CMB observables for priors evaluation."""
    config.validate()
    microphysics_dict = knobs_to_dict(knobs_from_dict(config.microphysics))
    if config.z_bridge is None:
        return compute_lcdm_shift_params(
            H0_km_s_Mpc=_infer_h0_km_s_mpc(model, config.H0_km_s_Mpc),
            Omega_m=_infer_omega_m(model, config.Omega_m),
            omega_b_h2=float(config.omega_b_h2),
            omega_c_h2=float(config.omega_c_h2),
            N_eff=float(config.N_eff),
            Tcmb_K=float(config.Tcmb_K),
            rs_star_calibration=float(config.rs_star_calibration),
            dm_star_calibration=float(config.dm_star_calibration),
            Y_p=None if config.Y_p is None else float(config.Y_p),
            microphysics=microphysics_dict,
            integrator=str(config.integrator),
            integration_eps_abs=float(config.integration_eps_abs),
            integration_eps_rel=float(config.integration_eps_rel),
            recombination_method=str(config.recombination_method),
            drag_method=str(config.drag_method),
            recombination_rtol=float(config.recombination_rtol),
            recombination_atol=float(config.recombination_atol),
            recombination_max_steps=int(config.recombination_max_steps),
        )
    return compute_bridged_shift_params(
        model=model,
        z_bridge=float(config.z_bridge),
        omega_b_h2=float(config.omega_b_h2),
        omega_c_h2=float(config.omega_c_h2),
        N_eff=float(config.N_eff),
        Tcmb_K=float(config.Tcmb_K),
        rs_star_calibration=float(config.rs_star_calibration),
        dm_star_calibration=float(config.dm_star_calibration),
        Y_p=None if config.Y_p is None else float(config.Y_p),
        microphysics=microphysics_dict,
        integrator=str(config.integrator),
        integration_eps_abs=float(config.integration_eps_abs),
        integration_eps_rel=float(config.integration_eps_rel),
        recombination_method=str(config.recombination_method),
        drag_method=str(config.drag_method),
        recombination_rtol=float(config.recombination_rtol),
        recombination_atol=float(config.recombination_atol),
        recombination_max_steps=int(config.recombination_max_steps),
        D_M_model_to_z_bridge_m=(
            None
            if config.D_M_model_to_z_bridge_m is None
            else float(config.D_M_model_to_z_bridge_m)
        ),
    )


def materialize_cmb_prior_values(
    *,
    predicted: Mapping[str, float],
    keys: Sequence[str],
    key_aliases: Mapping[str, CMBKeyAlias] | None = None,
) -> Dict[str, float]:
    """Materialize priors keys from predictions, supporting alias mapping."""
    alias_map: Dict[str, CMBKeyAlias] = default_cmb_key_aliases()
    if key_aliases is not None:
        alias_map.update(dict(key_aliases))

    out: Dict[str, float] = {}
    missing: list[str] = []
    for key in keys:
        if key in predicted:
            out[key] = float(predicted[key])
            continue
        fn = alias_map.get(key)
        if fn is None:
            missing.append(str(key))
            continue
        out[key] = float(fn(predicted))

    if missing:
        available = sorted(str(k) for k in predicted.keys())
        aliases = sorted(alias_map.keys())
        raise ValueError(
            "Missing predicted CMB prior keys: "
            f"{missing}. Available={available}. Alias keys={aliases}."
        )
    return out


def evaluate_cmb_priors_dataset(
    *,
    dataset: _CMBPriorsDatasetLike,
    model: HzModel,
    config: CMBPriorsDriverConfig,
    key_aliases: Mapping[str, CMBKeyAlias] | None = None,
) -> CMBPriorsEvaluation:
    """Evaluate a CMB priors dataset via reusable early-time prediction driver."""
    predicted_all = predict_cmb_observables(model=model, config=config)
    predicted_for_keys = materialize_cmb_prior_values(
        predicted=predicted_all,
        keys=tuple(dataset.keys),
        key_aliases=key_aliases,
    )
    result = dataset.chi2_from_values(predicted_for_keys)
    return CMBPriorsEvaluation(
        result=result,
        predicted_all=dict(predicted_all),
        predicted_for_keys=dict(predicted_for_keys),
    )


__all__ = [
    "CMBKeyAlias",
    "CMBPriorsDriverConfig",
    "CMBPriorsEvaluation",
    "default_cmb_key_aliases",
    "evaluate_cmb_priors_dataset",
    "materialize_cmb_prior_values",
    "predict_cmb_observables",
]
