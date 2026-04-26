"""Phase-2 E2 deformation families (diagnostic-only, stdlib-only).

This module keeps deformation helpers lightweight and explicit. The goal is to
expand explored late-time history families without changing the underlying
measurement-model equations.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

A_DIP_MIN = 0.0
A_DIP_MAX = 0.95
A_BUMP_MIN = 0.0
A_BUMP_MAX = 5.0

DEFAULT_DIP_Z_LO = 2.0
DEFAULT_DIP_Z_HI = 5.0
DEFAULT_BUMP_Z_LO = 5.0
DEFAULT_BUMP_Z_HI = 1100.0
DEFAULT_WINDOW_W = 0.25

DEFAULT_FACTOR_FLOOR = 1e-2

SPL4_DLOGH_MIN = -1.0
SPL4_DLOGH_MAX = 1.0
SPL4_KNOT_Z3 = 3.0
SPL4_KNOT_Z30 = 30.0
SPL4_KNOT_Z300 = 300.0
SPL4_KNOT_Z1100 = 1100.0


def _sigmoid_stable(x: float) -> float:
    """Numerically stable logistic sigmoid."""
    xx = float(x)
    if xx >= 0.0:
        e = math.exp(-xx)
        return 1.0 / (1.0 + e)
    e = math.exp(xx)
    return e / (1.0 + e)


def window(z: float, z_lo: float, z_hi: float, w: float) -> float:
    """Smooth top-hat window with logistic edges.

    W(z; z_lo, z_hi, w) = S((z-z_lo)/w) - S((z-z_hi)/w)
    """
    zz = float(z)
    z_lo_f = float(z_lo)
    z_hi_f = float(z_hi)
    w_f = float(w)
    if not (math.isfinite(zz) and math.isfinite(z_lo_f) and math.isfinite(z_hi_f) and math.isfinite(w_f)):
        raise ValueError("window expects finite inputs")
    if w_f <= 0.0:
        raise ValueError("window width w must be > 0")
    if z_hi_f <= z_lo_f:
        raise ValueError("window expects z_hi > z_lo")
    s_lo = _sigmoid_stable((zz - z_lo_f) / w_f)
    s_hi = _sigmoid_stable((zz - z_hi_f) / w_f)
    out = float(s_lo - s_hi)
    # Floating round-off can produce tiny overshoots outside [0,1].
    return min(1.0, max(0.0, out))


def log1p_gaussian_window(z: float, zc: float, w: float) -> float:
    """Gaussian window in x=ln(1+z), normalized to 1 at z=zc."""
    zz = float(z)
    zc_f = float(zc)
    w_f = float(w)
    if not (math.isfinite(zz) and math.isfinite(zc_f) and math.isfinite(w_f)):
        raise ValueError("log1p_gaussian_window expects finite inputs")
    if zz < 0.0:
        raise ValueError("z must be >= 0")
    if zc_f <= 0.0:
        raise ValueError("zc must be > 0")
    if w_f <= 0.0:
        raise ValueError("w must be > 0")
    x = math.log1p(zz)
    xc = math.log1p(zc_f)
    u = (x - xc) / w_f
    return float(math.exp(-0.5 * u * u))


@dataclass(frozen=True)
class DipBumpWindowDeformation:
    """Multiplicative deformation f(z)=1-A_dip*W_dip + A_bump*W_bump."""

    A_dip: float
    A_bump: float
    z_dip_lo: float = DEFAULT_DIP_Z_LO
    z_dip_hi: float = DEFAULT_DIP_Z_HI
    z_bump_lo: float = DEFAULT_BUMP_Z_LO
    z_bump_hi: float = DEFAULT_BUMP_Z_HI
    w: float = DEFAULT_WINDOW_W

    def __post_init__(self) -> None:
        a_dip = float(self.A_dip)
        a_bump = float(self.A_bump)
        if not (math.isfinite(a_dip) and A_DIP_MIN <= a_dip <= A_DIP_MAX):
            raise ValueError(f"A_dip must be finite and in [{A_DIP_MIN}, {A_DIP_MAX}]")
        if not (math.isfinite(a_bump) and A_BUMP_MIN <= a_bump <= A_BUMP_MAX):
            raise ValueError(f"A_bump must be finite and in [{A_BUMP_MIN}, {A_BUMP_MAX}]")

        for name, value in (
            ("z_dip_lo", self.z_dip_lo),
            ("z_dip_hi", self.z_dip_hi),
            ("z_bump_lo", self.z_bump_lo),
            ("z_bump_hi", self.z_bump_hi),
            ("w", self.w),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

        if float(self.z_dip_lo) < 0.0:
            raise ValueError("z_dip_lo must be >= 0")
        if float(self.z_dip_hi) <= float(self.z_dip_lo):
            raise ValueError("Require z_dip_hi > z_dip_lo")
        if float(self.z_bump_lo) < 0.0:
            raise ValueError("z_bump_lo must be >= 0")
        if float(self.z_bump_hi) <= float(self.z_bump_lo):
            raise ValueError("Require z_bump_hi > z_bump_lo")
        if float(self.w) <= 0.0:
            raise ValueError("window width w must be > 0")

    def minimum_possible_factor(self) -> float:
        """Conservative lower bound for f(z) over all z."""
        return float(1.0 - float(self.A_dip))

    def assert_positive(self, *, floor: float = DEFAULT_FACTOR_FLOOR) -> None:
        """Fail fast when deformation can drive H(z) too close to non-positive."""
        floor_f = float(floor)
        if not (math.isfinite(floor_f) and floor_f > 0.0):
            raise ValueError("floor must be finite and > 0")
        min_factor = self.minimum_possible_factor()
        if min_factor <= floor_f:
            raise ValueError(
                f"deformation factor min={min_factor:.6g} is <= floor={floor_f:.6g}; "
                "adjust A_dip or factor floor"
            )

    def factor(self, z: float) -> float:
        w_dip = window(float(z), float(self.z_dip_lo), float(self.z_dip_hi), float(self.w))
        w_bump = window(float(z), float(self.z_bump_lo), float(self.z_bump_hi), float(self.w))
        return float(1.0 - float(self.A_dip) * w_dip + float(self.A_bump) * w_bump)

    def apply(self, H_base: Callable[[float], float], *, floor: float = DEFAULT_FACTOR_FLOOR) -> Callable[[float], float]:
        """Return deformed H(z)=H_base(z)*factor(z) with positivity checks."""
        self.assert_positive(floor=floor)

        def _H(z: float) -> float:
            zz = float(z)
            hz = float(H_base(zz))
            if not (math.isfinite(hz) and hz > 0.0):
                raise ValueError("baseline H(z) must be positive and finite")
            fac = float(self.factor(zz))
            if not (math.isfinite(fac) and fac > float(floor)):
                raise ValueError(f"deformation factor invalid at z={zz}: {fac!r}")
            return float(hz * fac)

        return _H


@dataclass(frozen=True)
class LogHTwoWindowDeformation:
    """Two-window additive deformation in log H.

    delta_logH(z) = tw1_a*W1(z) + tw2_a*W2(z)
    H(z) = H_base(z) * exp(delta_logH(z))
    """

    tw1_zc: float
    tw1_w: float
    tw1_a: float
    tw2_zc: float
    tw2_w: float
    tw2_a: float

    def __post_init__(self) -> None:
        checks = (
            ("tw1_zc", self.tw1_zc),
            ("tw1_w", self.tw1_w),
            ("tw1_a", self.tw1_a),
            ("tw2_zc", self.tw2_zc),
            ("tw2_w", self.tw2_w),
            ("tw2_a", self.tw2_a),
        )
        for name, value in checks:
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if float(self.tw1_zc) <= 0.0:
            raise ValueError("tw1_zc must be > 0")
        if float(self.tw2_zc) <= 0.0:
            raise ValueError("tw2_zc must be > 0")
        if float(self.tw1_w) <= 0.0:
            raise ValueError("tw1_w must be > 0")
        if float(self.tw2_w) <= 0.0:
            raise ValueError("tw2_w must be > 0")

    def window1(self, z: float) -> float:
        return float(log1p_gaussian_window(z, float(self.tw1_zc), float(self.tw1_w)))

    def window2(self, z: float) -> float:
        return float(log1p_gaussian_window(z, float(self.tw2_zc), float(self.tw2_w)))

    def delta_log_h(self, z: float) -> float:
        w1 = self.window1(float(z))
        w2 = self.window2(float(z))
        return float(float(self.tw1_a) * w1 + float(self.tw2_a) * w2)

    def factor(self, z: float) -> float:
        delta = float(self.delta_log_h(float(z)))
        fac = float(math.exp(delta))
        if not (math.isfinite(fac) and fac > 0.0):
            raise ValueError(f"invalid logh_two_window factor at z={float(z)}")
        return fac

    def apply(self, H_base: Callable[[float], float]) -> Callable[[float], float]:
        def _H(z: float) -> float:
            zz = float(z)
            hz = float(H_base(zz))
            if not (math.isfinite(hz) and hz > 0.0):
                raise ValueError("baseline H(z) must be positive and finite")
            fac = float(self.factor(zz))
            return float(hz * fac)

        return _H


@dataclass(frozen=True)
class Spline4LogHDeformation:
    """Piecewise-linear spline for delta(log H) in x=ln(1+z) with fixed knots.

    Anchor:
    - z=0 has delta(logH)=0 so the deformation does not move H0.

    Free knot values:
    - z=3,30,300,1100 with per-knot delta(logH) parameters.
    """

    spl4_dlogh_z3: float
    spl4_dlogh_z30: float
    spl4_dlogh_z300: float
    spl4_dlogh_z1100: float

    def __post_init__(self) -> None:
        checks = (
            ("spl4_dlogh_z3", self.spl4_dlogh_z3),
            ("spl4_dlogh_z30", self.spl4_dlogh_z30),
            ("spl4_dlogh_z300", self.spl4_dlogh_z300),
            ("spl4_dlogh_z1100", self.spl4_dlogh_z1100),
        )
        for name, value in checks:
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

    @staticmethod
    def _knot_x() -> tuple[float, float, float, float, float]:
        return (
            math.log1p(0.0),
            math.log1p(SPL4_KNOT_Z3),
            math.log1p(SPL4_KNOT_Z30),
            math.log1p(SPL4_KNOT_Z300),
            math.log1p(SPL4_KNOT_Z1100),
        )

    def _knot_y(self) -> tuple[float, float, float, float, float]:
        return (
            0.0,
            float(self.spl4_dlogh_z3),
            float(self.spl4_dlogh_z30),
            float(self.spl4_dlogh_z300),
            float(self.spl4_dlogh_z1100),
        )

    def dlogh(self, z: float) -> float:
        zz = float(z)
        if not math.isfinite(zz):
            raise ValueError("z must be finite")
        if zz < 0.0:
            raise ValueError("z must be >= 0")

        x = math.log1p(zz)
        knot_x = self._knot_x()
        knot_y = self._knot_y()

        if x <= knot_x[0]:
            return float(knot_y[0])
        for i in range(len(knot_x) - 1):
            x0 = float(knot_x[i])
            x1 = float(knot_x[i + 1])
            if x <= x1:
                y0 = float(knot_y[i])
                y1 = float(knot_y[i + 1])
                t = (x - x0) / (x1 - x0)
                return float(y0 + t * (y1 - y0))
        # Hold-last for z > 1100.
        return float(knot_y[-1])

    def factor(self, z: float) -> float:
        delta = float(self.dlogh(float(z)))
        fac = float(math.exp(delta))
        if not (math.isfinite(fac) and fac > 0.0):
            raise ValueError(f"invalid spline4_logh factor at z={float(z)}")
        return fac

    def apply(self, H_base: Callable[[float], float]) -> Callable[[float], float]:
        def _H(z: float) -> float:
            zz = float(z)
            hz = float(H_base(zz))
            if not (math.isfinite(hz) and hz > 0.0):
                raise ValueError("baseline H(z) must be positive and finite")
            return float(hz * self.factor(zz))

        return _H


__all__ = [
    "A_BUMP_MAX",
    "A_BUMP_MIN",
    "A_DIP_MAX",
    "A_DIP_MIN",
    "DEFAULT_BUMP_Z_HI",
    "DEFAULT_BUMP_Z_LO",
    "DEFAULT_DIP_Z_HI",
    "DEFAULT_DIP_Z_LO",
    "DEFAULT_FACTOR_FLOOR",
    "DEFAULT_WINDOW_W",
    "DipBumpWindowDeformation",
    "LogHTwoWindowDeformation",
    "SPL4_DLOGH_MAX",
    "SPL4_DLOGH_MIN",
    "SPL4_KNOT_Z3",
    "SPL4_KNOT_Z30",
    "SPL4_KNOT_Z300",
    "SPL4_KNOT_Z1100",
    "Spline4LogHDeformation",
    "log1p_gaussian_window",
    "window",
]
