"""Shared early-time parameter container and parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


def _is_finite(value: float) -> bool:
    return math.isfinite(float(value))


@dataclass(frozen=True)
class EarlyTimeParams:
    """Canonical early-time parameters used by rd/CMB bridge paths."""

    omega_b_h2: float
    omega_c_h2: float
    N_eff: float = 3.046
    Tcmb_K: float = 2.7255
    rd_method: str = "eisenstein_hu_1998"

    def __post_init__(self) -> None:
        if not (float(self.omega_b_h2) > 0.0 and _is_finite(float(self.omega_b_h2))):
            raise ValueError("omega_b_h2 must be finite and > 0")
        if not (float(self.omega_c_h2) >= 0.0 and _is_finite(float(self.omega_c_h2))):
            raise ValueError("omega_c_h2 must be finite and >= 0")
        if not _is_finite(float(self.N_eff)):
            raise ValueError("N_eff must be finite")
        if not (float(self.Tcmb_K) > 0.0 and _is_finite(float(self.Tcmb_K))):
            raise ValueError("Tcmb_K must be finite and > 0")
        method = str(self.rd_method).strip()
        if not method:
            raise ValueError("rd_method must be a non-empty string")

    def to_rd_kwargs(self) -> dict[str, float | str]:
        return {
            "omega_b_h2": float(self.omega_b_h2),
            "omega_c_h2": float(self.omega_c_h2),
            "N_eff": float(self.N_eff),
            "Tcmb_K": float(self.Tcmb_K),
            "method": str(self.rd_method),
        }

    def to_cmb_driver_kwargs(self) -> dict[str, float]:
        return {
            "omega_b_h2": float(self.omega_b_h2),
            "omega_c_h2": float(self.omega_c_h2),
            "N_eff": float(self.N_eff),
            "Tcmb_K": float(self.Tcmb_K),
        }

    def to_metadata(self, *, include_rd_method: bool = True) -> dict[str, float | str]:
        payload: dict[str, float | str] = {
            "omega_b_h2": float(self.omega_b_h2),
            "omega_c_h2": float(self.omega_c_h2),
            "N_eff": float(self.N_eff),
            "Tcmb_K": float(self.Tcmb_K),
        }
        if include_rd_method:
            payload["rd_method"] = str(self.rd_method)
        return payload


def _require_message(context: str) -> str:
    ctx = context.strip()
    prefix = f"{ctx} " if ctx else ""
    return f"{prefix}requires --omega-b-h2 and --omega-c-h2"


def early_time_params_from_values(
    *,
    omega_b_h2: float | None,
    omega_c_h2: float | None,
    N_eff: float = 3.046,
    Tcmb_K: float = 2.7255,
    rd_method: str = "eisenstein_hu_1998",
    require: bool = False,
    context: str = "",
) -> EarlyTimeParams | None:
    if omega_b_h2 is None and omega_c_h2 is None:
        if require:
            raise ValueError(_require_message(context))
        return None
    if omega_b_h2 is None or omega_c_h2 is None:
        raise ValueError(_require_message(context))
    return EarlyTimeParams(
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(N_eff),
        Tcmb_K=float(Tcmb_K),
        rd_method=str(rd_method),
    )


def early_time_params_from_namespace(
    args: Any,
    *,
    require: bool = False,
    context: str = "",
    n_eff_attrs: Sequence[str] = ("N_eff", "Neff"),
) -> EarlyTimeParams | None:
    omega_b = getattr(args, "omega_b_h2", None)
    omega_c = getattr(args, "omega_c_h2", None)

    n_eff: float | None = None
    for attr in n_eff_attrs:
        if hasattr(args, attr):
            value = getattr(args, attr)
            if value is not None:
                n_eff = float(value)
                break
    if n_eff is None:
        n_eff = 3.046

    tcmb = getattr(args, "Tcmb_K", 2.7255)
    rd_method = getattr(args, "rd_method", "eisenstein_hu_1998")
    return early_time_params_from_values(
        omega_b_h2=None if omega_b is None else float(omega_b),
        omega_c_h2=None if omega_c is None else float(omega_c),
        N_eff=float(n_eff),
        Tcmb_K=float(tcmb),
        rd_method=str(rd_method),
        require=bool(require),
        context=context,
    )


__all__ = [
    "EarlyTimeParams",
    "early_time_params_from_namespace",
    "early_time_params_from_values",
]
