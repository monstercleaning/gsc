"""Redshift drift (Sandage–Loeb) dataset helpers (v11.0.0).

We represent measurements in terms of spectroscopic velocity drift:
  Δv = c * Δz / (1+z)

Units here:
  dv_cm_s = Δv in cm/s accumulated over `baseline_years` years.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Optional, Tuple, Union

from .base import Chi2Result, HzModel
from ..measurement_model import delta_v_cm_s


@dataclass(frozen=True)
class DriftDataset:
    name: str
    z: Tuple[float, ...]
    dv_cm_s: Tuple[float, ...]
    sigma_dv_cm_s: Tuple[float, ...]
    baseline_years: float
    baseline_years_by_row: Optional[Tuple[float, ...]] = None

    @classmethod
    def from_csv(
        cls,
        path: Union[str, Path],
        *,
        baseline_years: Optional[float] = None,
        name: Optional[str] = None,
        z_col: str = "z",
        dv_col: str = "dv_cm_s",
        sigma_col: str = "sigma_dv_cm_s",
        baseline_col: str = "baseline_years",
        baseline_alt_col: str = "baseline_yr",
    ) -> "DriftDataset":
        if baseline_years is not None and baseline_years <= 0:
            raise ValueError("baseline_years must be positive")
        p = Path(path)
        if name is None:
            name = p.stem

        zs: list[float] = []
        dvs: list[float] = []
        sigs: list[float] = []
        baselines: list[float] = []

        with p.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"Missing CSV header: {p}")
            missing = [c for c in (z_col, dv_col, sigma_col) if c not in reader.fieldnames]
            if missing:
                raise ValueError(f"Missing columns {missing} in {p}; available={reader.fieldnames}")
            has_baseline = baseline_col in reader.fieldnames or baseline_alt_col in reader.fieldnames
            baseline_key = baseline_col if baseline_col in reader.fieldnames else baseline_alt_col
            for row in reader:
                if not row:
                    continue
                z_s = (row.get(z_col) or "").strip()
                if not z_s:
                    continue
                zs.append(float(z_s))
                dvs.append(float((row.get(dv_col) or "").strip()))
                sigs.append(float((row.get(sigma_col) or "").strip()))
                if baseline_years is None:
                    if not has_baseline:
                        raise ValueError(
                            f"baseline_years not provided and no '{baseline_col}'/'{baseline_alt_col}' column in {p}"
                        )
                    baselines.append(float((row.get(baseline_key) or "").strip()))

        baseline_by_row: Optional[Tuple[float, ...]] = None
        baseline_scalar = 0.0
        if baseline_years is None:
            if not baselines:
                raise ValueError("No baseline_years values read from CSV")
            if any(b <= 0 for b in baselines):
                raise ValueError("baseline_years values must be positive")
            baseline_by_row = tuple(float(b) for b in baselines)
        else:
            baseline_scalar = float(baseline_years)

        return cls(
            name=name,
            z=tuple(zs),
            dv_cm_s=tuple(dvs),
            sigma_dv_cm_s=tuple(sigs),
            baseline_years=baseline_scalar,
            baseline_years_by_row=baseline_by_row,
        )

    def chi2(self, model: HzModel) -> Chi2Result:
        if not (len(self.z) == len(self.dv_cm_s) == len(self.sigma_dv_cm_s)):
            raise ValueError("z/dv/sigma length mismatch")
        if len(self.z) == 0:
            raise ValueError("Empty drift dataset")
        if self.baseline_years_by_row is None and self.baseline_years <= 0:
            raise ValueError("baseline_years must be positive")
        if self.baseline_years_by_row is not None and len(self.baseline_years_by_row) != len(self.z):
            raise ValueError("baseline_years_by_row length mismatch")

        H0 = float(model.H(0.0))
        chi2 = 0.0
        for i, (z, dv_obs, sig) in enumerate(zip(self.z, self.dv_cm_s, self.sigma_dv_cm_s)):
            if sig <= 0:
                raise ValueError("sigma_dv_cm_s must be positive")
            years = self.baseline_years_by_row[i] if self.baseline_years_by_row is not None else self.baseline_years
            dv_pred = delta_v_cm_s(z=z, years=years, H0=H0, H_of_z=model.H)
            r = (dv_obs - dv_pred) / sig
            chi2 += r * r

        return Chi2Result(chi2=float(chi2), ndof=int(len(self.z)), params={})
