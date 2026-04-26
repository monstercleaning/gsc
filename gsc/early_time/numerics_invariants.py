"""Phase 2 numerical invariants for early-time predictions.

The checks in this module are structural/consistency checks only:
- finite and positive core values
- alias consistency (theta_star vs 100theta_star)
- algebraic identities (lA and rd unit conversion)

No scientific model equations are changed here.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Sequence

from ..measurement_model import MPC_SI


INVARIANTS_SCHEMA_VERSION = 1

CHECK_ID_FINITE_POSITIVE_CORE = "finite_positive_core"
CHECK_ID_ALIAS_THETA_100 = "alias_theta_star_100theta_star"
CHECK_ID_IDENTITY_LA = "identity_lA_equals_pi_over_theta_star"
CHECK_ID_IDENTITY_RD_UNITS = "identity_rd_m_equals_rd_Mpc_times_MPC_SI"

DEFAULT_POSITIVE_KEYS: tuple[str, ...] = (
    "theta_star",
    "100theta_star",
    "100*theta_star",
    "lA",
    "R",
    "z_star",
    "r_s_star_Mpc",
    "rd_Mpc",
    "rd_m",
    "D_M_star_Mpc",
)

CORE_POSITIVE_REQUIRED_KEYS: tuple[str, ...] = (
    "theta_star",
    "lA",
    "R",
    "rd_Mpc",
)

DEFAULT_REQUIRED_CHECK_IDS: tuple[str, ...] = (
    CHECK_ID_FINITE_POSITIVE_CORE,
    CHECK_ID_ALIAS_THETA_100,
    CHECK_ID_IDENTITY_LA,
    CHECK_ID_IDENTITY_RD_UNITS,
)


def _as_float(value: Any) -> float:
    """Convert numeric-like values (including numpy scalars) to float."""
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid numeric value")
    try:
        return float(value)
    except Exception as exc:
        raise ValueError(f"cannot convert to float: {value!r}") from exc


def _approx_equal(a: float, b: float, *, tol_abs: float, tol_rel: float) -> bool:
    scale = max(abs(float(a)), abs(float(b)))
    return abs(float(a) - float(b)) <= max(float(tol_abs), float(tol_rel) * scale)


def _json_safe(value: Any) -> Any:
    """Return JSON-safe builtins only."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return float(value)
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(v) for v in value]
    try:
        fv = float(value)
        return float(fv) if math.isfinite(fv) else str(fv)
    except Exception:
        return str(value)


