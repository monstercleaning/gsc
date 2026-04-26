"""BAO (Baryon Acoustic Oscillations) dataset helpers (v11.0.0).

Late-time safe design:
- Treat the sound-horizon scale r_d as a nuisance parameter (do not compute it
  from early-universe physics at v11.0.0 scope).
- Work with BAO observables expressed as distance ratios: D(z)/r_d.
- Profile r_d analytically via p = 1/r_d (chi^2 is quadratic in p).

Supported measurement block types (CSV `type` column):
- DV_over_rd
  columns: z, dv_over_rd, sigma_dv_over_rd
- DM_over_rd__DH_over_rd
  columns: z, dm_over_rd, dh_over_rd, sigma_dm_over_rd, sigma_dh_over_rd, rho_dm_dh
- VECTOR_over_rd (requires numpy)
  columns: values_path, cov_path
  - values CSV must have rows: kind,z,y  (kind in {DV,DM,DH})
  - cov is an N×N covariance for the y vector order in the values CSV

All distances D_* are computed from the effective late-time history H(z) using
the measurement-model helpers (flat case).
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from .base import Chi2Result, HzModel
from ..measurement_model import C_SI, D_M_flat
from .sn import load_covariance  # reuse robust .cov/.npz loader (numpy)


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "numpy is required for BAO covariance blocks (VECTOR_over_rd). "
            "Install it (e.g. `python3 -m pip install numpy`) or run with a venv that has numpy."
        ) from e
    return np


def D_H(*, z: float, model: HzModel, c: float = C_SI) -> float:
    """Hubble distance D_H = c/H(z) in meters."""
    Hz = float(model.H(z))
    if Hz <= 0:
        raise ValueError("H(z) must be positive")
    return c / Hz


def D_V_flat(*, z: float, model: HzModel, n: int = 10_000, c: float = C_SI) -> float:
    """Volume distance D_V in meters (flat), using D_V = (z D_H D_M^2)^(1/3)."""
    if z < 0:
        raise ValueError("Require z >= 0")
    dm = D_M_flat(z=z, H_of_z=model.H, c=c, n=n)
    dh = D_H(z=z, model=model, c=c)
    return (z * dh * dm * dm) ** (1.0 / 3.0)


@dataclass(frozen=True)
class BAOBlock1D:
    """A single isotropic BAO constraint (1D)."""

    z: float
    y: float
    sigma: float
    kind: str = "DV_over_rd"
    label: str = ""

    def abc(self, model: HzModel, *, n: int) -> tuple[float, float, float]:
        if self.sigma <= 0:
            raise ValueError("sigma must be positive")
        if self.kind != "DV_over_rd":
            raise ValueError(f"Unsupported 1D BAO kind: {self.kind}")

        d = D_V_flat(z=self.z, model=model, n=n)
        w = 1.0 / (self.sigma * self.sigma)
        # chi2(p) = (p*d - y)^2 / sigma^2 = A p^2 - 2 B p + C
        A = (d * d) * w
        B = (d * self.y) * w
        C = (self.y * self.y) * w
        return (A, B, C)


@dataclass(frozen=True)
class BAOBlock2D:
    """An anisotropic BAO constraint (2D): (D_M/r_d, D_H/r_d)."""

    z: float
    y_dm: float
    y_dh: float
    sigma_dm: float
    sigma_dh: float
    rho_dm_dh: float
    kind: str = "DM_over_rd__DH_over_rd"
    label: str = ""

    def abc(self, model: HzModel, *, n: int) -> tuple[float, float, float]:
        if self.kind != "DM_over_rd__DH_over_rd":
            raise ValueError(f"Unsupported 2D BAO kind: {self.kind}")
        if self.sigma_dm <= 0 or self.sigma_dh <= 0:
            raise ValueError("sigma values must be positive")
        if not (-1.0 < self.rho_dm_dh < 1.0):
            raise ValueError("Require -1 < rho < 1 for covariance to be invertible")

        dm = D_M_flat(z=self.z, H_of_z=model.H, n=n)
        dh = D_H(z=self.z, model=model)

        # Covariance:
        #   C = [[a, b],
        #        [b, c]]
        a = self.sigma_dm * self.sigma_dm
        c = self.sigma_dh * self.sigma_dh
        b = self.rho_dm_dh * self.sigma_dm * self.sigma_dh
        det = a * c - b * b
        if det <= 0:
            raise ValueError("2x2 covariance must be positive definite (det>0)")

        # C^{-1} = (1/det) [[c, -b], [-b, a]]
        inv00 = c / det
        inv01 = -b / det
        inv11 = a / det

        # d^T C^{-1} d
        A = dm * (inv00 * dm + inv01 * dh) + dh * (inv01 * dm + inv11 * dh)
        # d^T C^{-1} y
        B = dm * (inv00 * self.y_dm + inv01 * self.y_dh) + dh * (inv01 * self.y_dm + inv11 * self.y_dh)
        # y^T C^{-1} y
        C = self.y_dm * (inv00 * self.y_dm + inv01 * self.y_dh) + self.y_dh * (inv01 * self.y_dm + inv11 * self.y_dh)
        return (A, B, C)


@dataclass(frozen=True)
class BAOBlockND:
    """A multi-observable BAO constraint with a full covariance on y=D/rd.

    This is used for small published BAO covariances (e.g. BOSS DR12 consensus).
    For large N, prefer a dedicated likelihood library.
    """

    kinds: Tuple[str, ...]
    zs: Tuple[float, ...]
    y: Tuple[float, ...]
    cov: Any
    kind: str = "VECTOR_over_rd"
    label: str = ""

    def abc(self, model: HzModel, *, n: int) -> tuple[float, float, float]:
        if not (len(self.kinds) == len(self.zs) == len(self.y)):
            raise ValueError("kinds/zs/y length mismatch for BAOBlockND")
        if len(self.y) == 0:
            raise ValueError("Empty BAOBlockND")

        np = _require_numpy()
        cov = self.cov
        if not hasattr(cov, "shape"):
            cov = np.asarray(cov, dtype=float)
        nobs = len(self.y)
        if cov.shape != (nobs, nobs):
            raise ValueError(f"Covariance shape mismatch: got {cov.shape}, expected {(nobs, nobs)}")

        diag = np.diag(cov)
        if not (np.isfinite(diag).all() and float(diag.min()) > 0.0):
            raise ValueError("BAO covariance diagonal must be finite and strictly positive")
        max_abs = float(np.max(np.abs(cov)))
        if max_abs > 0:
            max_diff = float(np.max(np.abs(cov - cov.T)))
            if max_diff > (1e-12 * max_abs + 1e-15):
                raise ValueError("BAO covariance is not symmetric enough")

        d_list: list[float] = []
        for k, z in zip(self.kinds, self.zs):
            kk = str(k).strip().upper()
            if kk == "DV":
                d_list.append(float(D_V_flat(z=float(z), model=model, n=n)))
            elif kk == "DM":
                d_list.append(float(D_M_flat(z=float(z), H_of_z=model.H, n=n)))
            elif kk == "DH":
                d_list.append(float(D_H(z=float(z), model=model)))
            else:
                raise ValueError(f"Unknown BAO kind in BAOBlockND: {k!r}")

        d = np.asarray(d_list, dtype=float)
        y = np.asarray(self.y, dtype=float)

        L = np.linalg.cholesky(cov)

        def solve_cov(b):
            t = np.linalg.solve(L, b)
            return np.linalg.solve(L.T, t)

        v_d = solve_cov(d)  # C^{-1} d
        v_y = solve_cov(y)  # C^{-1} y
        A = float(np.dot(d, v_d))
        B = float(np.dot(d, v_y))
        C = float(np.dot(y, v_y))
        return (A, B, C)


BAOBlock = Union[BAOBlock1D, BAOBlock2D, BAOBlockND]


@dataclass(frozen=True)
class BAODataset:
    name: str
    blocks: Tuple[BAOBlock, ...]

    @classmethod
    def from_csv(cls, path: Union[str, Path], *, name: Optional[str] = None) -> "BAODataset":
        p = Path(path)
        if name is None:
            name = p.stem

        blocks: List[BAOBlock] = []
        with p.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"Missing CSV header: {p}")
            if "type" not in reader.fieldnames:
                raise ValueError(f"Missing required column 'type' in {p}")
            for row in reader:
                if not row:
                    continue
                t = (row.get("type") or "").strip()
                if not t:
                    continue
                label = (row.get("label") or row.get("survey") or "").strip()
                if t == "DV_over_rd":
                    z = float((row.get("z") or "").strip())
                    y = float((row.get("dv_over_rd") or "").strip())
                    sig = float((row.get("sigma_dv_over_rd") or "").strip())
                    blocks.append(BAOBlock1D(z=z, y=y, sigma=sig, kind=t, label=label))
                elif t == "DM_over_rd__DH_over_rd":
                    z = float((row.get("z") or "").strip())
                    y_dm = float((row.get("dm_over_rd") or "").strip())
                    y_dh = float((row.get("dh_over_rd") or "").strip())
                    sig_dm = float((row.get("sigma_dm_over_rd") or "").strip())
                    sig_dh = float((row.get("sigma_dh_over_rd") or "").strip())
                    rho = float((row.get("rho_dm_dh") or "").strip())
                    blocks.append(
                        BAOBlock2D(
                            z=z,
                            y_dm=y_dm,
                            y_dh=y_dh,
                            sigma_dm=sig_dm,
                            sigma_dh=sig_dh,
                            rho_dm_dh=rho,
                            kind=t,
                            label=label,
                        )
                    )
                elif t == "VECTOR_over_rd":
                    values_rel = (row.get("values_path") or "").strip()
                    cov_rel = (row.get("cov_path") or "").strip()
                    if not values_rel or not cov_rel:
                        raise ValueError(f"VECTOR_over_rd requires values_path and cov_path columns in {p}")
                    values_p = (p.parent / values_rel).resolve()
                    cov_p = (p.parent / cov_rel).resolve()

                    kinds: list[str] = []
                    zs: list[float] = []
                    ys: list[float] = []
                    with values_p.open("r", newline="", encoding="utf-8") as vf:
                        vreader = csv.DictReader(vf)
                        if vreader.fieldnames is None:
                            raise ValueError(f"Missing CSV header: {values_p}")
                        need = ("kind", "z", "y")
                        missing = [c for c in need if c not in vreader.fieldnames]
                        if missing:
                            raise ValueError(f"Missing columns {missing} in {values_p}; available={vreader.fieldnames}")
                        for vrow in vreader:
                            if not vrow:
                                continue
                            k_s = (vrow.get("kind") or "").strip()
                            z_s = (vrow.get("z") or "").strip()
                            y_s = (vrow.get("y") or "").strip()
                            if not (k_s and z_s and y_s):
                                continue
                            kinds.append(k_s)
                            zs.append(float(z_s))
                            ys.append(float(y_s))

                    if not ys:
                        raise ValueError(f"No VECTOR_over_rd values loaded from {values_p}")
                    cov = load_covariance(cov_p, n=len(ys), cache_npz=True)
                    blocks.append(BAOBlockND(kinds=tuple(kinds), zs=tuple(zs), y=tuple(ys), cov=cov, label=label))
                else:
                    raise ValueError(f"Unknown BAO block type '{t}' in {p}")

        if not blocks:
            raise ValueError(f"No BAO blocks loaded from {p}")
        return cls(name=name, blocks=tuple(blocks))

    def chi2(
        self,
        model: HzModel,
        *,
        fit_rd: bool = True,
        rd_m: Optional[float] = None,
        n: int = 10_000,
    ) -> Chi2Result:
        """Return chi^2 with analytic profiling over r_d (default).

        If rd_m is provided, it is treated as fixed (fit_rd is ignored).
        """
        if not self.blocks:
            raise ValueError("Empty BAO dataset")

        A = 0.0
        B = 0.0
        C = 0.0
        n_obs = 0

        for b in self.blocks:
            a_i, b_i, c_i = b.abc(model, n=n)
            A += float(a_i)
            B += float(b_i)
            C += float(c_i)
            if isinstance(b, BAOBlock1D):
                n_obs += 1
            elif isinstance(b, BAOBlock2D):
                n_obs += 2
            else:
                n_obs += len(getattr(b, "y", ()))

        if A <= 0:
            raise ValueError("Invalid BAO design matrix: A <= 0")

        method = "profile_rd"
        params: Dict[str, float] = {}
        if rd_m is not None:
            if rd_m <= 0:
                raise ValueError("rd_m must be positive")
            p = 1.0 / rd_m
            chi2 = A * p * p - 2.0 * B * p + C
            ndof = n_obs
            method = "fixed_rd"
            params["rd_m"] = float(rd_m)
            params["p_star"] = float(p)
        else:
            if not fit_rd:
                raise ValueError("fit_rd=False requires rd_m to be provided")
            p_star = B / A
            if p_star <= 0:
                raise ValueError("Profiled p_star <= 0 (implies non-physical r_d)")
            chi2 = C - (B * B) / A
            rd_star = 1.0 / p_star
            ndof = n_obs - 1
            params["rd_m"] = float(rd_star)
            params["p_star"] = float(p_star)

        if not math.isfinite(chi2):
            raise ValueError("Non-finite BAO chi2")

        return Chi2Result(
            chi2=float(chi2),
            ndof=int(ndof),
            params=params,
            meta={"method": method, "n_obs": n_obs},
        )


@dataclass(frozen=True)
class BAODatasetFixedRd:
    """Adapter that makes a BAODataset compatible with chi2_total() with fixed r_d."""

    base: BAODataset
    rd_m: float
    name: str = "bao"

    def chi2(self, model: HzModel) -> Chi2Result:
        return self.base.chi2(model, rd_m=self.rd_m)
