#!/usr/bin/env python3
"""Deterministic Triangle-1 joint SN+BAO epsilon posterior (Phase-4 M157 / 4B.5)."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time
import zlib
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.datasets.bao import BAOBlock1D, BAOBlock2D, BAODataset  # noqa: E402
from gsc.datasets.sn import load_sn_mu_csv  # noqa: E402
from gsc.epsilon.translator import one_plus_z_from_sigma_ratio  # noqa: E402
from gsc.histories.full_range import FlatLCDMRadHistory  # noqa: E402
from gsc.measurement_model import C_SI, H0_to_SI, distance_modulus_from_D_L  # noqa: E402


TOOL = "phase4_triangle1_joint_sn_bao_epsilon_posterior"
TOOL_VERSION = "m157-v1"
SCHEMA = "phase4_triangle1_joint_sn_bao_epsilon_posterior_report_v1"
PANTHEON_FETCH_SCHEMA = "phase4_pantheon_plus_fetch_manifest_v1"
DESI_FETCH_SCHEMA = "phase4_desi_bao_fetch_manifest_v1"
FAIL_MARKER = "PHASE4_TRIANGLE1_JOINT_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")
DEFAULT_PANTHEON_DATASET = "data/sn/pantheon_plus_shoes/pantheon_plus_shoes_mu.csv"
DEFAULT_BAO_DATASET = "data/bao/desi/desi_dr1_bao_baseline.csv"


class UsageError(Exception):
    """CLI usage/configuration error."""


class JointError(Exception):
    """Runtime joint-posterior failure."""


@dataclass(frozen=True)
class SNDatasetBundle:
    z_obs: List[float]
    mu_obs: List[float]
    sigma_mu: List[float]
    meta: Dict[str, Any]
    row_full: Optional[List[int]]


@dataclass(frozen=True)
class BAODatasetBundle:
    dataset: BAODataset
    relpath: str
    sha256: str
    mode: str


@dataclass(frozen=True)
class RowResult:
    omega_m: float
    epsilon_em: float
    chi2_joint: float
    chi2_sn: float
    chi2_bao: float
    ndof_joint: int
    ndof_sn: int
    ndof_bao: int
    delta_m: float
    rd_m: float


class EpsilonMappedLCDMHistory:
    """Flat LCDM history with inference-layer epsilon redshift remapping.

    Mapping convention (same toy ansatz family as M148/M156):
      1 + z_em = sigma_ratio^(1 + epsilon_em), epsilon_gr = 0
      => 1 + z_gr = sigma_ratio = (1 + z_em)^(1/(1+epsilon_em))
    """

    def __init__(
        self,
        *,
        h0_si: float,
        omega_m: float,
        epsilon_em: float,
        Tcmb_K: float,
        N_eff: float,
    ) -> None:
        self._epsilon_em = float(epsilon_em)
        if not math.isfinite(self._epsilon_em):
            raise JointError("epsilon_em must be finite")
        if abs(1.0 + self._epsilon_em) < 1.0e-12:
            raise JointError("epsilon_em too close to -1 makes mapping undefined")
        self._base = FlatLCDMRadHistory(
            H0=float(h0_si),
            Omega_m=float(omega_m),
            Tcmb_K=float(Tcmb_K),
            N_eff=float(N_eff),
        )

    def _z_gr_from_z_obs(self, z_obs: float) -> float:
        z = float(z_obs)
        one_plus_z_obs = 1.0 + z
        if one_plus_z_obs <= 0.0:
            raise JointError("observed redshift must satisfy 1+z>0")

        sigma_ratio = one_plus_z_obs ** (1.0 / (1.0 + self._epsilon_em))
        one_plus_z_em_check = one_plus_z_from_sigma_ratio(sigma_ratio, self._epsilon_em)
        if abs(one_plus_z_em_check - one_plus_z_obs) > 1.0e-10 * max(1.0, one_plus_z_obs):
            raise JointError("epsilon mapping inversion consistency check failed")
        return float(sigma_ratio - 1.0)

    def H(self, z: float) -> float:
        return float(self._base.H(self._z_gr_from_z_obs(float(z))))


def _optional_numpy() -> Any:
    try:  # pragma: no cover - environment dependent
        import numpy as np  # type: ignore

        return np
    except Exception:
        return None


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _fmt_e(value: float) -> str:
    return f"{float(value):.12e}"


def _to_iso_utc(epoch_seconds: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    except Exception as exc:
        raise UsageError("--created-utc must be a valid integer epoch-seconds value") from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_finite(value: float, *, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise UsageError(f"{name} must be finite")
    return out


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_int_like(value: float) -> bool:
    return math.isfinite(value) and float(int(value)) == float(value)


def _split_numeric_tokens(line: str) -> List[str]:
    out: List[str] = []
    token: List[str] = []
    for ch in line:
        if ch in (" ", "\t", ",", ";"):
            if token:
                out.append("".join(token))
                token = []
            continue
        token.append(ch)
    if token:
        out.append("".join(token))
    return out


def _infer_tri_n(count: int) -> Optional[int]:
    if count <= 0:
        return None
    disc = 1 + 8 * count
    root = int(math.isqrt(disc))
    if root * root != disc:
        return None
    n = (root - 1) // 2
    if n * (n + 1) // 2 != count:
        return None
    return int(n)


def _load_covariance_matrix(path: Path) -> List[List[float]]:
    if not path.is_file():
        raise UsageError(f"covariance file not found: {path}")
    values: List[float] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            for tok in _split_numeric_tokens(line):
                try:
                    values.append(float(tok))
                except ValueError as exc:
                    raise JointError(f"non-numeric token in covariance file {path.name}: {tok!r}") from exc
    if not values:
        raise JointError(f"empty covariance file: {path.name}")

    n: Optional[int] = None
    raw_vals = values
    if _is_int_like(values[0]) and values[0] > 0.0:
        candidate_n = int(values[0])
        rest = values[1:]
        if len(rest) in (candidate_n * candidate_n, candidate_n * (candidate_n + 1) // 2):
            n = candidate_n
            raw_vals = rest

    if n is None:
        m = len(values)
        sq = int(math.isqrt(m))
        if sq * sq == m:
            n = sq
            raw_vals = values
        else:
            tri = _infer_tri_n(m)
            if tri is not None:
                n = tri
                raw_vals = values
    if n is None or n <= 0:
        raise JointError(
            f"unable to infer covariance layout for {path.name}; provide full N*N or triangular values (optionally with leading N)"
        )

    mat: List[List[float]] = [[0.0 for _ in range(n)] for _ in range(n)]
    n2 = n * n
    ntri = n * (n + 1) // 2
    if len(raw_vals) == n2:
        idx = 0
        for i in range(n):
            row = mat[i]
            for j in range(n):
                row[j] = float(raw_vals[idx])
                idx += 1
    elif len(raw_vals) == ntri:
        idx = 0
        for i in range(n):
            for j in range(i + 1):
                v = float(raw_vals[idx])
                mat[i][j] = v
                mat[j][i] = v
                idx += 1
    else:
        raise JointError(f"covariance layout mismatch for {path.name}; got {len(raw_vals)} values")
    return mat


def _subset_covariance(cov: Sequence[Sequence[float]], indices: Sequence[int]) -> List[List[float]]:
    n = len(cov)
    if n == 0:
        raise JointError("covariance matrix is empty")
    idx = [int(v) for v in indices]
    if len(set(idx)) != len(idx):
        raise JointError("row_full indices must be unique")
    if min(idx) < 0 or max(idx) >= n:
        raise JointError("row_full indices are out of covariance bounds")
    return [[float(cov[i][j]) for j in idx] for i in idx]


def _cholesky_factor(cov: Sequence[Sequence[float]]) -> List[List[float]]:
    n = len(cov)
    if n == 0:
        raise JointError("covariance matrix is empty")
    for row in cov:
        if len(row) != n:
            raise JointError("covariance matrix must be square")

    l: List[List[float]] = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = float(cov[i][j])
            for k in range(j):
                s -= l[i][k] * l[j][k]
            if i == j:
                if s <= 0.0:
                    raise JointError("covariance matrix is not positive definite")
                l[i][j] = math.sqrt(s)
            else:
                denom = l[j][j]
                if denom == 0.0:
                    raise JointError("covariance decomposition failure")
                l[i][j] = s / denom
    return l


def _solve_cholesky(l: Sequence[Sequence[float]], b: Sequence[float]) -> List[float]:
    n = len(l)
    if len(b) != n:
        raise JointError("solve vector length mismatch")
    y = [0.0 for _ in range(n)]
    for i in range(n):
        s = float(b[i])
        for k in range(i):
            s -= float(l[i][k]) * y[k]
        denom = float(l[i][i])
        if denom == 0.0:
            raise JointError("singular covariance factor (forward solve)")
        y[i] = s / denom

    x = [0.0 for _ in range(n)]
    for i in range(n - 1, -1, -1):
        s = y[i]
        for k in range(i + 1, n):
            s -= float(l[k][i]) * x[k]
        denom = float(l[i][i])
        if denom == 0.0:
            raise JointError("singular covariance factor (back solve)")
        x[i] = s / denom
    return x


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise JointError("dot length mismatch")
    return float(sum(float(x) * float(y) for x, y in zip(a, b)))


def _make_cov_solver(cov: Sequence[Sequence[float]]) -> Any:
    n = len(cov)
    np = _optional_numpy()
    if np is not None:
        arr = np.asarray(cov, dtype=float)
        if arr.shape != (n, n):
            raise JointError("covariance matrix must be square")
        try:
            l_np = np.linalg.cholesky(arr)
        except Exception as exc:
            raise JointError("covariance matrix is not positive definite") from exc

        def solve(vec: Sequence[float]) -> List[float]:
            vv = np.asarray(vec, dtype=float)
            if vv.shape != (n,):
                raise JointError("solve vector length mismatch")
            y = np.linalg.solve(l_np, vv)
            x = np.linalg.solve(l_np.T, y)
            return [float(v) for v in x.tolist()]

        return solve

    if n > 256:
        raise JointError(
            "full covariance mode without numpy supports only n<=256; install numpy for large covariance runs"
        )
    l = _cholesky_factor(cov)

    def solve(vec: Sequence[float]) -> List[float]:
        return _solve_cholesky(l, vec)

    return solve


def _snapshot_fingerprint(repo_root: Path) -> Dict[str, str]:
    candidates = (
        repo_root / "repo_snapshot_manifest.json",
        repo_root.parent / "repo_snapshot_manifest.json",
    )
    for path in candidates:
        if path.is_file():
            return {
                "repo_snapshot_manifest_sha256": _sha256_file(path),
                "repo_snapshot_manifest_source": path.name,
            }
    return {
        "repo_snapshot_manifest_sha256": "unavailable",
        "repo_snapshot_manifest_source": "unavailable",
    }


def _relative_or_basename(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return path.name


def _resolve_path_from_repo(repo_root: Path, raw_path: str) -> Path:
    p = Path(raw_path)
    if p.is_absolute():
        return p.expanduser().resolve()
    return (repo_root / p).resolve()


def _resolve_from_manifest_filename(repo_root: Path, manifest_path: Optional[Path], filename: Optional[str]) -> Optional[Path]:
    if not filename:
        return None
    name = str(filename).strip()
    if not name:
        return None
    candidates: List[Path] = []
    if manifest_path is not None:
        candidates.append((manifest_path.parent / name).resolve())
    candidates.append((repo_root / name).resolve())
    for c in candidates:
        if c.is_file():
            return c
    return None


def _linear_grid(vmin: float, vmax: float, n: int, *, name: str) -> List[float]:
    n_i = int(n)
    if n_i < 2:
        raise UsageError(f"{name} grid count must be >= 2")
    lo = _require_finite(vmin, name=f"{name}_min")
    hi = _require_finite(vmax, name=f"{name}_max")
    if hi < lo:
        raise UsageError(f"{name}_max must be >= {name}_min")
    if n_i == 2:
        return [float(lo), float(hi)]
    step = (hi - lo) / float(n_i - 1)
    return [float(lo + i * step) for i in range(n_i)]


def _z_gr_from_z_obs(z_obs: float, epsilon_em: float) -> float:
    z_val = _require_finite(z_obs, name="z_obs")
    eps = _require_finite(epsilon_em, name="epsilon_em")
    denom = 1.0 + eps
    if abs(denom) < 1.0e-12:
        raise JointError("epsilon_em too close to -1 makes z_gr mapping undefined")
    one_plus_z_obs = 1.0 + z_val
    if one_plus_z_obs <= 0.0:
        raise JointError("observed z must satisfy 1+z>0")
    sigma_ratio = one_plus_z_obs ** (1.0 / denom)
    one_plus_z_em_check = one_plus_z_from_sigma_ratio(sigma_ratio, eps)
    if abs(one_plus_z_em_check - one_plus_z_obs) > 1.0e-10 * max(1.0, one_plus_z_obs):
        raise JointError("epsilon mapping inversion consistency check failed")
    return float(sigma_ratio - 1.0)


def _build_dl_table(*, omega_m: float, h0_si: float, z_max: float, n_steps: int) -> Tuple[List[float], List[float]]:
    om = _require_finite(omega_m, name="omega_m")
    if not (0.0 < om < 1.0):
        raise JointError(f"omega_m must satisfy 0<omega_m<1, got {om}")
    h0 = _require_finite(h0_si, name="h0_si")
    if h0 <= 0.0:
        raise JointError("h0_si must be > 0")
    z_hi = max(1.0e-6, _require_finite(z_max, name="z_max"))
    if z_hi < 0.0:
        raise JointError("z_max must be >= 0")
    n = int(n_steps)
    if n < 32:
        raise JointError("integration_n must be >= 32")

    omega_l = 1.0 - om
    dz = z_hi / float(n)

    z_nodes: List[float] = [0.0] * (n + 1)
    d_l_nodes: List[float] = [0.0] * (n + 1)
    inv_e_prev = 1.0 / math.sqrt(om + omega_l)
    integral = 0.0

    for i in range(1, n + 1):
        z = float(i) * dz
        one_plus = 1.0 + z
        e2 = om * (one_plus ** 3) + omega_l
        if e2 <= 0.0:
            raise JointError("non-positive E^2 encountered in D_L table build")
        inv_e = 1.0 / math.sqrt(e2)
        integral += 0.5 * (inv_e_prev + inv_e) * dz
        d_c = (C_SI / h0) * integral
        d_l = (1.0 + z) * d_c
        z_nodes[i] = z
        d_l_nodes[i] = d_l
        inv_e_prev = inv_e

    return z_nodes, d_l_nodes


def _interp_linear(xs: Sequence[float], ys: Sequence[float], xq: float) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise JointError("interpolation table must have >=2 aligned points")
    x0 = float(xs[0])
    x1 = float(xs[-1])
    x = float(xq)
    eps = 1.0e-12 * max(1.0, abs(x1))
    if x < x0 - eps or x > x1 + eps:
        raise JointError(f"z query {x:.6g} outside interpolation range [{x0:.6g}, {x1:.6g}]")
    if x < x0:
        x = x0
    if x > x1:
        x = x1

    idx = bisect_right(xs, x)
    if idx <= 0:
        return float(ys[0])
    if idx >= len(xs):
        return float(ys[-1])
    i0 = idx - 1
    i1 = idx
    xa = float(xs[i0])
    xb = float(xs[i1])
    ya = float(ys[i0])
    yb = float(ys[i1])
    if xb == xa:
        return ya
    t = (x - xa) / (xb - xa)
    return ya + t * (yb - ya)


def _mu_from_table(z_gr: float, z_nodes: Sequence[float], d_l_nodes: Sequence[float]) -> float:
    d_l = _interp_linear(z_nodes, d_l_nodes, float(z_gr))
    if d_l <= 0.0:
        raise JointError("D_L must remain positive")
    return float(distance_modulus_from_D_L(D_L_m=d_l))


def _profile_chi2(*, mu_obs: Sequence[float], sigma_mu: Sequence[float], mu_model: Sequence[float]) -> Tuple[float, float]:
    if not (len(mu_obs) == len(sigma_mu) == len(mu_model)):
        raise JointError("mu arrays must have matching length")
    if len(mu_obs) == 0:
        raise JointError("empty SN dataset")

    s0 = 0.0
    s1 = 0.0
    s2 = 0.0
    for obs, sig, mdl in zip(mu_obs, sigma_mu, mu_model):
        sig_v = float(sig)
        if sig_v <= 0.0:
            raise JointError("sigma_mu must be > 0")
        w = 1.0 / (sig_v * sig_v)
        r = float(obs) - float(mdl)
        s0 += w
        s1 += w * r
        s2 += w * r * r

    if s0 <= 0.0:
        raise JointError("invalid profile weights")
    delta_m = s1 / s0
    chi2 = s2 - (s1 * s1 / s0)
    if chi2 < 0.0 and chi2 > -1.0e-12:
        chi2 = 0.0
    return float(chi2), float(delta_m)


def _profile_chi2_full_cov(
    *,
    mu_obs: Sequence[float],
    mu_model: Sequence[float],
    solve_cov: Any,
    c_inv_one: Sequence[float],
    one_dot_cinv_one: float,
) -> Tuple[float, float]:
    if len(mu_obs) != len(mu_model):
        raise JointError("mu arrays must have matching length")
    if len(mu_obs) == 0:
        raise JointError("empty SN dataset")
    if one_dot_cinv_one <= 0.0:
        raise JointError("invalid full-covariance normalization")

    r = [float(obs) - float(mdl) for obs, mdl in zip(mu_obs, mu_model)]
    c_inv_r = solve_cov(r)
    one_dot_cinv_r = _dot(c_inv_one, r)
    delta_m = one_dot_cinv_r / float(one_dot_cinv_one)
    chi2 = _dot(r, c_inv_r) - (one_dot_cinv_r * one_dot_cinv_r) / float(one_dot_cinv_one)
    if chi2 < 0.0 and chi2 > -1.0e-12:
        chi2 = 0.0
    return float(chi2), float(delta_m)


def _cdf_quantile(xs: Sequence[float], probs: Sequence[float], q: float) -> float:
    qq = min(1.0, max(0.0, float(q)))
    if len(xs) != len(probs) or len(xs) == 0:
        raise JointError("quantile inputs must be non-empty aligned arrays")
    c = 0.0
    prev_c = 0.0
    prev_x = float(xs[0])
    for idx, (x, p) in enumerate(zip(xs, probs)):
        pv = max(0.0, float(p))
        c += pv
        if c >= qq:
            xv = float(x)
            if idx == 0 or pv <= 0.0:
                return xv
            alpha = (qq - prev_c) / pv
            return prev_x + alpha * (xv - prev_x)
        prev_c = c
        prev_x = float(x)
    return float(xs[-1])


def _summary_stats(xs: Sequence[float], probs: Sequence[float]) -> Dict[str, float]:
    if len(xs) != len(probs) or len(xs) == 0:
        raise JointError("stats inputs must be non-empty aligned arrays")
    norm = float(sum(float(p) for p in probs))
    if norm <= 0.0:
        raise JointError("posterior marginal has non-positive normalization")
    w = [float(p) / norm for p in probs]
    mean = sum(float(x) * wi for x, wi in zip(xs, w))
    var = sum(((float(x) - mean) ** 2) * wi for x, wi in zip(xs, w))
    if var < 0.0 and var > -1.0e-16:
        var = 0.0
    std = math.sqrt(max(0.0, var))
    return {
        "mean": float(mean),
        "std": float(std),
        "p16": _cdf_quantile(xs, w, 0.16),
        "p50": _cdf_quantile(xs, w, 0.50),
        "p84": _cdf_quantile(xs, w, 0.84),
        "p2_5": _cdf_quantile(xs, w, 0.025),
        "p97_5": _cdf_quantile(xs, w, 0.975),
    }


def _make_toy_sn_dataset() -> SNDatasetBundle:
    z = [0.03, 0.08, 0.12, 0.18, 0.26, 0.35, 0.48, 0.62, 0.78, 0.95]
    sigma = [0.12, 0.11, 0.11, 0.10, 0.10, 0.10, 0.11, 0.11, 0.12, 0.12]
    offsets = [0.00, 0.03, -0.02, 0.01, -0.01, 0.02, -0.015, 0.01, -0.005, 0.0]
    omega_ref = 0.31
    h0_si_ref = H0_to_SI(70.0)
    z_nodes, d_l_nodes = _build_dl_table(omega_m=omega_ref, h0_si=h0_si_ref, z_max=max(z) + 0.02, n_steps=1024)
    mu: List[float] = []
    for zi, off in zip(z, offsets):
        mu.append(_mu_from_table(zi, z_nodes, d_l_nodes) + float(off))
    csv_like = "z,mu,sigma_mu\n" + "".join(
        f"{_fmt_e(zi)},{_fmt_e(mui)},{_fmt_e(si)}\n" for zi, mui, si in zip(z, mu, sigma)
    )
    meta = {
        "dataset_mode": "toy_embedded",
        "dataset_relpath": "toy_embedded_pantheon_mu.csv",
        "dataset_sha256": _sha256_bytes(csv_like.encode("utf-8")),
        "n_points": int(len(z)),
    }
    return SNDatasetBundle(z_obs=list(z), mu_obs=list(mu), sigma_mu=list(sigma), meta=meta, row_full=None)


def _make_toy_bao_dataset() -> BAODatasetBundle:
    blocks = (
        BAOBlock1D(z=0.30, y=7.90, sigma=0.18, label="TOY_BAO_DV"),
        BAOBlock2D(
            z=0.85,
            y_dm=20.50,
            y_dh=18.20,
            sigma_dm=0.45,
            sigma_dh=0.40,
            rho_dm_dh=0.10,
            label="TOY_BAO_ANISO_1",
        ),
        BAOBlock2D(
            z=1.50,
            y_dm=26.20,
            y_dh=13.10,
            sigma_dm=0.80,
            sigma_dh=0.60,
            rho_dm_dh=0.15,
            label="TOY_BAO_ANISO_2",
        ),
    )
    dataset = BAODataset(name="desi_bao_toy_embedded", blocks=blocks)
    toy_csv = "".join(
        [
            "type,label,survey,z,dv_over_rd,sigma_dv_over_rd,dm_over_rd,dh_over_rd,sigma_dm_over_rd,sigma_dh_over_rd,rho_dm_dh,values_path,cov_path\n",
            "DV_over_rd,TOY_BAO_DV,TOY,3.000000000000e-01,7.900000000000e+00,1.800000000000e-01,,,,,,,\n",
            "DM_over_rd__DH_over_rd,TOY_BAO_ANISO_1,TOY,8.500000000000e-01,,,2.050000000000e+01,1.820000000000e+01,4.500000000000e-01,4.000000000000e-01,1.000000000000e-01,,\n",
            "DM_over_rd__DH_over_rd,TOY_BAO_ANISO_2,TOY,1.500000000000e+00,,,2.620000000000e+01,1.310000000000e+01,8.000000000000e-01,6.000000000000e-01,1.500000000000e-01,,\n",
        ]
    )
    return BAODatasetBundle(
        dataset=dataset,
        relpath="toy_embedded_desi_bao.csv",
        sha256=_sha256_bytes(toy_csv.encode("utf-8")),
        mode="toy_embedded",
    )


def _load_sn_dataset(repo_root: Path, dataset_arg: Optional[str], toy_mode: bool) -> SNDatasetBundle:
    if toy_mode:
        return _make_toy_sn_dataset()

    raw = str(dataset_arg).strip() if dataset_arg is not None else ""
    if not raw:
        raw = DEFAULT_PANTHEON_DATASET
    dataset_path = _resolve_path_from_repo(repo_root, raw)
    if not dataset_path.is_file():
        raise UsageError(f"Pantheon mu dataset file not found: {dataset_path}")

    z, mu, sigma_mu, raw_meta = load_sn_mu_csv(dataset_path)
    row_full_meta = raw_meta.get("row_full")
    row_full: Optional[List[int]] = None
    if isinstance(row_full_meta, tuple):
        row_full = [int(v) for v in row_full_meta]
    elif isinstance(row_full_meta, list):
        row_full = [int(v) for v in row_full_meta]

    meta = {
        "dataset_mode": "pantheon_plus_shoes_mu_csv",
        "dataset_relpath": _relative_or_basename(dataset_path, repo_root),
        "dataset_sha256": _sha256_file(dataset_path),
        "n_points": int(len(z)),
        "has_row_full": bool(row_full is not None),
    }
    return SNDatasetBundle(
        z_obs=list(z),
        mu_obs=list(mu),
        sigma_mu=list(sigma_mu),
        meta=meta,
        row_full=row_full,
    )


def _load_bao_dataset(repo_root: Path, dataset_arg: str, toy_mode: bool) -> BAODatasetBundle:
    if toy_mode:
        return _make_toy_bao_dataset()

    dataset_path = _resolve_path_from_repo(repo_root, str(dataset_arg))
    if not dataset_path.is_file():
        raise UsageError(f"BAO dataset file not found: {dataset_path}")
    dataset = BAODataset.from_csv(dataset_path, name="desi_bao_baseline")
    return BAODatasetBundle(
        dataset=dataset,
        relpath=_relative_or_basename(dataset_path, repo_root),
        sha256=_sha256_file(dataset_path),
        mode="desi_dr1_baseline_compact",
    )


def _load_data_manifest(repo_root: Path, manifest_arg: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[Path], Optional[str]]:
    if not manifest_arg:
        return None, None, None
    path = _resolve_path_from_repo(repo_root, str(manifest_arg))
    if not path.is_file():
        raise UsageError(f"data manifest file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise UsageError(f"failed to parse data manifest JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise UsageError("data manifest must be a JSON object")
    return payload, path, _sha256_file(path)


def _verify_manifest_hash_with_candidates(
    manifest_payload: Mapping[str, Any],
    *,
    key_candidates: Sequence[str],
    observed_sha256: str,
    label: str,
) -> None:
    files = manifest_payload.get("files")
    if not isinstance(files, Mapping):
        raise UsageError("data manifest is missing 'files' object")

    entry: Optional[Mapping[str, Any]] = None
    for key in key_candidates:
        obj = files.get(key)
        if isinstance(obj, Mapping):
            entry = obj
            break
    if entry is None:
        joined = ", ".join(repr(k) for k in key_candidates)
        raise UsageError(f"data manifest is missing expected file entry for {label}; tried keys: {joined}")

    expected = entry.get("sha256")
    if not isinstance(expected, str) or len(expected.strip()) != 64:
        raise UsageError(f"data manifest sha256 is missing/invalid for {label}")
    if expected.strip().lower() != observed_sha256.lower():
        raise JointError(
            f"data manifest sha256 mismatch for {label}: expected {expected.strip().lower()} got {observed_sha256.lower()}"
        )


def _optional_matplotlib() -> Optional[Any]:
    try:  # pragma: no cover - environment dependent
        import matplotlib

        matplotlib.use("Agg")
        matplotlib.rcParams["savefig.dpi"] = 140
        matplotlib.rcParams["font.family"] = "DejaVu Sans"
        matplotlib.rcParams["path.simplify"] = False
        matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt  # type: ignore

        return plt
    except Exception:
        return None


def _save_png(fig: Any, out_path: Path) -> None:
    fig.savefig(
        str(out_path),
        format="png",
        dpi=140,
        metadata={
            "Software": "GSC phase4_triangle1_joint_sn_bao_epsilon_posterior",
            "Creation Time": "2000-01-01T00:00:00Z",
        },
    )


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def _save_png_rgb(*, width: int, height: int, rgb_rows: Sequence[bytes], out_path: Path) -> None:
    if width <= 0 or height <= 0:
        raise JointError("PNG dimensions must be positive")
    if len(rgb_rows) != height:
        raise JointError("PNG row count mismatch")
    for row in rgb_rows:
        if len(row) != width * 3:
            raise JointError("PNG row width mismatch")

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rgb_rows)
    idat = zlib.compress(raw, level=9)
    data = signature + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")
    out_path.write_bytes(data)


def _draw_line_rgb(
    image: List[List[List[int]]],
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: Tuple[int, int, int],
) -> None:
    width = len(image[0])
    height = len(image)

    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        if 0 <= x < width and 0 <= y < height:
            image[y][x][0] = color[0]
            image[y][x][1] = color[1]
            image[y][x][2] = color[2]
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _write_png_1d_fallback(*, x: Sequence[float], y: Sequence[float], out_path: Path) -> None:
    width = 880
    height = 520
    image: List[List[List[int]]] = [[[255, 255, 255] for _ in range(width)] for _ in range(height)]
    margin_left = 80
    margin_right = 24
    margin_top = 24
    margin_bottom = 72
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    x_min = float(min(x))
    x_max = float(max(x))
    y_max = float(max(y)) if y else 1.0
    if y_max <= 0.0:
        y_max = 1.0

    axis_color = (30, 30, 30)
    curve_color = (31, 119, 180)

    x_axis_y = margin_top + plot_h
    for xx in range(margin_left, margin_left + plot_w + 1):
        _draw_line_rgb(image, x0=xx, y0=x_axis_y, x1=xx, y1=x_axis_y, color=axis_color)
    for yy in range(margin_top, margin_top + plot_h + 1):
        _draw_line_rgb(image, x0=margin_left, y0=yy, x1=margin_left, y1=yy, color=axis_color)

    def px(v: float) -> int:
        if x_max == x_min:
            return margin_left + plot_w // 2
        return int(round(margin_left + (float(v) - x_min) * plot_w / (x_max - x_min)))

    def py(v: float) -> int:
        val = max(0.0, float(v))
        return int(round(margin_top + plot_h - (val / y_max) * plot_h))

    points = [(px(float(xx)), py(float(yy))) for xx, yy in zip(x, y)]
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        _draw_line_rgb(image, x0=x0, y0=y0, x1=x1, y1=y1, color=curve_color)

    rows = [bytes(ch for pix in row for ch in pix) for row in image]
    _save_png_rgb(width=width, height=height, rgb_rows=rows, out_path=out_path)


def _write_png_2d_fallback(*, posterior: Sequence[Sequence[float]], out_path: Path) -> None:
    n_rows = len(posterior)
    n_cols = len(posterior[0]) if n_rows > 0 else 0
    if n_rows == 0 or n_cols == 0:
        raise JointError("posterior grid must be non-empty")
    for row in posterior:
        if len(row) != n_cols:
            raise JointError("posterior rows must have equal length")

    width = 860
    height = 560
    image: List[List[List[int]]] = [[[255, 255, 255] for _ in range(width)] for _ in range(height)]
    margin_left = 80
    margin_right = 24
    margin_top = 24
    margin_bottom = 72
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    max_v = max(float(v) for row in posterior for v in row)
    if max_v <= 0.0:
        max_v = 1.0

    for py in range(plot_h):
        fy = py / max(1, plot_h - 1)
        i = int(round((1.0 - fy) * (n_rows - 1)))
        i = max(0, min(n_rows - 1, i))
        row = posterior[i]
        for px in range(plot_w):
            fx = px / max(1, plot_w - 1)
            j = int(round(fx * (n_cols - 1)))
            j = max(0, min(n_cols - 1, j))
            v = max(0.0, float(row[j])) / max_v
            r = int(round(30 + 210 * v))
            g = int(round(50 + 120 * (1.0 - abs(v - 0.5) * 2.0)))
            b = int(round(220 - 170 * v))
            image[margin_top + py][margin_left + px] = [r, g, b]

    axis_color = (30, 30, 30)
    x_axis_y = margin_top + plot_h
    for xx in range(margin_left, margin_left + plot_w + 1):
        _draw_line_rgb(image, x0=xx, y0=x_axis_y, x1=xx, y1=x_axis_y, color=axis_color)
    for yy in range(margin_top, margin_top + plot_h + 1):
        _draw_line_rgb(image, x0=margin_left, y0=yy, x1=margin_left, y1=yy, color=axis_color)

    rows = [bytes(ch for pix in row for ch in pix) for row in image]
    _save_png_rgb(width=width, height=height, rgb_rows=rows, out_path=out_path)


def _write_png_1d(*, x: Sequence[float], y: Sequence[float], out_path: Path, title: str) -> str:
    plt = _optional_matplotlib()
    if plt is None:
        _write_png_1d_fallback(x=x, y=y, out_path=out_path)
        return "fallback"

    fig, ax = plt.subplots(figsize=(6.0, 4.0), dpi=140)
    ax.plot([float(v) for v in x], [float(v) for v in y], color="#1f77b4", linewidth=2.0)
    ax.set_title(str(title))
    ax.set_xlabel("epsilon_em")
    ax.set_ylabel("marginal posterior")
    ax.grid(True, linestyle=":", linewidth=0.7, alpha=0.6)
    fig.tight_layout()
    _save_png(fig, out_path)
    plt.close(fig)
    return "matplotlib"


def _write_png_2d(
    *,
    eps_grid: Sequence[float],
    om_grid: Sequence[float],
    posterior: Sequence[Sequence[float]],
    out_path: Path,
    title: str,
) -> str:
    plt = _optional_matplotlib()
    if plt is None:
        _write_png_2d_fallback(posterior=posterior, out_path=out_path)
        return "fallback"

    fig, ax = plt.subplots(figsize=(6.2, 4.6), dpi=140)
    mesh = ax.imshow(
        [[float(v) for v in row] for row in posterior],
        origin="lower",
        aspect="auto",
        extent=[
            float(min(eps_grid)),
            float(max(eps_grid)),
            float(min(om_grid)),
            float(max(om_grid)),
        ],
        cmap="viridis",
        interpolation="nearest",
    )
    ax.set_title(str(title))
    ax.set_xlabel("epsilon_em")
    ax.set_ylabel("Omega_m")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("posterior probability")
    fig.tight_layout()
    _save_png(fig, out_path)
    plt.close(fig)
    return "matplotlib"


def _count_forbidden(text: str) -> int:
    return int(sum(text.count(token) for token in ABS_TOKENS))


def _render_markdown(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Triangle-1 Joint SN+BAO Epsilon Posterior (Phase-4 M157)")
    lines.append("")
    lines.append("Deterministic joint low-z artifact combining Pantheon+ SN and DESI BAO baseline leg.")
    lines.append("")

    lines.append("## Run Summary")
    lines.append("")
    lines.append(f"- run_mode: `{payload.get('run_mode')}`")
    lines.append(f"- covariance_mode: `{payload.get('covariance_mode')}`")
    lines.append(f"- toy_mode: `{bool(payload.get('toy_mode'))}`")
    lines.append(f"- plot_backend: `{payload.get('plot_backend')}`")
    lines.append("")

    results = payload.get("results", {}) if isinstance(payload.get("results"), Mapping) else {}
    best = results.get("best_fit", {}) if isinstance(results.get("best_fit"), Mapping) else {}
    eps = results.get("epsilon_em", {}) if isinstance(results.get("epsilon_em"), Mapping) else {}
    om = results.get("omega_m", {}) if isinstance(results.get("omega_m"), Mapping) else {}

    lines.append("## Best Fit")
    lines.append("")
    lines.append(f"- chi2_min: `{float(best.get('chi2_min', float('nan'))):.6f}`")
    lines.append(f"- ndof_joint: `{int(best.get('ndof_joint', -1))}`")
    lines.append(f"- omega_m_best: `{float(best.get('omega_m', float('nan'))):.6f}`")
    lines.append(f"- epsilon_em_best: `{float(best.get('epsilon_em', float('nan'))):.6f}`")
    lines.append(f"- rd_m_best: `{float(best.get('rd_m', float('nan'))):.12e}`")
    lines.append("")

    lines.append("## Posterior Summaries")
    lines.append("")
    lines.append(
        f"- epsilon_em mean/std: `{float(eps.get('mean', float('nan'))):.6e}` / `{float(eps.get('std', float('nan'))):.6e}`"
    )
    lines.append(
        f"- epsilon_em p16/p50/p84: `{float(eps.get('p16', float('nan'))):.6e}`, `{float(eps.get('p50', float('nan'))):.6e}`, `{float(eps.get('p84', float('nan'))):.6e}`"
    )
    lines.append(
        f"- omega_m mean/std: `{float(om.get('mean', float('nan'))):.6e}` / `{float(om.get('std', float('nan'))):.6e}`"
    )
    lines.append("")

    lines.append("## Scope and Assumptions")
    lines.append("")
    lines.append("- Inference-layer intervention only: redshift remapping enters cosmology inference, not lightcurve training.")
    lines.append("- BAO leg treats `r_d` as nuisance (`profile` or `fixed`), explicitly recorded in report.")
    lines.append("- DR1 baseline compact products for deterministic reviewer checks; DR2 BAO/cosmology products are robustness checks when public/available in chosen tooling.")
    lines.append("- This artifact is a joint low-z scaffold, not a full global likelihood claim.")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_text(payload: Mapping[str, Any]) -> str:
    results = payload.get("results", {}) if isinstance(payload.get("results"), Mapping) else {}
    best = results.get("best_fit", {}) if isinstance(results.get("best_fit"), Mapping) else {}
    lines = [
        f"schema={payload.get('schema')}",
        f"run_mode={payload.get('run_mode')}",
        f"covariance_mode={payload.get('covariance_mode')}",
        f"toy_mode={bool(payload.get('toy_mode'))}",
        f"plot_backend={payload.get('plot_backend')}",
        f"chi2_min={float(best.get('chi2_min', float('nan'))):.6f}",
        f"omega_m_best={float(best.get('omega_m', float('nan'))):.6f}",
        f"epsilon_em_best={float(best.get('epsilon_em', float('nan'))):.6f}",
        f"rd_m_best={float(best.get('rd_m', float('nan'))):.12e}",
        "report_json=TRIANGLE1_JOINT_SN_BAO_REPORT.json",
    ]
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic Triangle-1 joint SN+BAO epsilon posterior.")
    ap.add_argument("--repo-root", default="v11.0.0")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--format", choices=("json", "text"), default="json")
    ap.add_argument("--run-mode", choices=("demo", "paper_grade"), default="demo")
    ap.add_argument("--deterministic", choices=(0, 1), type=int, default=1)
    ap.add_argument("--created-utc", type=int, default=None)
    ap.add_argument("--toy", choices=(0, 1), type=int, default=0)

    ap.add_argument("--pantheon-mu-csv", default=None)
    ap.add_argument("--pantheon-covariance", default=None)
    ap.add_argument("--pantheon-data-manifest", default=None)
    ap.add_argument(
        "--covariance-mode",
        choices=("diag_only_proof_of_concept", "full"),
        default="diag_only_proof_of_concept",
    )

    ap.add_argument("--bao-baseline-csv", default=DEFAULT_BAO_DATASET)
    ap.add_argument("--bao-data-manifest", default=None)
    ap.add_argument("--bao-rd-mode", choices=("profile", "fixed"), default="profile")
    ap.add_argument("--bao-rd-m-fixed", type=float, default=None)

    ap.add_argument("--H0-km-s-Mpc", type=float, default=70.0)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)
    ap.add_argument("--N-eff", type=float, default=3.046)

    ap.add_argument("--omega-m-min", type=float, default=0.15)
    ap.add_argument("--omega-m-max", type=float, default=0.45)
    ap.add_argument("--omega-m-steps", type=int, default=41)
    ap.add_argument("--epsilon-min", type=float, default=-0.12)
    ap.add_argument("--epsilon-max", type=float, default=0.12)
    ap.add_argument("--epsilon-steps", type=int, default=61)
    ap.add_argument("--integration-n", type=int, default=3000)
    ap.add_argument("--pivot-z", type=float, default=0.5)
    ap.add_argument("--emit-plots", choices=(0, 1), type=int, default=1)
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)

        repo_root = Path(str(args.repo_root)).expanduser().resolve()
        if not repo_root.is_dir():
            raise UsageError(f"--repo-root directory not found: {repo_root}")

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        deterministic_mode = bool(int(args.deterministic))
        if args.created_utc is not None:
            created_epoch = int(args.created_utc)
        elif deterministic_mode:
            created_epoch = DEFAULT_CREATED_UTC_EPOCH
        else:
            created_epoch = int(time.time())
        created_utc = _to_iso_utc(created_epoch)

        run_mode = str(args.run_mode)
        toy_mode = bool(int(args.toy))
        covariance_mode = str(args.covariance_mode)
        emit_plots = bool(int(args.emit_plots))

        if run_mode == "paper_grade":
            if covariance_mode != "full":
                raise UsageError("--run-mode paper_grade requires --covariance-mode full")
            if not args.pantheon_data_manifest:
                raise UsageError("--run-mode paper_grade requires --pantheon-data-manifest")
            if _optional_matplotlib() is None:
                raise UsageError("--run-mode paper_grade requires matplotlib for paper-grade plot outputs")

        h0_km = _require_finite(float(args.H0_km_s_Mpc), name="H0_km_s_Mpc")
        if h0_km <= 0.0:
            raise UsageError("--H0-km-s-Mpc must be > 0")
        h0_si = H0_to_SI(h0_km)

        omega_grid = _linear_grid(float(args.omega_m_min), float(args.omega_m_max), int(args.omega_m_steps), name="omega_m")
        epsilon_grid = _linear_grid(float(args.epsilon_min), float(args.epsilon_max), int(args.epsilon_steps), name="epsilon")
        if min(epsilon_grid) <= -0.95:
            raise UsageError("--epsilon-min must be > -0.95 for stable mapping")
        if int(args.integration_n) < 32:
            raise UsageError("--integration-n must be >= 32")

        pantheon_manifest_payload, pantheon_manifest_path, pantheon_manifest_sha = _load_data_manifest(
            repo_root, args.pantheon_data_manifest
        )
        bao_manifest_payload, bao_manifest_path, bao_manifest_sha = _load_data_manifest(repo_root, args.bao_data_manifest)

        pantheon_mu_arg = str(args.pantheon_mu_csv).strip() if args.pantheon_mu_csv is not None else ""
        if not pantheon_mu_arg and pantheon_manifest_payload is not None:
            files = pantheon_manifest_payload.get("files")
            if isinstance(files, Mapping):
                mu_entry = files.get("mu")
                if isinstance(mu_entry, Mapping):
                    from_manifest = _resolve_from_manifest_filename(
                        repo_root,
                        pantheon_manifest_path,
                        str(mu_entry.get("filename")) if mu_entry.get("filename") is not None else None,
                    )
                    if from_manifest is not None:
                        pantheon_mu_arg = str(from_manifest)
        if not pantheon_mu_arg:
            pantheon_mu_arg = DEFAULT_PANTHEON_DATASET

        sn_bundle = _load_sn_dataset(repo_root, pantheon_mu_arg, toy_mode)
        bao_bundle = _load_bao_dataset(repo_root, str(args.bao_baseline_csv), toy_mode)

        if run_mode == "paper_grade" and not toy_mode:
            if str(args.bao_baseline_csv).strip() != DEFAULT_BAO_DATASET and bao_manifest_payload is None:
                raise UsageError(
                    "--run-mode paper_grade requires --bao-data-manifest when using non-default BAO baseline inputs"
                )

        if pantheon_manifest_payload is not None and not toy_mode:
            schema_id = pantheon_manifest_payload.get("schema")
            if not isinstance(schema_id, str) or schema_id != PANTHEON_FETCH_SCHEMA:
                raise UsageError(f"pantheon data manifest schema must be {PANTHEON_FETCH_SCHEMA!r}")
            _verify_manifest_hash_with_candidates(
                pantheon_manifest_payload,
                key_candidates=("mu", Path(str(pantheon_mu_arg)).name, sn_bundle.meta["dataset_relpath"]),
                observed_sha256=str(sn_bundle.meta["dataset_sha256"]),
                label="pantheon_mu",
            )

        if bao_manifest_payload is not None and not toy_mode:
            schema_id = bao_manifest_payload.get("schema")
            if not isinstance(schema_id, str) or schema_id != DESI_FETCH_SCHEMA:
                raise UsageError(f"bao data manifest schema must be {DESI_FETCH_SCHEMA!r}")
            _verify_manifest_hash_with_candidates(
                bao_manifest_payload,
                key_candidates=(Path(str(args.bao_baseline_csv)).name, bao_bundle.relpath),
                observed_sha256=bao_bundle.sha256,
                label="bao_baseline",
            )

        solve_cov: Optional[Any] = None
        c_inv_one: Optional[List[float]] = None
        one_dot_cinv_one: Optional[float] = None
        cov_relpath: Optional[str] = None
        cov_sha256: Optional[str] = None
        cov_dim: Optional[int] = None

        if covariance_mode == "full":
            cov_arg = str(args.pantheon_covariance).strip() if args.pantheon_covariance is not None else ""
            if not cov_arg and pantheon_manifest_payload is not None:
                files = pantheon_manifest_payload.get("files")
                if isinstance(files, Mapping):
                    cov_entry = files.get("cov")
                    if isinstance(cov_entry, Mapping):
                        from_manifest = _resolve_from_manifest_filename(
                            repo_root,
                            pantheon_manifest_path,
                            str(cov_entry.get("filename")) if cov_entry.get("filename") is not None else None,
                        )
                        if from_manifest is not None:
                            cov_arg = str(from_manifest)
            if not cov_arg:
                raise UsageError("--covariance-mode full requires --pantheon-covariance (or manifest-resolvable cov filename)")

            cov_path = _resolve_path_from_repo(repo_root, cov_arg)
            cov_relpath = _relative_or_basename(cov_path, repo_root)
            cov_sha256 = _sha256_file(cov_path)
            cov_matrix = _load_covariance_matrix(cov_path)
            if sn_bundle.row_full is not None:
                cov_matrix = _subset_covariance(cov_matrix, sn_bundle.row_full)
            if len(cov_matrix) != len(sn_bundle.z_obs):
                raise JointError(
                    f"covariance dimension mismatch: got {len(cov_matrix)} expected {len(sn_bundle.z_obs)} after optional row_full slicing"
                )
            cov_dim = int(len(cov_matrix))
            solve_cov = _make_cov_solver(cov_matrix)
            c_inv_one = solve_cov([1.0 for _ in range(cov_dim)])
            one_dot_cinv_one = _dot([1.0 for _ in range(cov_dim)], c_inv_one)
            if one_dot_cinv_one <= 0.0:
                raise JointError("invalid full-covariance normalization scalar")

            if pantheon_manifest_payload is not None and not toy_mode:
                _verify_manifest_hash_with_candidates(
                    pantheon_manifest_payload,
                    key_candidates=("cov", Path(cov_arg).name, cov_relpath),
                    observed_sha256=cov_sha256,
                    label="pantheon_covariance",
                )

        rd_mode = str(args.bao_rd_mode)
        rd_m_fixed = None if args.bao_rd_m_fixed is None else _require_finite(float(args.bao_rd_m_fixed), name="bao_rd_m_fixed")
        if rd_mode == "fixed":
            if rd_m_fixed is None:
                raise UsageError("--bao-rd-mode fixed requires --bao-rd-m-fixed")
            if rd_m_fixed <= 0.0:
                raise UsageError("--bao-rd-m-fixed must be > 0")

        z_obs = list(sn_bundle.z_obs)
        mu_obs = list(sn_bundle.mu_obs)
        sigma_mu = list(sn_bundle.sigma_mu)
        if len(z_obs) < 3:
            raise JointError("SN dataset must contain at least 3 points")

        z_gr_by_eps: List[List[float]] = []
        z_max_gr = 0.0
        for eps in epsilon_grid:
            row: List[float] = []
            for z in z_obs:
                z_gr = _z_gr_from_z_obs(float(z), float(eps))
                if z_gr < 0.0:
                    raise JointError("z_gr mapping yielded negative redshift; adjust epsilon range")
                row.append(float(z_gr))
                z_max_gr = max(z_max_gr, float(z_gr))
            z_gr_by_eps.append(row)

        pivot_z = _require_finite(float(args.pivot_z), name="pivot_z")
        if pivot_z < 0.0:
            raise UsageError("--pivot-z must be >= 0")
        z_max_gr = max(z_max_gr, pivot_z, max(z_obs))

        chi2_sn_grid: List[List[float]] = []
        chi2_bao_grid: List[List[float]] = []
        chi2_joint_grid: List[List[float]] = []
        delta_m_grid: List[List[float]] = []
        rd_grid: List[List[float]] = []
        rows: List[RowResult] = []

        ndof_sn_ref = int(len(z_obs) - 1)
        ndof_bao_ref: Optional[int] = None

        chi2_joint_min = float("inf")
        best_i = 0
        best_j = 0

        for i_om, omega_m in enumerate(omega_grid):
            z_nodes, d_l_nodes = _build_dl_table(
                omega_m=float(omega_m),
                h0_si=h0_si,
                z_max=z_max_gr + 1.0e-4,
                n_steps=int(args.integration_n),
            )

            row_sn: List[float] = []
            row_bao: List[float] = []
            row_joint: List[float] = []
            row_dm: List[float] = []
            row_rd: List[float] = []

            for j_eps, z_gr_list in enumerate(z_gr_by_eps):
                mu_model = [_mu_from_table(float(z_gr), z_nodes, d_l_nodes) for z_gr in z_gr_list]
                if covariance_mode == "full":
                    if solve_cov is None or c_inv_one is None or one_dot_cinv_one is None:
                        raise JointError("internal full-covariance solver is not initialized")
                    chi2_sn, delta_m = _profile_chi2_full_cov(
                        mu_obs=mu_obs,
                        mu_model=mu_model,
                        solve_cov=solve_cov,
                        c_inv_one=c_inv_one,
                        one_dot_cinv_one=one_dot_cinv_one,
                    )
                else:
                    chi2_sn, delta_m = _profile_chi2(mu_obs=mu_obs, sigma_mu=sigma_mu, mu_model=mu_model)

                model = EpsilonMappedLCDMHistory(
                    h0_si=float(h0_si),
                    omega_m=float(omega_m),
                    epsilon_em=float(epsilon_grid[j_eps]),
                    Tcmb_K=float(args.Tcmb_K),
                    N_eff=float(args.N_eff),
                )
                if rd_mode == "profile":
                    bao_res = bao_bundle.dataset.chi2(model, fit_rd=True)
                else:
                    bao_res = bao_bundle.dataset.chi2(model, rd_m=float(rd_m_fixed))
                chi2_bao = float(bao_res.chi2)
                ndof_bao = int(bao_res.ndof)
                rd_m = float(bao_res.params.get("rd_m", rd_m_fixed if rd_m_fixed is not None else float("nan")))

                if not math.isfinite(chi2_bao):
                    raise JointError("non-finite BAO chi2 encountered")
                if not math.isfinite(rd_m) or rd_m <= 0.0:
                    raise JointError("non-physical rd_m encountered")
                if ndof_bao_ref is None:
                    ndof_bao_ref = ndof_bao
                elif ndof_bao != ndof_bao_ref:
                    raise JointError("BAO ndof changed across grid; unexpected setup")

                chi2_joint = float(chi2_sn + chi2_bao)
                ndof_joint = int(ndof_sn_ref + ndof_bao)

                row_sn.append(float(chi2_sn))
                row_bao.append(float(chi2_bao))
                row_joint.append(float(chi2_joint))
                row_dm.append(float(delta_m))
                row_rd.append(float(rd_m))
                rows.append(
                    RowResult(
                        omega_m=float(omega_m),
                        epsilon_em=float(epsilon_grid[j_eps]),
                        chi2_joint=float(chi2_joint),
                        chi2_sn=float(chi2_sn),
                        chi2_bao=float(chi2_bao),
                        ndof_joint=int(ndof_joint),
                        ndof_sn=int(ndof_sn_ref),
                        ndof_bao=int(ndof_bao),
                        delta_m=float(delta_m),
                        rd_m=float(rd_m),
                    )
                )

                if chi2_joint < chi2_joint_min:
                    chi2_joint_min = float(chi2_joint)
                    best_i = int(i_om)
                    best_j = int(j_eps)

            chi2_sn_grid.append(row_sn)
            chi2_bao_grid.append(row_bao)
            chi2_joint_grid.append(row_joint)
            delta_m_grid.append(row_dm)
            rd_grid.append(row_rd)

        if not rows or not math.isfinite(chi2_joint_min):
            raise JointError("failed to compute finite joint chi2 grid")

        weights_2d: List[List[float]] = []
        norm = 0.0
        for row in chi2_joint_grid:
            w_row: List[float] = []
            for chi2 in row:
                exponent = -0.5 * (float(chi2) - chi2_joint_min)
                w = 0.0 if exponent < -745.0 else math.exp(exponent)
                w_row.append(float(w))
                norm += float(w)
            weights_2d.append(w_row)
        if norm <= 0.0:
            raise JointError("joint posterior normalization is non-positive")

        posterior_2d: List[List[float]] = []
        for row in weights_2d:
            posterior_2d.append([float(w) / norm for w in row])

        p_eps = [0.0 for _ in epsilon_grid]
        p_om = [0.0 for _ in omega_grid]
        for i in range(len(omega_grid)):
            for j in range(len(epsilon_grid)):
                pv = float(posterior_2d[i][j])
                p_om[i] += pv
                p_eps[j] += pv

        eps_stats = _summary_stats(epsilon_grid, p_eps)
        om_stats = _summary_stats(omega_grid, p_om)

        best = min(rows, key=lambda r: (r.chi2_joint, r.omega_m, r.epsilon_em))
        eps_zero_idx = min(range(len(epsilon_grid)), key=lambda j: abs(float(epsilon_grid[j])))
        chi2_joint_eps0 = min(float(chi2_joint_grid[i][eps_zero_idx]) for i in range(len(omega_grid)))

        z_nodes_best, d_l_nodes_best = _build_dl_table(
            omega_m=float(best.omega_m),
            h0_si=h0_si,
            z_max=max(z_max_gr, pivot_z) + 1.0e-4,
            n_steps=int(args.integration_n),
        )
        eps_ref = float(eps_stats["p50"])
        z_gr_pivot = _z_gr_from_z_obs(pivot_z, eps_ref)
        mu_base_pivot = _mu_from_table(pivot_z, z_nodes_best, d_l_nodes_best)
        mu_eps_pivot = _mu_from_table(z_gr_pivot, z_nodes_best, d_l_nodes_best)
        delta_mu_pivot = float(mu_eps_pivot - mu_base_pivot)
        h0_ratio = float(10.0 ** (-delta_mu_pivot / 5.0))

        row_digest_lines: List[str] = []
        for i_om, omega_m in enumerate(omega_grid):
            for j_eps, epsilon in enumerate(epsilon_grid):
                row_digest_lines.append(
                    ",".join(
                        (
                            _fmt_e(omega_m),
                            _fmt_e(epsilon),
                            _fmt_e(chi2_joint_grid[i_om][j_eps]),
                            _fmt_e(chi2_sn_grid[i_om][j_eps]),
                            _fmt_e(chi2_bao_grid[i_om][j_eps]),
                            _fmt_e(delta_m_grid[i_om][j_eps]),
                            _fmt_e(rd_grid[i_om][j_eps]),
                            _fmt_e(posterior_2d[i_om][j_eps]),
                        )
                    )
                    + "\n"
                )
        joint_grid_digest = _sha256_bytes("".join(row_digest_lines).encode("utf-8"))
        epsilon_marginal_digest = _sha256_bytes(
            "".join(f"{_fmt_e(eps)},{_fmt_e(prob)}\n" for eps, prob in zip(epsilon_grid, p_eps)).encode("utf-8")
        )

        if not emit_plots:
            raise UsageError("--emit-plots 0 is no longer supported; plot artifacts are mandatory")

        plot_1d_path = outdir / "epsilon_posterior_1d.png"
        plot_2d_path = outdir / "omega_m_vs_epsilon.png"
        backend_1d = _write_png_1d(
            x=epsilon_grid,
            y=p_eps,
            out_path=plot_1d_path,
            title="Triangle-1 joint epsilon_em marginal (SN+BAO)",
        )
        backend_2d = _write_png_2d(
            eps_grid=epsilon_grid,
            om_grid=omega_grid,
            posterior=posterior_2d,
            out_path=plot_2d_path,
            title="Triangle-1 joint posterior in (omega_m, epsilon_em)",
        )
        plot_backend = "matplotlib" if backend_1d == "matplotlib" and backend_2d == "matplotlib" else "fallback"

        assumptions = {
            "intervention_level": "inference_layer_only",
            "epsilon_mapping": "1+z_em=sigma_ratio^(1+epsilon_em), epsilon_gr=0, 1+z_gr=(1+z_em)^(1/(1+epsilon_em))",
            "sn_lightcurve_training": "unchanged (no retraining in this artifact)",
            "bao_rd_handling": "rd nuisance profiled when bao_rd_mode=profile; fixed only when explicitly requested",
            "h0_handling": "H0 fixed for shape at input value; SN absolute scale absorbed via profiled intercept delta_M",
        }

        inputs_payload: Dict[str, Any] = {
            "pantheon": {
                "dataset_mode": str(sn_bundle.meta.get("dataset_mode", "")),
                "dataset_relpath": str(sn_bundle.meta.get("dataset_relpath", "")),
                "dataset_sha256": str(sn_bundle.meta.get("dataset_sha256", "")),
                "n_points": int(sn_bundle.meta.get("n_points", len(sn_bundle.z_obs))),
            },
            "bao": {
                "dataset_mode": str(bao_bundle.mode),
                "dataset_relpath": str(bao_bundle.relpath),
                "dataset_sha256": str(bao_bundle.sha256),
            },
            "grid": {
                "omega_m_min": float(min(omega_grid)),
                "omega_m_max": float(max(omega_grid)),
                "omega_m_steps": int(len(omega_grid)),
                "epsilon_min": float(min(epsilon_grid)),
                "epsilon_max": float(max(epsilon_grid)),
                "epsilon_steps": int(len(epsilon_grid)),
            },
            "bao_rd_mode": str(rd_mode),
            "bao_rd_m_fixed": None if rd_m_fixed is None else float(rd_m_fixed),
            "H0_km_s_Mpc": float(h0_km),
            "H0_si": float(h0_si),
            "Tcmb_K": float(args.Tcmb_K),
            "N_eff": float(args.N_eff),
            "covariance_mode": covariance_mode,
            "integration_n": int(args.integration_n),
            "pivot_z": float(pivot_z),
        }
        if cov_relpath is not None and cov_sha256 is not None:
            inputs_payload["pantheon"]["covariance_relpath"] = str(cov_relpath)
            inputs_payload["pantheon"]["covariance_sha256"] = str(cov_sha256)
            inputs_payload["pantheon"]["covariance_n"] = int(cov_dim) if cov_dim is not None else None

        if pantheon_manifest_payload is not None and pantheon_manifest_path is not None and pantheon_manifest_sha is not None:
            inputs_payload["pantheon_manifest"] = {
                "schema": str(pantheon_manifest_payload.get("schema", "")),
                "relpath": _relative_or_basename(pantheon_manifest_path, repo_root),
                "sha256": str(pantheon_manifest_sha),
            }
        if bao_manifest_payload is not None and bao_manifest_path is not None and bao_manifest_sha is not None:
            inputs_payload["bao_manifest"] = {
                "schema": str(bao_manifest_payload.get("schema", "")),
                "relpath": _relative_or_basename(bao_manifest_path, repo_root),
                "sha256": str(bao_manifest_sha),
            }

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "status": "ok",
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "deterministic_mode": bool(deterministic_mode),
            "run_mode": run_mode,
            "toy_mode": bool(toy_mode),
            "plot_backend": plot_backend,
            "repo_version_dir": str(repo_root.name),
            "paths_redacted": True,
            "covariance_mode": covariance_mode,
            "inputs": inputs_payload,
            "assumptions": assumptions,
            "results": {
                "best_fit": {
                    "chi2_min": float(best.chi2_joint),
                    "chi2_sn": float(best.chi2_sn),
                    "chi2_bao": float(best.chi2_bao),
                    "ndof_joint": int(best.ndof_joint),
                    "ndof_sn": int(best.ndof_sn),
                    "ndof_bao": int(best.ndof_bao),
                    "omega_m": float(best.omega_m),
                    "epsilon_em": float(best.epsilon_em),
                    "rd_m": float(best.rd_m),
                    "delta_M_profiled": float(best.delta_m),
                },
                "epsilon_em": {
                    **eps_stats,
                    "best_fit": float(best.epsilon_em),
                },
                "omega_m": {
                    **om_stats,
                    "best_fit": float(best.omega_m),
                },
                "h0_equivalent_shift_at_pivot": {
                    "pivot_z_obs": float(pivot_z),
                    "epsilon_em_reference": float(eps_ref),
                    "z_gr_at_pivot": float(z_gr_pivot),
                    "delta_mu_at_pivot": float(delta_mu_pivot),
                    "h0_ratio_equivalent": float(h0_ratio),
                    "note": "Approximate SN-only diagnostic at fixed best-fit omega_m; no absolute H0 inference without external calibration.",
                },
            },
            "diagnostics": {
                "chi2_at_nearest_epsilon_zero": float(chi2_joint_eps0),
                "delta_chi2_vs_epsilon_zero": float(best.chi2_joint - chi2_joint_eps0),
                "nearest_epsilon_zero_value": float(epsilon_grid[eps_zero_idx]),
            },
            "digests": {
                "joint_grid_sha256": joint_grid_digest,
                "epsilon_marginal_sha256": epsilon_marginal_digest,
            },
            "artifacts": [],
            "portability": {
                "forbidden_absolute_path_match_count": 0,
            },
            **_snapshot_fingerprint(repo_root),
        }

        report_json = outdir / "TRIANGLE1_JOINT_SN_BAO_REPORT.json"
        report_md = outdir / "TRIANGLE1_JOINT_SN_BAO_REPORT.md"

        markdown_text = _render_markdown(payload)
        report_md.write_text(markdown_text, encoding="utf-8")

        artifacts: List[Dict[str, str]] = []
        for rel, kind in (
            ("epsilon_posterior_1d.png", "plot"),
            ("omega_m_vs_epsilon.png", "plot"),
            ("TRIANGLE1_JOINT_SN_BAO_REPORT.md", "report_markdown"),
            ("TRIANGLE1_JOINT_SN_BAO_REPORT.json", "report_json"),
        ):
            p = outdir / rel
            row: Dict[str, str] = {"filename": rel, "kind": kind}
            if p.is_file() and rel != "TRIANGLE1_JOINT_SN_BAO_REPORT.json":
                row["sha256"] = _sha256_file(p)
            artifacts.append(row)
        payload["artifacts"] = sorted(artifacts, key=lambda row: str(row.get("filename", "")))

        json_text = _json_pretty(payload)
        abs_count = _count_forbidden(json_text) + _count_forbidden(markdown_text)
        payload["portability"]["forbidden_absolute_path_match_count"] = int(abs_count)
        json_text = _json_pretty(payload)
        report_json.write_text(json_text, encoding="utf-8")

        if str(args.format) == "json":
            print(json_text, end="")
        else:
            print(_render_text(payload), end="")
        return 0

    except (UsageError, JointError) as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