def _materialize_predicted_aliases(predicted: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Return a copy with deterministic derived aliases useful for strict checks."""
    observed = dict(predicted)
    derived: Dict[str, str] = {}

    if "theta_star" not in observed:
        if "100theta_star" in observed:
            try:
                observed["theta_star"] = _as_float(observed["100theta_star"]) / 100.0
                derived["theta_star"] = "from 100theta_star/100"
            except ValueError:
                pass
        elif "100*theta_star" in observed:
            try:
                observed["theta_star"] = _as_float(observed["100*theta_star"]) / 100.0
                derived["theta_star"] = "from 100*theta_star/100"
            except ValueError:
                pass

    if "theta_star" in observed:
        try:
            theta_star = _as_float(observed["theta_star"])
            if "100theta_star" not in observed:
                observed["100theta_star"] = 100.0 * theta_star
                derived["100theta_star"] = "from theta_star*100"
            if "100*theta_star" not in observed:
                observed["100*theta_star"] = 100.0 * theta_star
                derived["100*theta_star"] = "from theta_star*100"
        except ValueError:
            pass

    if "rd_Mpc" in observed and "rd_m" not in observed:
        try:
            observed["rd_m"] = _as_float(observed["rd_Mpc"]) * float(MPC_SI)
            derived["rd_m"] = "from rd_Mpc*MPC_SI"
        except ValueError:
            pass

    return observed, derived


def _required_keys_for_check(check_id: str) -> tuple[str, ...]:
    if check_id == CHECK_ID_FINITE_POSITIVE_CORE:
        return CORE_POSITIVE_REQUIRED_KEYS
    if check_id == CHECK_ID_ALIAS_THETA_100:
        return ("theta_star", "100theta_star")
    if check_id == CHECK_ID_IDENTITY_LA:
        return ("theta_star", "lA")
    if check_id == CHECK_ID_IDENTITY_RD_UNITS:
        return ("rd_Mpc", "rd_m")
    return ()


def check_finite_positive(predicted: Mapping[str, Any], keys: Sequence[str]) -> list[str]:
    """Validate that selected keys are finite and strictly positive."""
    violations: list[str] = []
    for key in keys:
        if key not in predicted:
            violations.append(f"missing key '{key}'")
            continue
        try:
            value = _as_float(predicted[key])
        except ValueError as exc:
            violations.append(f"key '{key}' not numeric: {exc}")
            continue
        if not math.isfinite(value):
            violations.append(f"key '{key}' is not finite: {value!r}")
            continue
        if value <= 0.0:
            violations.append(f"key '{key}' must be > 0, got {value:.16g}")
    return violations


def check_alias_consistency(
    predicted: Mapping[str, Any],
    *,
    tol_abs: float = 1e-12,
    tol_rel: float = 1e-9,
) -> list[str]:
    """Validate alias relations such as theta_star <-> 100theta_star."""
    violations: list[str] = []
    pairs: tuple[tuple[str, str, float], ...] = (
        ("theta_star", "100theta_star", 100.0),
        ("theta_star", "100*theta_star", 100.0),
        ("100theta_star", "100*theta_star", 1.0),
    )
    for lhs_key, rhs_key, factor in pairs:
        if lhs_key not in predicted or rhs_key not in predicted:
            continue
        try:
            lhs = _as_float(predicted[lhs_key])
            rhs = _as_float(predicted[rhs_key])
        except ValueError as exc:
            violations.append(f"alias relation '{lhs_key}'/'{rhs_key}' has non-numeric value: {exc}")
            continue
        if not (math.isfinite(lhs) and math.isfinite(rhs)):
            violations.append(f"alias relation '{lhs_key}'/'{rhs_key}' requires finite values")
            continue
        expected_rhs = float(factor) * lhs
        if not _approx_equal(rhs, expected_rhs, tol_abs=tol_abs, tol_rel=tol_rel):
            violations.append(
                f"alias mismatch: {rhs_key}={rhs:.16g} but expected {expected_rhs:.16g} from {lhs_key}"
            )
    return violations


def _check_alias_theta_100(
    predicted: Mapping[str, Any],
    *,
    tol_abs: float,
    tol_rel: float,
) -> list[str]:
    lhs = {"theta_star": predicted.get("theta_star"), "100theta_star": predicted.get("100theta_star")}
    return check_alias_consistency(lhs, tol_abs=tol_abs, tol_rel=tol_rel)


def check_identity_relations(
    predicted: Mapping[str, Any],
    *,
    tol_abs: float = 1e-12,
    tol_rel: float = 1e-9,
) -> list[str]:
    """Validate algebraic identities that must hold within one prediction payload."""
    violations: list[str] = []

    if "lA" in predicted and "theta_star" in predicted:
        violations.extend(_check_identity_lA(predicted, tol_abs=tol_abs, tol_rel=tol_rel))

    if "rd_Mpc" in predicted and "rd_m" in predicted:
        violations.extend(_check_identity_rd_units(predicted, tol_abs=tol_abs, tol_rel=tol_rel))

    return violations


def _check_identity_lA(
    predicted: Mapping[str, Any],
    *,
    tol_abs: float,
    tol_rel: float,
) -> list[str]:
    violations: list[str] = []
    try:
        l_a = _as_float(predicted["lA"])
        theta_star = _as_float(predicted["theta_star"])
    except ValueError as exc:
        return [f"identity lA=pi/theta_star has non-numeric value: {exc}"]
    if not (math.isfinite(l_a) and math.isfinite(theta_star)):
        return ["identity lA=pi/theta_star requires finite lA and theta_star"]
    if theta_star <= 0.0:
        return [f"identity lA=pi/theta_star requires theta_star>0, got {theta_star:.16g}"]
    expected = math.pi / theta_star
    if not _approx_equal(l_a, expected, tol_abs=tol_abs, tol_rel=tol_rel):
        violations.append(f"identity mismatch: lA={l_a:.16g} but pi/theta_star={expected:.16g}")
    return violations


def _check_identity_rd_units(
    predicted: Mapping[str, Any],
    *,
    tol_abs: float,
    tol_rel: float,
) -> list[str]:
    violations: list[str] = []
    try:
        rd_mpc = _as_float(predicted["rd_Mpc"])
        rd_m = _as_float(predicted["rd_m"])
    except ValueError as exc:
        return [f"identity rd_m=rd_Mpc*MPC_SI has non-numeric value: {exc}"]
    if not (math.isfinite(rd_mpc) and math.isfinite(rd_m)):
        return ["identity rd_m=rd_Mpc*MPC_SI requires finite values"]
    expected = rd_mpc * float(MPC_SI)
    if not _approx_equal(rd_m, expected, tol_abs=tol_abs, tol_rel=tol_rel):
        violations.append(f"identity mismatch: rd_m={rd_m:.16g} but rd_Mpc*MPC_SI={expected:.16g}")
    return violations


def _evaluate_check(
    *,
    check_id: str,
    predicted: Mapping[str, Any],
    strict: bool,
    required_set: set[str],
    tol_abs: float,
    tol_rel: float,
) -> tuple[dict[str, Any], list[str], list[str]]:
    required_keys = list(_required_keys_for_check(check_id))
    missing_keys = [k for k in required_keys if k not in predicted]
    required = check_id in required_set

    failures: list[str] = []
    missing_required: list[str] = []
    violations: list[str] = []
    status = "PASS"
    ok = True

    if missing_keys:
        status = "SKIP"
        if strict and required:
            status = "FAIL"
            ok = False
            msg = f"required check '{check_id}' missing keys: {', '.join(missing_keys)}"
            failures.append(msg)
            missing_required.append(check_id)
    else:
        try:
            if check_id == CHECK_ID_FINITE_POSITIVE_CORE:
                violations = check_finite_positive(predicted, required_keys)
            elif check_id == CHECK_ID_ALIAS_THETA_100:
                violations = _check_alias_theta_100(predicted, tol_abs=tol_abs, tol_rel=tol_rel)
            elif check_id == CHECK_ID_IDENTITY_LA:
                violations = _check_identity_lA(predicted, tol_abs=tol_abs, tol_rel=tol_rel)
            elif check_id == CHECK_ID_IDENTITY_RD_UNITS:
                violations = _check_identity_rd_units(predicted, tol_abs=tol_abs, tol_rel=tol_rel)
            else:
                violations = [f"unknown check id '{check_id}'"]
        except Exception as exc:  # pragma: no cover - defensive
            violations = [f"check '{check_id}' raised: {exc}"]
        if violations:
            status = "FAIL"
            ok = False
            failures.extend(violations)

    payload = {
        "ok": ok,
        "status": status,
        "required": bool(required),
        "required_keys": required_keys,
        "missing_keys": missing_keys,
        "violations": list(violations),
    }
    return payload, failures, missing_required


def run_early_time_invariants(
    predicted: Mapping[str, Any],
    *,
    profile: str = "default",
    tol_abs: float = 1e-12,
    tol_rel: float = 1e-9,
    positive_keys: Sequence[str] | None = None,
    strict: bool = True,
    required_check_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run early-time invariants and return a JSON-safe, regression-friendly report."""
    if positive_keys is None:
        positive_keys = DEFAULT_POSITIVE_KEYS
    if required_check_ids is None:
        required_check_ids = DEFAULT_REQUIRED_CHECK_IDS
    required_set = {str(cid) for cid in required_check_ids}

    known_check_ids = set(DEFAULT_REQUIRED_CHECK_IDS)
    unknown_required = sorted(cid for cid in required_set if cid not in known_check_ids)

    observed, derived = _materialize_predicted_aliases(predicted)
    present_positive = [str(k) for k in positive_keys if str(k) in observed]

    checks: Dict[str, Any] = {}
    errors: list[str] = []
    missing_required: list[str] = []

    for check_id in DEFAULT_REQUIRED_CHECK_IDS:
        payload, failures, missing = _evaluate_check(
            check_id=check_id,
            predicted=observed,
            strict=bool(strict),
            required_set=required_set,
            tol_abs=float(tol_abs),
            tol_rel=float(tol_rel),
        )
        checks[check_id] = payload
        errors.extend(failures)
        missing_required.extend(missing)

    if strict and unknown_required:
        errors.append(f"unknown required check ids: {', '.join(unknown_required)}")
        missing_required.extend(unknown_required)

    optional_positive = [k for k in present_positive if k not in CORE_POSITIVE_REQUIRED_KEYS]
    if optional_positive:
        optional_violations = check_finite_positive(observed, optional_positive)
        checks["finite_positive_optional"] = {
            "ok": len(optional_violations) == 0,
            "status": "PASS" if len(optional_violations) == 0 else "FAIL",
            "required": False,
            "required_keys": list(optional_positive),
            "missing_keys": [],
            "violations": optional_violations,
        }
        if optional_violations:
            errors.extend(optional_violations)

    violations: list[str] = []
    for payload in checks.values():
        vals = payload.get("violations")
        if isinstance(vals, list):
            for v in vals:
                s = str(v)
                if s not in violations:
                    violations.append(s)
    for err in errors:
        s = str(err)
        if s not in violations:
            violations.append(s)

    report = {
        "schema_version": int(INVARIANTS_SCHEMA_VERSION),
        "ok": len(errors) == 0,
        "strict": bool(strict),
        "profile": str(profile),
        "required_check_ids": sorted(required_set),
        "missing_required": sorted(set(missing_required)),
        "errors": [str(e) for e in errors],
        "violations": list(violations),
        "checks": checks,
        "checked": {
            "positive_keys": present_positive,
            "positive_key_count": len(present_positive),
            "available_key_count": len(observed),
            "derived_keys": sorted(str(k) for k in derived.keys()),
        },
        "meta": {
            "tol_abs": float(tol_abs),
            "tol_rel": float(tol_rel),
            "available_keys": sorted(str(k) for k in observed.keys()),
            "source_key_count": len(predicted),
            "unknown_required_check_ids": unknown_required,
        },
    }
    return _json_safe(report)


__all__ = [
    "INVARIANTS_SCHEMA_VERSION",
    "CHECK_ID_FINITE_POSITIVE_CORE",
    "CHECK_ID_ALIAS_THETA_100",
    "CHECK_ID_IDENTITY_LA",
    "CHECK_ID_IDENTITY_RD_UNITS",
    "CORE_POSITIVE_REQUIRED_KEYS",
    "DEFAULT_REQUIRED_CHECK_IDS",
    "DEFAULT_POSITIVE_KEYS",
    "_as_float",
    "check_alias_consistency",
    "check_finite_positive",
    "check_identity_relations",
    "run_early_time_invariants",
]
