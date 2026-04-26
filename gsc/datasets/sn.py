"""Supernova (SN Ia) late-time dataset helpers (v11.0.0).

This module supports a minimal "mu(z)" dataset:
  columns: z, mu, sigma_mu

Two modes are supported:
- diagonal errors (stdlib-only) for smoke tests
- full covariance (STAT+SYS) using numpy for publication-ready chi^2

We fit a single additive nuisance parameter (delta_M) analytically:
  mu_obs = mu_theory(z) + delta_M + noise
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from .base import Chi2Result, HzModel
from ..measurement_model import distance_modulus_flat


def load_sn_mu_csv(
    path: Union[str, Path],
    *,
    z_col: str = "z",
    mu_col: str = "mu",
    sigma_col: str = "sigma_mu",
    row_col: str = "row_full",
    is_calibrator_col: str = "is_calibrator",
) -> tuple[Tuple[float, ...], Tuple[float, ...], Tuple[float, ...], Dict[str, Any]]:
    """Load a minimal SN mu(z) CSV (stdlib-only)."""
    p = Path(path)
    zs: list[float] = []
    mus: list[float] = []
    sigs: list[float] = []
    row_full: list[int] = []
    is_calibrator: list[int] = []

    with p.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Missing CSV header: {p}")
        missing = [c for c in (z_col, mu_col, sigma_col) if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing columns {missing} in {p}; available={reader.fieldnames}")
        has_row = row_col in reader.fieldnames
        has_cal = is_calibrator_col in reader.fieldnames
        for row in reader:
            if not row:
                continue
            z_s = (row.get(z_col) or "").strip()
            if not z_s:
                continue
            if has_row:
                row_full.append(int(float((row.get(row_col) or "").strip())))
            if has_cal:
                is_calibrator.append(int(float((row.get(is_calibrator_col) or "").strip())))
            zs.append(float(z_s))
            mus.append(float((row.get(mu_col) or "").strip()))
            sigs.append(float((row.get(sigma_col) or "").strip()))

    meta: Dict[str, Any] = {
        "path": str(p),
        "columns": {"z": z_col, "mu": mu_col, "sigma_mu": sigma_col},
        "n": len(zs),
    }
    if has_row:
        if len(row_full) != len(zs):
            raise ValueError("row_full length mismatch")
        meta["row_full"] = tuple(row_full)
        meta["columns"]["row_full"] = row_col
    if has_cal:
        if len(is_calibrator) != len(zs):
            raise ValueError("is_calibrator length mismatch")
        meta["is_calibrator"] = tuple(is_calibrator)
        meta["columns"]["is_calibrator"] = is_calibrator_col
    return (tuple(zs), tuple(mus), tuple(sigs), meta)


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "numpy is required for SN covariance mode. "
            "Install it (e.g. `python3 -m pip install numpy`) or run with a venv that has numpy."
        ) from e
    return np


def _infer_cov_n(path: Union[str, Path], *, min_required: int) -> Optional[int]:
    """Best-effort inference of the full covariance dimension N.

    This is used when a CSV contains `row_full` indices for a subset. In that
    case we want to load the *full* covariance (N_full x N_full) and slice it.

    Preference order:
    1) cached `.npz` next to the `.cov` (fast; provides exact shape)
    2) `.npz` file itself (shape)
    3) leading integer token in the ASCII file (common convention)
    """
    if min_required <= 0:
        raise ValueError("min_required must be positive")

    p = Path(path)

    npz_path = p if p.suffix.lower() == ".npz" else Path(str(p) + ".npz")
    if npz_path.exists():
        try:
            np = _require_numpy()
            data = np.load(npz_path)
            cov = data["cov"] if "cov" in data.files else data[data.files[0]]
            n = int(cov.shape[0])
            if n >= min_required:
                return n
        except Exception:
            # Fall back to parsing the ASCII file.
            pass

    if not p.exists():
        return None

    # Read first non-empty, non-comment token.
    try:
        with p.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                tok = s.split()[0]
                v = float(tok)
                n = int(v)
                if n == v and n >= max(10, min_required):
                    return n
                break
    except OSError:
        return None

    return None


def load_covariance(
    path: Union[str, Path],
    *,
    n: int,
    cache_npz: bool = True,
) -> Any:
    """Load a covariance matrix in either ASCII .cov or cached .npz format.

    Supported numeric layouts (after stripping optional leading N):
    - N*N values: full matrix row-major
    - N(N+1)/2 values: lower-triangular (symmetric is reconstructed)
    """
    if n <= 0:
        raise ValueError("n must be positive")
    np = _require_numpy()
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Missing covariance file: {p}")

    if p.suffix.lower() == ".npz":
        data = np.load(p)
        if "cov" in data.files:
            cov = data["cov"]
        else:
            if not data.files:
                raise ValueError(f"Empty npz: {p}")
            cov = data[data.files[0]]
        if cov.shape != (n, n):
            raise ValueError(f"Covariance shape mismatch: got {cov.shape}, expected {(n, n)}")
        return cov

    # If a cache exists, prefer it (fast path).
    npz_path = Path(str(p) + ".npz")
    if cache_npz and npz_path.exists():
        data = np.load(npz_path)
        if "cov" in data.files:
            cov = data["cov"]
        else:
            if not data.files:
                raise ValueError(f"Empty npz: {npz_path}")
            cov = data[data.files[0]]
        if cov.shape != (n, n):
            raise ValueError(f"Covariance shape mismatch: got {cov.shape}, expected {(n, n)}")
        return cov

    vals: list[float] = []
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue
            for tok in s.split():
                try:
                    vals.append(float(tok))
                except ValueError as e:
                    raise ValueError(f"Non-numeric token in covariance file {p}: {tok!r}") from e

    if not vals:
        raise ValueError(f"Empty covariance file: {p}")

    # Optional leading N convention.
    if int(vals[0]) == n:
        # Only strip if the remaining count matches a supported layout.
        rest = vals[1:]
        if len(rest) in (n * n, n * (n + 1) // 2):
            vals = rest

    n2 = n * n
    ntri = n * (n + 1) // 2

    if len(vals) == n2:
        cov = np.array(vals, dtype=float).reshape((n, n))
    elif len(vals) == ntri:
        cov = np.zeros((n, n), dtype=float)
        k = 0
        for i in range(n):
            for j in range(i + 1):
                v = float(vals[k])
                cov[i, j] = v
                cov[j, i] = v
                k += 1
    else:
        raise ValueError(
            f"Unsupported covariance layout in {p}: got {len(vals)} numbers; "
            f"expected {n2} (N*N) or {ntri} (N(N+1)/2), optionally with a leading N."
        )

    if cache_npz:
        try:
            np.savez_compressed(npz_path, cov=cov)
        except OSError:
            # Cache is best-effort; ignore filesystem failures.
            pass

    return cov


@dataclass(frozen=True)
class SNDataset:
    """SN dataset supporting either diagonal or covariance chi^2."""

    name: str
    z: Tuple[float, ...]
    mu: Tuple[float, ...]
    sigma_mu: Tuple[float, ...]
    cov: Optional[Any] = None
    cov_path: Optional[str] = None

    @classmethod
    def from_csv(
        cls,
        path: Union[str, Path],
        *,
        name: Optional[str] = None,
    ) -> "SNDataset":
        p = Path(path)
        if name is None:
            name = p.stem
        z, mu, sigma_mu, _meta = load_sn_mu_csv(p)
        return cls(name=name, z=z, mu=mu, sigma_mu=sigma_mu)

    @classmethod
    def from_csv_and_cov(
        cls,
        csv_path: Union[str, Path],
        cov_path: Union[str, Path],
        *,
        name: Optional[str] = None,
        cache_npz: bool = True,
    ) -> "SNDataset":
        csv_p = Path(csv_path)
        if name is None:
            name = csv_p.stem
        z, mu, sigma_mu_csv, meta = load_sn_mu_csv(csv_p)
        row_full = meta.get("row_full")

        np = _require_numpy()
        cov_path_str = str(cov_path)
        if row_full is not None:
            idx = np.asarray(row_full, dtype=int)
            if idx.ndim != 1:
                raise ValueError("row_full must be a 1D index list")
            if len(idx) != len(z):
                raise ValueError("row_full length mismatch")
            if len(np.unique(idx)) != len(idx):
                raise ValueError("row_full must be unique (no duplicates)")
            if int(idx.min()) < 0:
                raise ValueError("row_full must be non-negative")
            min_required = int(idx.max()) + 1
            n_full = _infer_cov_n(cov_path, min_required=min_required) or min_required
            if int(idx.max()) >= n_full:
                raise ValueError("row_full indices exceed covariance dimension")
            cov_full = load_covariance(cov_path, n=n_full, cache_npz=cache_npz)
            cov = cov_full[np.ix_(idx, idx)]
            cov_path_str = f"{cov_path_str} (subset via row_full; n_full={n_full})"
        else:
            cov = load_covariance(cov_path, n=len(z), cache_npz=cache_npz)

        # Guardrails: basic sanity checks to prevent silent mismatches.
        diag = np.diag(cov)
        if not (np.isfinite(diag).all() and float(diag.min()) > 0.0):
            raise ValueError("Covariance diagonal must be finite and strictly positive")
        # Symmetry (relative).
        max_abs = float(np.max(np.abs(cov)))
        if max_abs > 0:
            max_diff = float(np.max(np.abs(cov - cov.T)))
            # Some releases print both triangles with limited precision; allow
            # tiny asymmetries at the 1e-7 relative level.
            if max_diff > (1e-7 * max_abs + 1e-12):
                rel = max_diff / max_abs
                raise ValueError(f"Covariance is not symmetric enough (rel={rel:g}, max_diff={max_diff:g})")

        # In STAT+SYS mode, ignore CSV sigma for chi^2; keep sigma from diag(C).
        sigma_mu_cov = tuple(float(x) for x in np.sqrt(diag))
        return cls(
            name=name,
            z=z,
            mu=mu,
            sigma_mu=sigma_mu_cov,
            cov=cov,
            cov_path=cov_path_str,
        )

    def chi2(self, model: HzModel, *, fit_delta_M: bool = True, n: int = 2000) -> Chi2Result:
        if not (len(self.z) == len(self.mu) == len(self.sigma_mu)):
            raise ValueError("z/mu/sigma_mu length mismatch")
        if len(self.z) == 0:
            raise ValueError("Empty SN dataset")

        mu_th = [distance_modulus_flat(z=z, H_of_z=model.H, n=n) for z in self.z]
        r0_list = [mu_obs - mu_pred for (mu_obs, mu_pred) in zip(self.mu, mu_th)]
        npts = len(r0_list)

        if self.cov is not None:
            np = _require_numpy()
            cov = self.cov
            if not hasattr(cov, "shape"):
                cov = np.asarray(cov, dtype=float)
            if cov.shape != (npts, npts):
                raise ValueError(f"Covariance shape mismatch: got {cov.shape}, expected {(npts, npts)}")

            r0 = np.asarray(r0_list, dtype=float)
            ones = np.ones(npts, dtype=float)

            # Use Cholesky for speed/stability: C = L L^T.
            L = np.linalg.cholesky(cov)

            def solve_cov(b):
                y = np.linalg.solve(L, b)
                return np.linalg.solve(L.T, y)

            x = solve_cov(r0)  # C^{-1} r0
            # Some BLAS builds can leak FP exception flags into later ufuncs,
            # producing spurious RuntimeWarnings for matmul/dot. We suppress
            # warnings here and validate finiteness explicitly.
            with np.errstate(all="ignore"):
                chi2_0 = float(np.dot(r0, x))
            if not math.isfinite(chi2_0):
                raise ValueError("Non-finite chi2 in covariance mode")

            if fit_delta_M:
                y = solve_cov(ones)  # C^{-1} 1
                with np.errstate(all="ignore"):
                    a = float(np.dot(ones, x))  # 1^T C^{-1} r0
                    b = float(np.dot(ones, y))  # 1^T C^{-1} 1
                if not (math.isfinite(a) and math.isfinite(b)):
                    raise ValueError("Non-finite nuisance projections in covariance mode")
                if b <= 0:
                    raise ValueError("Invalid covariance projection (1^T C^{-1} 1 <= 0)")
                delta_M = a / b
                chi2 = chi2_0 - (a * a) / b
                ndof = npts - 1
            else:
                delta_M = 0.0
                chi2 = chi2_0
                ndof = npts

            if not math.isfinite(chi2):
                raise ValueError("Non-finite chi2 in covariance mode")

            return Chi2Result(
                chi2=float(chi2),
                ndof=int(ndof),
                params={"delta_M": float(delta_M)},
                meta={"method": "cov", "cov_path": self.cov_path},
            )

        # Diagonal chi^2 mode.
        delta_M = 0.0
        ndof = npts
        if fit_delta_M:
            w_sum = 0.0
            w_res_sum = 0.0
            for r0, sig in zip(r0_list, self.sigma_mu):
                if sig <= 0:
                    raise ValueError("sigma_mu must be positive")
                w = 1.0 / (sig * sig)
                w_sum += w
                w_res_sum += w * r0
            if w_sum <= 0:
                raise ValueError("Invalid weights (all zero?)")
            delta_M = w_res_sum / w_sum
            ndof -= 1

        chi2 = 0.0
        for r0, sig in zip(r0_list, self.sigma_mu):
            r = (r0 - delta_M) / sig
            chi2 += r * r

        return Chi2Result(
            chi2=float(chi2),
            ndof=int(ndof),
            params={"delta_M": float(delta_M)},
            meta={"method": "diag"},
        )


# Backwards-compatible alias (diag-only name used by earlier harness code).
SNMuDataset = SNDataset
