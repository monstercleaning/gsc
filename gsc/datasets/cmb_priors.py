"""Compressed-CMB prior helpers (E1 bridge, v11.0.0).

Supported in this module:
- scalar/vector prior loading from CSV (`name,value,sigma`)
- optional full covariance (`.cov`/`.npz`)
- deterministic chi2 evaluation against model-predicted values
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Dict, Optional, Tuple

from .base import Chi2Result


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "numpy is required for CMB prior covariance mode. "
            "Install numpy or run with a venv that has numpy."
        ) from e
    return np


@dataclass(frozen=True)
class CMBScalarPrior:
    """A scalar Gaussian prior."""

    name: str
    value: float
    sigma: float
    # Optional "theory error" term (absolute) added in quadrature.
    # This is useful when using approximate bridge predictors (E1) with
    # extremely tight observational priors (e.g. Planck theta*).
    sigma_theory: float = 0.0
    label: str = ""


def load_cmb_priors_csv(path: Path | str) -> Tuple[CMBScalarPrior, ...]:
    """Load scalar compressed-CMB priors from CSV.

    Required columns:
    - `name`
    - `value`
    - `sigma`

    Optional:
    - `label`
    """
    p = Path(path)
    priors = []
    with p.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Missing CSV header: {p}")
        required = ("name", "value", "sigma")
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing required columns {missing} in {p}")

        for row in reader:
            if not row:
                continue
            name = (row.get("name") or "").strip()
            if not name or name.startswith("#"):
                continue
            try:
                value = float((row.get("value") or "").strip())
                sigma = float((row.get("sigma") or "").strip())
                # Accept either `sigma_theory` (canonical) or `sigma_th` (alias).
                sigma_theory_raw = (row.get("sigma_theory") or row.get("sigma_th") or "").strip()
                sigma_theory = float(sigma_theory_raw) if sigma_theory_raw else 0.0
            except Exception as e:
                raise ValueError(f"Invalid value/sigma in {p} for prior {name!r}") from e
            if sigma <= 0.0:
                raise ValueError(f"sigma must be > 0 for prior {name!r} in {p}")
            if sigma_theory < 0.0:
                raise ValueError(f"sigma_theory must be >= 0 for prior {name!r} in {p}")
            label = (row.get("label") or "").strip()
            priors.append(
                CMBScalarPrior(
                    name=name,
                    value=value,
                    sigma=sigma,
                    sigma_theory=sigma_theory,
                    label=label,
                )
            )

    if not priors:
        raise ValueError(f"No CMB priors loaded from {p}")
    return tuple(priors)


def load_cmb_covariance(path: Path | str, *, n: int):
    """Load an optional covariance matrix for vector priors.

    Reuses the robust `.cov`/`.npz` parser used by SN/BAO datasets.
    """
    from .sn import load_covariance

    return load_covariance(path, n=n, cache_npz=True)


@dataclass(frozen=True)
class CMBPriorsDataset:
    """Compressed-CMB priors as a Gaussian likelihood block."""

    name: str
    priors: Tuple[CMBScalarPrior, ...]
    cov: Optional[object] = None

    @property
    def keys(self) -> Tuple[str, ...]:
        return tuple(p.name for p in self.priors)

    @property
    def values(self) -> Tuple[float, ...]:
        return tuple(float(p.value) for p in self.priors)

    @property
    def sigmas(self) -> Tuple[float, ...]:
        return tuple(float(p.sigma) for p in self.priors)

    @property
    def sigmas_theory(self) -> Tuple[float, ...]:
        return tuple(float(p.sigma_theory) for p in self.priors)

    @classmethod
    def from_csv(
        cls,
        path: Path | str,
        *,
        cov_path: Optional[Path | str] = None,
        name: Optional[str] = None,
    ) -> "CMBPriorsDataset":
        p = Path(path)
        priors = load_cmb_priors_csv(p)
        if name is None:
            name = p.stem
        cov = None
        if cov_path is not None:
            cov = load_cmb_covariance(cov_path, n=len(priors))
        return cls(name=name, priors=priors, cov=cov)

    def chi2_from_values(self, predicted: Dict[str, float]) -> Chi2Result:
        """Evaluate chi2 for a dictionary of model-predicted prior values."""
        keys = self.keys
        obs = self.values
        sig = self.sigmas
        sig_th = self.sigmas_theory

        missing = [k for k in keys if k not in predicted]
        if missing:
            raise ValueError(f"Missing predicted CMB prior values for keys: {missing}")

        if self.cov is None:
            import math

            chi2 = 0.0
            for k, y, s, sth in zip(keys, obs, sig, sig_th):
                sigma_eff = math.sqrt(float(s) * float(s) + float(sth) * float(sth))
                if sigma_eff <= 0.0:
                    raise ValueError(f"Non-positive sigma for prior {k!r}")
                r = (float(predicted[k]) - float(y)) / sigma_eff
                chi2 += r * r
            return Chi2Result(
                chi2=float(chi2),
                ndof=len(keys),
                params={},
                meta={"method": "diag", "keys": list(keys)},
            )

        np = _require_numpy()
        cov = self.cov
        if not hasattr(cov, "shape"):
            cov = np.asarray(cov, dtype=float)
        # Add optional theory-error terms to the diagonal, assuming independent
        # theory uncertainty per prior element.
        if any(float(sth) > 0.0 for sth in sig_th):
            add = np.diag(np.asarray([float(sth) ** 2 for sth in sig_th], dtype=float))
            cov = cov + add
        y = np.asarray(obs, dtype=float)
        y_pred = np.asarray([float(predicted[k]) for k in keys], dtype=float)
        r = y_pred - y

        if cov.shape != (len(keys), len(keys)):
            raise ValueError(f"CMB covariance shape mismatch: got {cov.shape}, expected {(len(keys), len(keys))}")

        diag = np.diag(cov)
        if not (np.isfinite(diag).all() and float(diag.min()) > 0.0):
            raise ValueError("CMB covariance diagonal must be finite and strictly positive")
        max_abs = float(np.max(np.abs(cov)))
        if max_abs > 0:
            max_diff = float(np.max(np.abs(cov - cov.T)))
            if max_diff > (1e-12 * max_abs + 1e-15):
                raise ValueError("CMB covariance is not symmetric enough")

        L = np.linalg.cholesky(cov)
        u = np.linalg.solve(L, r)
        chi2 = float(u @ u)
        return Chi2Result(
            chi2=chi2,
            ndof=len(keys),
            params={},
            meta={"method": "cov", "keys": list(keys)},
        )
