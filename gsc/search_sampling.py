"""Deterministic sampling helpers for lightweight parameter-space scans."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple


Bounds = Mapping[str, Tuple[float, float]]


@dataclass(frozen=True)
class MHSummary:
    samples: List[Dict[str, float]]
    acceptance_rate: float
    accepted_steps: int
    total_steps: int


@dataclass(frozen=True)
class AdaptiveMHProposal:
    step_index: int
    proposal: Dict[str, float]
    proposal_scales: Dict[str, float]


@dataclass(frozen=True)
class AdaptiveMHTransformState:
    keys: Tuple[str, ...]
    y_current: Dict[str, float]
    scales: Dict[str, float]
    acceptance_window_rate: float
    accepted_window: int
    window_count: int
    adaptation_round: int


def _sorted_keys(mapping: Mapping[str, object]) -> List[str]:
    return sorted(str(k) for k in mapping.keys())


def _normalize_bounds(bounds: Bounds) -> Dict[str, Tuple[float, float]]:
    if not bounds:
        raise ValueError("bounds must not be empty")
    norm: Dict[str, Tuple[float, float]] = {}
    for key in _sorted_keys(bounds):
        lo, hi = bounds[key]
        lo_f = float(lo)
        hi_f = float(hi)
        if not (math.isfinite(lo_f) and math.isfinite(hi_f)):
            raise ValueError(f"bounds for {key!r} must be finite")
        if hi_f < lo_f:
            raise ValueError(f"invalid bounds for {key!r}: hi < lo")
        norm[key] = (lo_f, hi_f)
    return norm


def _sigmoid_stable(x: float) -> float:
    xx = float(x)
    if xx >= 0.0:
        z = math.exp(-xx)
        return 1.0 / (1.0 + z)
    z = math.exp(xx)
    return z / (1.0 + z)


def _clamp_unit_open(u: float, *, eps: float = 1e-12) -> float:
    uu = float(u)
    lo = float(eps)
    hi = 1.0 - float(eps)
    if uu <= lo:
        return lo
    if uu >= hi:
        return hi
    return uu


def bounded_logit_transform(x: float, lo: float, hi: float) -> float:
    lo_f = float(lo)
    hi_f = float(hi)
    if not (math.isfinite(lo_f) and math.isfinite(hi_f) and hi_f > lo_f):
        raise ValueError("bounded_logit_transform requires finite lo<hi")
    xx = float(x)
    if not (math.isfinite(xx) and lo_f <= xx <= hi_f):
        raise ValueError("x must be finite and inside [lo, hi]")
    if xx == lo_f:
        uu = _clamp_unit_open(0.0)
    elif xx == hi_f:
        uu = _clamp_unit_open(1.0)
    else:
        uu = _clamp_unit_open((xx - lo_f) / (hi_f - lo_f))
    return math.log(uu) - math.log1p(-uu)


def bounded_logit_inverse(y: float, lo: float, hi: float) -> float:
    lo_f = float(lo)
    hi_f = float(hi)
    if not (math.isfinite(lo_f) and math.isfinite(hi_f) and hi_f > lo_f):
        raise ValueError("bounded_logit_inverse requires finite lo<hi")
    yy = float(y)
    if not math.isfinite(yy):
        raise ValueError("bounded_logit_inverse requires finite y")
    uu = _clamp_unit_open(_sigmoid_stable(yy))
    return lo_f + (hi_f - lo_f) * uu


class AdaptiveRWMHSampler:
    """Deterministic bounded adaptive random-walk proposals in transformed space."""

    def __init__(
        self,
        *,
        bounds: Bounds,
        start: Mapping[str, float],
        seed: int,
        init_scale: float = 0.1,
        target_accept: float = 0.25,
        adapt_every: int = 25,
        min_scale: float = 1e-6,
        max_scale: float = 1e2,
    ) -> None:
        self._bounds = _normalize_bounds(bounds)
        self._keys: Tuple[str, ...] = tuple(_sorted_keys(self._bounds))
        if not self._keys:
            raise ValueError("bounds must not be empty")
        if set(self._keys) != set(_sorted_keys(start)):
            raise ValueError("start keys must match bounds keys")
        for key in self._keys:
            value = float(start[key])
            lo, hi = self._bounds[key]
            if not (math.isfinite(value) and lo <= value <= hi):
                raise ValueError(f"start[{key!r}] must be finite and inside bounds")

        if not (math.isfinite(float(init_scale)) and float(init_scale) > 0.0):
            raise ValueError("init_scale must be finite and > 0")
        if not (math.isfinite(float(target_accept)) and 0.0 < float(target_accept) < 1.0):
            raise ValueError("target_accept must be finite and in (0,1)")
        if int(adapt_every) <= 0:
            raise ValueError("adapt_every must be > 0")
        if not (math.isfinite(float(min_scale)) and math.isfinite(float(max_scale)) and float(min_scale) > 0.0):
            raise ValueError("min_scale/max_scale must be finite and > 0")
        if float(max_scale) < float(min_scale):
            raise ValueError("max_scale must be >= min_scale")

        self._rng = random.Random(int(seed))
        self._target_accept = float(target_accept)
        self._adapt_every = int(adapt_every)
        self._min_log_scale = math.log(float(min_scale))
        self._max_log_scale = math.log(float(max_scale))
        self._log_scales: Dict[str, float] = {k: math.log(float(init_scale)) for k in self._keys}

        self._x_current: Dict[str, float] = {k: float(start[k]) for k in self._keys}
        self._y_current: Dict[str, float] = {
            k: bounded_logit_transform(float(start[k]), self._bounds[k][0], self._bounds[k][1])
            for k in self._keys
        }
        self._y_pending: Optional[Dict[str, float]] = None
        self._x_pending: Optional[Dict[str, float]] = None
        self._step_index: int = 0
        self._window_count: int = 0
        self._accepted_window: int = 0
        self._adapt_round: int = 0
        self._last_window_rate: float = 0.0

    @property
    def keys(self) -> Tuple[str, ...]:
        return self._keys

    def current_point(self) -> Dict[str, float]:
        return {k: float(v) for k, v in self._x_current.items()}

    def current_transformed(self) -> Dict[str, float]:
        return {k: float(v) for k, v in self._y_current.items()}

    def proposal_scales(self) -> Dict[str, float]:
        return {k: float(math.exp(v)) for k, v in self._log_scales.items()}

    def propose(self) -> AdaptiveMHProposal:
        y_prop: Dict[str, float] = {}
        x_prop: Dict[str, float] = {}
        scales = self.proposal_scales()
        for key in self._keys:
            y = float(self._y_current[key]) + self._rng.gauss(0.0, float(scales[key]))
            lo, hi = self._bounds[key]
            x = bounded_logit_inverse(y, lo, hi)
            y_prop[key] = float(y)
            x_prop[key] = float(x)

        self._y_pending = y_prop
        self._x_pending = x_prop
        return AdaptiveMHProposal(
            step_index=int(self._step_index),
            proposal={k: float(v) for k, v in x_prop.items()},
            proposal_scales={k: float(v) for k, v in scales.items()},
        )

    def _apply_adaptation(self) -> None:
        self._adapt_round += 1
        rate = float(self._accepted_window) / float(self._window_count) if self._window_count > 0 else 0.0
        self._last_window_rate = float(rate)
        gamma = 1.0 / math.sqrt(float(self._adapt_round))
        delta = float(gamma) * (float(rate) - float(self._target_accept))
        for key in self._keys:
            new_log = float(self._log_scales[key]) + float(delta)
            new_log = min(max(new_log, self._min_log_scale), self._max_log_scale)
            self._log_scales[key] = float(new_log)
        self._window_count = 0
        self._accepted_window = 0

    def record_acceptance(self, accepted: bool) -> None:
        if self._x_pending is None or self._y_pending is None:
            raise RuntimeError("record_acceptance() called before propose()")

        if bool(accepted):
            self._x_current = {k: float(v) for k, v in self._x_pending.items()}
            self._y_current = {k: float(v) for k, v in self._y_pending.items()}
            self._accepted_window += 1

        self._x_pending = None
        self._y_pending = None
        self._step_index += 1
        self._window_count += 1
        if self._window_count >= self._adapt_every:
            self._apply_adaptation()

    def transform_state(self) -> AdaptiveMHTransformState:
        return AdaptiveMHTransformState(
            keys=tuple(self._keys),
            y_current={k: float(v) for k, v in self._y_current.items()},
            scales=self.proposal_scales(),
            acceptance_window_rate=float(self._last_window_rate),
            accepted_window=int(self._accepted_window),
            window_count=int(self._window_count),
            adaptation_round=int(self._adapt_round),
        )


def iter_random_points(bounds: Bounds, n: int, seed: int) -> Iterator[Dict[str, float]]:
    """Yield deterministic random points from axis-aligned bounds."""
    if n <= 0:
        raise ValueError("n must be > 0")
    norm = _normalize_bounds(bounds)
    rng = random.Random(int(seed))
    for _ in range(int(n)):
        point: Dict[str, float] = {}
        for key in _sorted_keys(norm):
            lo, hi = norm[key]
            point[key] = float(lo if lo == hi else rng.uniform(lo, hi))
        yield point


def halton_bases(dim: int) -> List[int]:
    """Return the first ``dim`` prime bases used by the Halton sampler."""
    return _first_primes(int(dim))


def _first_primes(n: int) -> List[int]:
    if n <= 0:
        raise ValueError("n must be > 0")
    primes: List[int] = []
    candidate = 2
    while len(primes) < n:
        is_prime = True
        limit = int(math.sqrt(float(candidate))) + 1
        for p in primes:
            if p > limit:
                break
            if candidate % p == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(candidate)
        candidate += 1
    return primes


def _radical_inverse(index: int, base: int, digit_perm: Optional[Sequence[int]] = None) -> float:
    if index < 0:
        raise ValueError("index must be >= 0")
    if base <= 1:
        raise ValueError("base must be > 1")
    if digit_perm is not None:
        if len(digit_perm) != base:
            raise ValueError("digit_perm length must equal base")
        if sorted(int(v) for v in digit_perm) != list(range(base)):
            raise ValueError("digit_perm must be a permutation of [0, base)")

    out = 0.0
    inv = 1.0 / float(base)
    factor = inv
    i = int(index)
    while i > 0:
        digit = int(i % base)
        if digit_perm is not None:
            digit = int(digit_perm[digit])
        out += float(digit) * factor
        i //= base
        factor *= inv
    return float(out)


def _digit_permutation(base: int, seed: int, dim_index: int) -> List[int]:
    """Build a deterministic digit permutation with 0 fixed to avoid boundary collapse."""
    if base <= 1:
        raise ValueError("base must be > 1")
    if base == 2:
        return [0, 1]
    rng = random.Random(int(seed) + 1009 * int(dim_index))
    tail = list(range(1, int(base)))
    rng.shuffle(tail)
    if tail == list(range(1, int(base))) and len(tail) > 1:
        tail = tail[1:] + tail[:1]
    return [0] + tail


def iter_halton_points(
    bounds: Bounds,
    n: int,
    seed: int = 0,
    *,
    scramble: bool = False,
    skip: int = 0,
) -> Iterator[Dict[str, float]]:
    """Yield Halton low-discrepancy samples mapped to axis-aligned bounds."""
    if n <= 0:
        raise ValueError("n must be > 0")
    if skip < 0:
        raise ValueError("skip must be >= 0")
    norm = _normalize_bounds(bounds)
    keys = _sorted_keys(norm)
    bases = halton_bases(len(keys))
    perms: List[Optional[List[int]]] = []
    for dim_index, base in enumerate(bases):
        if scramble:
            perms.append(_digit_permutation(base, int(seed), dim_index))
        else:
            perms.append(None)

    for sample_index in range(int(n)):
        halton_index = int(skip) + sample_index + 1  # start at 1 to avoid the all-zero vector
        point: Dict[str, float] = {}
        for dim_index, key in enumerate(keys):
            lo, hi = norm[key]
            u = _radical_inverse(halton_index, bases[dim_index], perms[dim_index])
            # Keep the unit interval half-open by clipping exact 1.0 from floating error.
            u = min(max(float(u), 0.0), math.nextafter(1.0, 0.0))
            point[key] = float(lo if lo == hi else lo + (hi - lo) * u)
        yield point


def iter_lhs_points(bounds: Bounds, n: int, seed: int = 0) -> Iterator[Dict[str, float]]:
    """Yield deterministic center-jitter-free Latin hypercube samples."""
    if n <= 0:
        raise ValueError("n must be > 0")
    norm = _normalize_bounds(bounds)
    keys = _sorted_keys(norm)
    n_int = int(n)
    per_dim_perm: List[List[int]] = []
    for dim_index in range(len(keys)):
        rng = random.Random(int(seed) + 1009 * int(dim_index))
        perm = list(range(n_int))
        rng.shuffle(perm)
        per_dim_perm.append(perm)

    for sample_index in range(n_int):
        point: Dict[str, float] = {}
        for dim_index, key in enumerate(keys):
            lo, hi = norm[key]
            u = (float(per_dim_perm[dim_index][sample_index]) + 0.5) / float(n_int)
            point[key] = float(lo if lo == hi else lo + (hi - lo) * u)
        yield point


def _in_bounds(sample: Mapping[str, float], bounds: Optional[Bounds]) -> bool:
    if bounds is None:
        return True
    for key, (lo, hi) in _normalize_bounds(bounds).items():
        val = float(sample[key])
        if val < lo or val > hi:
            return False
    return True


def metropolis_hastings(
    logp: Callable[[Mapping[str, float]], float],
    start: Mapping[str, float],
    step_scales: Mapping[str, float],
    n_steps: int,
    seed: int,
    burn: int = 0,
    thin: int = 1,
    bounds: Optional[Bounds] = None,
) -> Iterator[Dict[str, float]]:
    """Yield deterministic MH samples from a generic log-probability callback."""
    yield from run_metropolis_hastings(
        logp=logp,
        start=start,
        step_scales=step_scales,
        n_steps=n_steps,
        seed=seed,
        burn=burn,
        thin=thin,
        bounds=bounds,
    ).samples


def run_metropolis_hastings(
    logp: Callable[[Mapping[str, float]], float],
    start: Mapping[str, float],
    step_scales: Mapping[str, float],
    n_steps: int,
    seed: int,
    burn: int = 0,
    thin: int = 1,
    bounds: Optional[Bounds] = None,
) -> MHSummary:
    """Run deterministic MH and return samples plus acceptance statistics."""
    if n_steps <= 0:
        raise ValueError("n_steps must be > 0")
    if burn < 0:
        raise ValueError("burn must be >= 0")
    if thin <= 0:
        raise ValueError("thin must be > 0")
    keys = _sorted_keys(start)
    if not keys:
        raise ValueError("start must not be empty")
    for key in keys:
        if key not in step_scales:
            raise ValueError(f"missing step scale for key {key!r}")
        scale = float(step_scales[key])
        if not (math.isfinite(scale) and scale > 0.0):
            raise ValueError(f"invalid step scale for {key!r}: {scale!r}")

    if bounds is not None:
        norm_bounds = _normalize_bounds(bounds)
        missing = [k for k in keys if k not in norm_bounds]
        if missing:
            raise ValueError(f"bounds missing keys: {missing}")
    else:
        norm_bounds = None

    current = {key: float(start[key]) for key in keys}
    if not _in_bounds(current, norm_bounds):
        raise ValueError("start point is outside bounds")

    def _safe_logp(p: Mapping[str, float]) -> float:
        if not _in_bounds(p, norm_bounds):
            return float("-inf")
        try:
            value = float(logp(p))
        except Exception:
            return float("-inf")
        return value if math.isfinite(value) else float("-inf")

    current_logp = _safe_logp(current)
    rng = random.Random(int(seed))
    accepted_steps = 0
    samples: List[Dict[str, float]] = []

    for step in range(int(n_steps)):
        proposal = dict(current)
        for key in keys:
            proposal[key] = float(proposal[key] + rng.gauss(0.0, float(step_scales[key])))
        proposal_logp = _safe_logp(proposal)

        accept = False
        if proposal_logp > current_logp:
            accept = True
        elif math.isfinite(proposal_logp):
            if not math.isfinite(current_logp):
                accept = True
            else:
                delta = proposal_logp - current_logp
                if delta >= 0.0:
                    accept = True
                else:
                    accept = rng.random() < math.exp(delta)

        if accept:
            current = proposal
            current_logp = proposal_logp
            accepted_steps += 1

        if step >= burn and ((step - burn) % thin == 0):
            samples.append(dict(current))

    total_steps = int(n_steps)
    acceptance_rate = float(accepted_steps) / float(total_steps) if total_steps > 0 else 0.0
    return MHSummary(
        samples=samples,
        acceptance_rate=acceptance_rate,
        accepted_steps=accepted_steps,
        total_steps=total_steps,
    )


__all__ = [
    "AdaptiveMHProposal",
    "AdaptiveMHTransformState",
    "AdaptiveRWMHSampler",
    "MHSummary",
    "bounded_logit_inverse",
    "bounded_logit_transform",
    "halton_bases",
    "iter_halton_points",
    "iter_lhs_points",
    "iter_random_points",
    "metropolis_hastings",
    "run_metropolis_hastings",
]
