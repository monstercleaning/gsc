"""Diagnostic microphysics scaling knobs for compressed-CMB priors.

These knobs are intentionally phenomenological and diagnostic-only. They do not
claim a physical derivation; they provide controlled stress-testing dimensions
for E2 closure scans.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class MicrophysicsKnobs:
    z_star_scale: float = 1.0
    r_s_scale: float = 1.0
    r_d_scale: float = 1.0

    def validate(self, reason_prefix: str = "") -> None:
        validate_knobs(_knobs_dataclass_to_dict(self), reason_prefix=reason_prefix)


@dataclass(frozen=True)
class KnobSpec:
    name: str
    kind: str
    default: float
    hard_min: float
    hard_max: float
    plausible_min: float
    plausible_max: float
    doc: str = ""


KNOB_SPECS: Dict[str, KnobSpec] = {
    "z_star_scale": KnobSpec(
        name="z_star_scale",
        kind="scale",
        default=1.0,
        hard_min=0.90,
        hard_max=1.10,
        plausible_min=0.98,
        plausible_max=1.02,
        doc="Effective scaling of recombination redshift z_star (diagnostic only).",
    ),
    "r_s_scale": KnobSpec(
        name="r_s_scale",
        kind="scale",
        default=1.0,
        hard_min=0.80,
        hard_max=1.20,
        plausible_min=0.95,
        plausible_max=1.05,
        doc="Effective scaling of r_s(z_star) (diagnostic only).",
    ),
    "r_d_scale": KnobSpec(
        name="r_d_scale",
        kind="scale",
        default=1.0,
        hard_min=0.80,
        hard_max=1.20,
        plausible_min=0.95,
        plausible_max=1.05,
        doc="Effective scaling of drag horizon r_d (diagnostic only).",
    ),
}
_KNOWN_KEYS = frozenset(KNOB_SPECS.keys())
_ORDERED_KEYS = tuple(sorted(_KNOWN_KEYS))
_HUGE_PENALTY = 1.0e30


def iter_knob_specs_sorted() -> tuple[KnobSpec, ...]:
    """Return knob specs in stable lexicographic order."""
    return tuple(KNOB_SPECS[key] for key in sorted(KNOB_SPECS.keys()))


def _knobs_dataclass_to_dict(knobs: MicrophysicsKnobs) -> Dict[str, float]:
    return {
        "z_star_scale": float(knobs.z_star_scale),
        "r_s_scale": float(knobs.r_s_scale),
        "r_d_scale": float(knobs.r_d_scale),
    }


def _normalize_knobs_mapping(data: Mapping[str, Any]) -> Dict[str, float]:
    unknown = sorted(str(k) for k in data.keys() if str(k) not in _KNOWN_KEYS)
    if unknown:
        raise ValueError(f"unknown microphysics knob(s): {', '.join(unknown)}")
    out: Dict[str, float] = {}
    for key in _ORDERED_KEYS:
        spec = KNOB_SPECS[key]
        raw = data.get(key, spec.default)
        try:
            value = float(raw)
        except Exception as exc:
            raise ValueError(f"{key} must be a finite float (got {raw!r})") from exc
        if not math.isfinite(value):
            raise ValueError(f"{key} must be finite (got {raw!r})")
        out[key] = float(value)
    return out


def _coerce_knobs_dict(data: Optional[Mapping[str, Any] | MicrophysicsKnobs]) -> Dict[str, float]:
    if data is None:
        return {key: float(KNOB_SPECS[key].default) for key in _ORDERED_KEYS}
    if isinstance(data, MicrophysicsKnobs):
        return _knobs_dataclass_to_dict(data)
    if not isinstance(data, Mapping):
        raise ValueError("microphysics must be a mapping, MicrophysicsKnobs, or None")
    return _normalize_knobs_mapping(data)


def _format_float(value: float) -> str:
    return f"{float(value):.12g}"


def validate_knobs(
    knobs: Optional[Mapping[str, Any] | MicrophysicsKnobs],
    *,
    reason_prefix: str = "",
) -> None:
    values = _coerce_knobs_dict(knobs)
    prefix = f"{reason_prefix}: " if str(reason_prefix).strip() else ""
    for key in _ORDERED_KEYS:
        spec = KNOB_SPECS[key]
        value = float(values[key])
        if value < float(spec.hard_min) or value > float(spec.hard_max):
            raise ValueError(
                f"{prefix}{key}={_format_float(value)} outside hard bounds "
                f"[{_format_float(spec.hard_min)}, {_format_float(spec.hard_max)}]"
            )


def assess_knobs(knobs: Optional[Mapping[str, Any] | MicrophysicsKnobs]) -> Dict[str, object]:
    try:
        values = _coerce_knobs_dict(knobs)
        validate_knobs(values, reason_prefix="microphysics")
    except ValueError as exc:
        return {
            "hard_ok": False,
            "plausible_ok": False,
            "max_rel_dev": float(_HUGE_PENALTY),
            "penalty": float(_HUGE_PENALTY),
            "notes": [str(exc)],
            "per_knob": {},
        }

    notes = []
    penalty = 0.0
    max_rel_dev = 0.0
    per_knob: Dict[str, Dict[str, float | bool]] = {}
    for key in _ORDERED_KEYS:
        spec = KNOB_SPECS[key]
        value = float(values[key])
        rel_dev = abs(value / float(spec.default) - 1.0)
        max_rel_dev = max(max_rel_dev, rel_dev)
        plausible_ok = float(spec.plausible_min) <= value <= float(spec.plausible_max)
        contribution = 0.0
        if not plausible_ok:
            if value < float(spec.plausible_min):
                delta = float(spec.plausible_min) - value
            else:
                delta = value - float(spec.plausible_max)
            half_width = 0.5 * (float(spec.plausible_max) - float(spec.plausible_min))
            if half_width <= 0.0:
                raise ValueError(f"Invalid plausible bounds for {key}")
            contribution = (delta / half_width) ** 2
            notes.append(
                f"{key}={_format_float(value)} outside plausible "
                f"[{_format_float(spec.plausible_min)}, {_format_float(spec.plausible_max)}]"
            )
        penalty += contribution
        per_knob[key] = {
            "value": value,
            "default": float(spec.default),
            "rel_dev": float(rel_dev),
            "plausible_ok": bool(plausible_ok),
            "penalty_contrib": float(contribution),
            "hard_min": float(spec.hard_min),
            "hard_max": float(spec.hard_max),
            "plausible_min": float(spec.plausible_min),
            "plausible_max": float(spec.plausible_max),
        }
    notes.sort()
    return {
        "hard_ok": True,
        "plausible_ok": len(notes) == 0,
        "max_rel_dev": float(max_rel_dev),
        "penalty": float(penalty),
        "notes": notes,
        "per_knob": per_knob,
    }


def knobs_from_dict(data: Optional[Mapping[str, Any] | MicrophysicsKnobs]) -> MicrophysicsKnobs:
    values = _coerce_knobs_dict(data)
    validate_knobs(values, reason_prefix="microphysics")
    knobs = MicrophysicsKnobs(
        z_star_scale=float(values["z_star_scale"]),
        r_s_scale=float(values["r_s_scale"]),
        r_d_scale=float(values["r_d_scale"]),
    )
    return knobs


def knobs_to_dict(knobs: MicrophysicsKnobs) -> Dict[str, float]:
    values = _knobs_dataclass_to_dict(knobs)
    validate_knobs(values, reason_prefix="microphysics")
    return {key: float(values[key]) for key in _ORDERED_KEYS}


__all__ = [
    "KnobSpec",
    "KNOB_SPECS",
    "MicrophysicsKnobs",
    "iter_knob_specs_sorted",
    "validate_knobs",
    "assess_knobs",
    "knobs_from_dict",
    "knobs_to_dict",
]
