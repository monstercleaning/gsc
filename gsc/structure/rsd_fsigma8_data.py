"""RSD f*sigma8 dataset utilities (stdlib-only, deterministic)."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


def _finite_float(value: object, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise ValueError(f"{name} must be a finite float")
    return float(out)


def load_fsigma8_csv(path: str) -> List[Dict[str, object]]:
    """Load RSD f*sigma8 CSV with deterministic row order.

    Expected columns:
      z,fsigma8,sigma,omega_m_ref,ref_key
    """
    src = Path(path).expanduser().resolve()
    try:
        raw_lines = src.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"failed to read CSV: {exc}") from exc

    filtered: List[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        filtered.append(line)

    if not filtered:
        raise ValueError("dataset has no usable rows")

    reader = csv.DictReader(filtered)
    if reader.fieldnames is None:
        raise ValueError("CSV is missing header")

    required = {"z", "fsigma8", "sigma", "omega_m_ref", "ref_key"}
    got = {str(name).strip() for name in reader.fieldnames}
    missing = sorted(required - got)
    if missing:
        raise ValueError("CSV missing required columns: " + ",".join(missing))

    out: List[Dict[str, object]] = []
    for idx, row in enumerate(reader, start=2):
        z = _finite_float(row.get("z"), name=f"z (row {idx})")
        fs8 = _finite_float(row.get("fsigma8"), name=f"fsigma8 (row {idx})")
        sigma = _finite_float(row.get("sigma"), name=f"sigma (row {idx})")
        om_ref = _finite_float(row.get("omega_m_ref"), name=f"omega_m_ref (row {idx})")
        ref_key = str(row.get("ref_key") or "").strip()

        if z <= 0.0:
            raise ValueError(f"z (row {idx}) must be > 0")
        if sigma <= 0.0:
            raise ValueError(f"sigma (row {idx}) must be > 0")
        if not (0.0 <= om_ref <= 1.0):
            raise ValueError(f"omega_m_ref (row {idx}) must satisfy 0 <= omega_m_ref <= 1")
        if not ref_key:
            raise ValueError(f"ref_key (row {idx}) must be non-empty")

        out.append(
            {
                "z": float(z),
                "fsigma8": float(fs8),
                "sigma": float(sigma),
                "omega_m_ref": float(om_ref),
                "ref_key": ref_key,
            }
        )

    if not out:
        raise ValueError("dataset has no usable points")
    return out


def diag_weights(data: Iterable[Dict[str, object]]) -> List[float]:
    """Return diagonal weights 1/sigma^2 for each record."""
    out: List[float] = []
    for idx, row in enumerate(data):
        sigma = _finite_float(row.get("sigma"), name=f"sigma[{idx}]")
        if sigma <= 0.0:
            raise ValueError(f"sigma[{idx}] must be > 0")
        out.append(float(1.0 / (sigma * sigma)))
    return out


def chi2_diag(residuals: Sequence[float], sigmas: Sequence[float]) -> float:
    """Return chi2 = sum((r_i/sigma_i)^2) for diagonal covariance."""
    if len(residuals) != len(sigmas):
        raise ValueError("residuals and sigmas must have same length")
    total = 0.0
    for idx, (res, sigma) in enumerate(zip(residuals, sigmas)):
        rr = _finite_float(res, name=f"residual[{idx}]")
        ss = _finite_float(sigma, name=f"sigma[{idx}]")
        if ss <= 0.0:
            raise ValueError(f"sigma[{idx}] must be > 0")
        pull = rr / ss
        total += pull * pull
    if not math.isfinite(total):
        raise ValueError("non-finite chi2")
    return float(total)


def profile_scale_chi2_diag(
    data_y: Sequence[float],
    model_t: Sequence[float],
    sigmas: Sequence[float],
) -> Dict[str, Optional[float]]:
    """Profile scalar amplitude s in model y = s * t for diagonal covariance."""
    if not (len(data_y) == len(model_t) == len(sigmas)):
        raise ValueError("data_y, model_t and sigmas must have same length")

    a_num = 0.0
    b_den = 0.0
    for idx, (yy, tt, ss) in enumerate(zip(data_y, model_t, sigmas)):
        y = _finite_float(yy, name=f"data_y[{idx}]")
        t = _finite_float(tt, name=f"model_t[{idx}]")
        sigma = _finite_float(ss, name=f"sigma[{idx}]")
        if sigma <= 0.0:
            raise ValueError(f"sigma[{idx}] must be > 0")
        w = 1.0 / (sigma * sigma)
        a_num += t * y * w
        b_den += t * t * w

    if not math.isfinite(a_num) or not math.isfinite(b_den):
        raise ValueError("non-finite profile coefficients")

    if b_den <= 0.0:
        return {
            "scale_bestfit": None,
            "chi2_min": None,
            "a_num": float(a_num),
            "b_den": float(b_den),
        }

    scale = float(a_num / b_den)
    residuals = [float(y - scale * t) for y, t in zip(data_y, model_t)]
    chi2 = chi2_diag(residuals, sigmas)
    return {
        "scale_bestfit": float(scale),
        "chi2_min": float(chi2),
        "a_num": float(a_num),
        "b_den": float(b_den),
    }

