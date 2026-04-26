#!/usr/bin/env python3
"""Deterministic Pantheon+ SN-only epsilon posterior (Phase-4 M150 / 4B.3 scaffold)."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import struct
import sys
import time
import zlib
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.datasets.sn import load_sn_mu_csv  # noqa: E402
from gsc.measurement_model import C_SI, H0_to_SI, distance_modulus_from_D_L  # noqa: E402


TOOL = "phase4_pantheon_plus_epsilon_posterior"
TOOL_VERSION = "m155-v2"
SCHEMA = "phase4_pantheon_plus_epsilon_posterior_report_v2"
FAIL_MARKER = "PHASE4_PANTHEON_EPSILON_POSTERIOR_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")
FETCH_MANIFEST_SCHEMA = "phase4_pantheon_plus_fetch_manifest_v1"


class UsageError(Exception):
    """CLI usage/configuration error."""


class PosteriorError(Exception):
    """Posterior build/runtime error."""


@dataclass(frozen=True)
class DatasetBundle:
    z_obs: List[float]
    mu_obs: List[float]
    sigma_mu: List[float]
    meta: Dict[str, Any]
    row_full: Optional[List[int]]


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
    token = []
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
                    raise PosteriorError(f"non-numeric token in covariance file {path.name}: {tok!r}") from exc
    if not values:
        raise PosteriorError(f"empty covariance file: {path.name}")

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
        raise PosteriorError(
            f"unable to infer covariance matrix layout for {path.name}; provide full N*N or triangular values (optionally with leading N)"
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
        raise PosteriorError(
            f"covariance layout mismatch for {path.name}; got {len(raw_vals)} values after optional leading N"
        )
    return mat


def _subset_covariance(cov: Sequence[Sequence[float]], indices: Sequence[int]) -> List[List[float]]:
    n = len(cov)
    if n == 0:
        raise PosteriorError("covariance matrix is empty")
    idx = [int(v) for v in indices]
    if len(set(idx)) != len(idx):
        raise PosteriorError("row_full indices must be unique")
    if min(idx) < 0 or max(idx) >= n:
        raise PosteriorError("row_full indices are out of covariance bounds")
    return [[float(cov[i][j]) for j in idx] for i in idx]


def _cholesky_factor(cov: Sequence[Sequence[float]]) -> List[List[float]]:
    n = len(cov)
    if n == 0:
        raise PosteriorError("covariance matrix is empty")
    for row in cov:
        if len(row) != n:
            raise PosteriorError("covariance matrix must be square")

    l: List[List[float]] = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = float(cov[i][j])
            for k in range(j):
                s -= l[i][k] * l[j][k]
            if i == j:
                if s <= 0.0:
                    raise PosteriorError("covariance matrix is not positive definite")
                l[i][j] = math.sqrt(s)
            else:
                denom = l[j][j]
                if denom == 0.0:
                    raise PosteriorError("covariance decomposition failure")
                l[i][j] = s / denom
    return l


def _solve_cholesky(l: Sequence[Sequence[float]], b: Sequence[float]) -> List[float]:
    n = len(l)
    if len(b) != n:
        raise PosteriorError("solve vector length mismatch")
    y = [0.0 for _ in range(n)]
    for i in range(n):
        s = float(b[i])
        for k in range(i):
            s -= float(l[i][k]) * y[k]
        denom = float(l[i][i])
        if denom == 0.0:
            raise PosteriorError("singular covariance factor (forward solve)")
        y[i] = s / denom

    x = [0.0 for _ in range(n)]
    for i in range(n - 1, -1, -1):
        s = y[i]
        for k in range(i + 1, n):
            s -= float(l[k][i]) * x[k]
        denom = float(l[i][i])
        if denom == 0.0:
            raise PosteriorError("singular covariance factor (back solve)")
        x[i] = s / denom
    return x


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise PosteriorError("dot length mismatch")
    return float(sum(float(x) * float(y) for x, y in zip(a, b)))


def _make_cov_solver(cov: Sequence[Sequence[float]]) -> Any:
    n = len(cov)
    np = _optional_numpy()
    if np is not None:
        arr = np.asarray(cov, dtype=float)
        if arr.shape != (n, n):
            raise PosteriorError("covariance matrix must be square")
        try:
            l_np = np.linalg.cholesky(arr)
        except Exception as exc:
            raise PosteriorError("covariance matrix is not positive definite") from exc

        def solve(vec: Sequence[float]) -> List[float]:
            vv = np.asarray(vec, dtype=float)
            if vv.shape != (n,):
                raise PosteriorError("solve vector length mismatch")
            y = np.linalg.solve(l_np, vv)
            x = np.linalg.solve(l_np.T, y)
            return [float(v) for v in x.tolist()]

        return solve

    if n > 256:
        raise PosteriorError(
            "full covariance mode without numpy is only supported for small matrices (n<=256); install numpy for large Pantheon+ covariance runs"
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
        return path.relative_to(repo_root).as_posix()
    except Exception:
        return path.name


def _linear_grid(vmin: float, vmax: float, n: int, *, name: str) -> List[float]:
    if int(n) < 2:
        raise UsageError(f"{name} grid count must be >= 2")
    lo = _require_finite(vmin, name=f"{name}_min")
    hi = _require_finite(vmax, name=f"{name}_max")
    if hi < lo:
        raise UsageError(f"{name}_max must be >= {name}_min")
    if int(n) == 2:
        return [float(lo), float(hi)]
    step = (hi - lo) / float(int(n) - 1)
    return [float(lo + i * step) for i in range(int(n))]


def _z_gr_from_z_obs(z_obs: float, epsilon_em: float) -> float:
    z_val = _require_finite(z_obs, name="z_obs")
    eps = _require_finite(epsilon_em, name="epsilon_em")
    denom = 1.0 + eps
    if abs(denom) < 1.0e-12:
        raise PosteriorError("epsilon_em too close to -1 makes z_gr mapping undefined")
    one_plus_z_obs = 1.0 + z_val
    if one_plus_z_obs <= 0.0:
        raise PosteriorError("observed z must satisfy 1+z>0")
    return float(one_plus_z_obs ** (1.0 / denom) - 1.0)


def _build_dl_table(
    *,
    omega_m: float,
    h0_si: float,
    z_max: float,
    n_steps: int,
) -> Tuple[List[float], List[float]]:
    om = _require_finite(omega_m, name="omega_m")
    if not (0.0 < om < 1.0):
        raise PosteriorError(f"omega_m must satisfy 0<omega_m<1, got {om}")
    h0 = _require_finite(h0_si, name="h0_si")
    if h0 <= 0.0:
        raise PosteriorError("h0_si must be > 0")
    z_hi = max(1.0e-6, _require_finite(z_max, name="z_max"))
    if z_hi < 0.0:
        raise PosteriorError("z_max must be >= 0")
    n = int(n_steps)
    if n < 32:
        raise PosteriorError("integration_n must be >= 32")

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
            raise PosteriorError("non-positive E^2 encountered in D_L table build")
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
        raise PosteriorError("interpolation table must have >=2 aligned points")
    x0 = float(xs[0])
    x1 = float(xs[-1])
    x = float(xq)
    eps = 1.0e-12 * max(1.0, abs(x1))
    if x < x0 - eps or x > x1 + eps:
        raise PosteriorError(f"z query {x:.6g} outside interpolation range [{x0:.6g}, {x1:.6g}]")
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
        raise PosteriorError("D_L must remain positive")
    return float(distance_modulus_from_D_L(D_L_m=d_l))


def _profile_chi2(
    *,
    mu_obs: Sequence[float],
    sigma_mu: Sequence[float],
    mu_model: Sequence[float],
) -> Tuple[float, float]:
    if not (len(mu_obs) == len(sigma_mu) == len(mu_model)):
        raise PosteriorError("mu arrays must have matching length")
    if len(mu_obs) == 0:
        raise PosteriorError("empty dataset")

    s0 = 0.0
    s1 = 0.0
    s2 = 0.0
    for obs, sig, mdl in zip(mu_obs, sigma_mu, mu_model):
        sig_v = float(sig)
        if sig_v <= 0.0:
            raise PosteriorError("sigma_mu must be > 0")
        w = 1.0 / (sig_v * sig_v)
        r = float(obs) - float(mdl)
        s0 += w
        s1 += w * r
        s2 += w * r * r

    if s0 <= 0.0:
        raise PosteriorError("invalid profile weights")
    delta_m = s1 / s0
    chi2 = s2 - (s1 * s1 / s0)
    if chi2 < 0.0 and chi2 > -1.0e-12:
        chi2 = 0.0
    return float(chi2), float(delta_m)


def _cdf_quantile(xs: Sequence[float], probs: Sequence[float], q: float) -> float:
    qq = min(1.0, max(0.0, float(q)))
    if len(xs) != len(probs) or len(xs) == 0:
        raise PosteriorError("quantile inputs must be non-empty aligned arrays")
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
        raise PosteriorError("stats inputs must be non-empty aligned arrays")
    norm = float(sum(float(p) for p in probs))
    if norm <= 0.0:
        raise PosteriorError("posterior marginal has non-positive normalization")
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


def _make_toy_dataset() -> DatasetBundle:
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
        "dataset_relpath": "toy_embedded_dataset.csv",
        "dataset_sha256": _sha256_bytes(csv_like.encode("utf-8")),
        "n_points": int(len(z)),
    }
    return DatasetBundle(
        z_obs=list(z),
        mu_obs=list(mu),
        sigma_mu=list(sigma),
        meta=meta,
        row_full=None,
    )


def _load_dataset(repo_root: Path, dataset_arg: str, toy_mode: bool) -> DatasetBundle:
    if toy_mode:
        return _make_toy_dataset()

    candidate = Path(dataset_arg)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    else:
        candidate = candidate.expanduser().resolve()
    if not candidate.is_file():
        raise UsageError(f"dataset file not found: {candidate}")

    z, mu, sigma_mu, raw_meta = load_sn_mu_csv(candidate)
    row_full_meta = raw_meta.get("row_full")
    row_full: Optional[List[int]] = None
    if isinstance(row_full_meta, tuple):
        row_full = [int(v) for v in row_full_meta]
    elif isinstance(row_full_meta, list):
        row_full = [int(v) for v in row_full_meta]
    rel = _relative_or_basename(candidate, repo_root)
    meta = {
        "dataset_mode": "pantheon_plus_shoes_mu_csv",
        "dataset_relpath": rel,
        "dataset_sha256": _sha256_file(candidate),
        "n_points": int(len(z)),
        "has_row_full": bool(row_full is not None),
    }
    return DatasetBundle(
        z_obs=list(z),
        mu_obs=list(mu),
        sigma_mu=list(sigma_mu),
        meta=meta,
        row_full=row_full,
    )


def _resolve_path_from_repo(repo_root: Path, raw_path: str) -> Path:
    p = Path(raw_path)
    if p.is_absolute():
        return p.expanduser().resolve()
    return (repo_root / p).resolve()


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
    manifest_sha = _sha256_file(path)
    return payload, path, manifest_sha


def _verify_manifest_file_hash(
    *,
    manifest_payload: Mapping[str, Any],
    logical_name: str,
    observed_sha256: str,
) -> None:
    files = manifest_payload.get("files")
    if not isinstance(files, Mapping):
        raise UsageError("data manifest is missing 'files' object")
    entry = files.get(logical_name)
    if not isinstance(entry, Mapping):
        raise UsageError(f"data manifest is missing files.{logical_name}")
    expected = entry.get("sha256")
    if not isinstance(expected, str) or len(expected.strip()) != 64:
        raise UsageError(f"data manifest files.{logical_name}.sha256 is missing/invalid")
    if expected.strip().lower() != observed_sha256.lower():
        raise PosteriorError(
            f"data manifest sha256 mismatch for {logical_name}: expected {expected.strip().lower()} got {observed_sha256.lower()}"
        )


def _profile_chi2_full_cov(
    *,
    mu_obs: Sequence[float],
    mu_model: Sequence[float],
    solve_cov: Any,
    c_inv_one: Sequence[float],
    one_dot_cinv_one: float,
) -> Tuple[float, float]:
    if len(mu_obs) != len(mu_model):
        raise PosteriorError("mu arrays must have matching length")
    if len(mu_obs) == 0:
        raise PosteriorError("empty dataset")
    if one_dot_cinv_one <= 0.0:
        raise PosteriorError("invalid full-covariance normalization")
    r = [float(obs) - float(mdl) for obs, mdl in zip(mu_obs, mu_model)]
    c_inv_r = solve_cov(r)
    one_dot_cinv_r = _dot(c_inv_one, r)
    delta_m = one_dot_cinv_r / float(one_dot_cinv_one)
    chi2 = _dot(r, c_inv_r) - (one_dot_cinv_r * one_dot_cinv_r) / float(one_dot_cinv_one)
    if chi2 < 0.0 and chi2 > -1.0e-12:
        chi2 = 0.0
    return float(chi2), float(delta_m)


def _load_pyplot() -> Optional[Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        matplotlib.rcParams["savefig.dpi"] = 140
        matplotlib.rcParams["font.family"] = "DejaVu Sans"
        matplotlib.rcParams["path.simplify"] = False
        matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt  # type: ignore

        return plt
    except Exception:  # pragma: no cover - environment dependent
        return None


def _save_png(fig: Any, out_path: Path) -> None:
    fig.savefig(
        str(out_path),
        format="png",
        dpi=140,
        metadata={
            "Software": "GSC phase4_pantheon_plus_epsilon_posterior",
            "Creation Time": "2000-01-01T00:00:00Z",
        },
    )


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def _save_png_rgb(*, width: int, height: int, rgb_rows: Sequence[bytes], out_path: Path) -> None:
    if width <= 0 or height <= 0:
        raise PosteriorError("PNG dimensions must be positive")
    if len(rgb_rows) != height:
        raise PosteriorError("PNG row count mismatch")
    for row in rgb_rows:
        if len(row) != width * 3:
            raise PosteriorError("PNG row width mismatch")

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
        return int(round(margin_top + plot_h * (1.0 - float(v) / y_max)))

    for i in range(1, len(x)):
        _draw_line_rgb(
            image,
            x0=px(float(x[i - 1])),
            y0=py(float(y[i - 1])),
            x1=px(float(x[i])),
            y1=py(float(y[i])),
            color=curve_color,
        )

    rows = [bytes(channel for pixel in row for channel in pixel) for row in image]
    _save_png_rgb(width=width, height=height, rgb_rows=rows, out_path=out_path)


def _write_png_2d_fallback(
    *,
    posterior: Sequence[Sequence[float]],
    out_path: Path,
) -> None:
    n_rows = len(posterior)
    n_cols = len(posterior[0]) if n_rows > 0 else 0
    if n_rows <= 0 or n_cols <= 0:
        raise PosteriorError("posterior grid must be non-empty")
    for row in posterior:
        if len(row) != n_cols:
            raise PosteriorError("posterior rows must have equal length")

    scale = 8
    width = n_cols * scale
    height = n_rows * scale
    max_v = max(float(v) for row in posterior for v in row)
    if max_v <= 0.0:
        max_v = 1.0

    image: List[List[List[int]]] = [[[255, 255, 255] for _ in range(width)] for _ in range(height)]
    for i in range(n_rows):
        row = posterior[i]
        for j in range(n_cols):
            frac = max(0.0, min(1.0, float(row[j]) / max_v))
            r = int(round(20 + 235 * frac))
            g = int(round(40 + 170 * frac))
            b = int(round(120 + 120 * (1.0 - frac)))
            for dy in range(scale):
                y = (n_rows - 1 - i) * scale + dy
                for dx in range(scale):
                    x = j * scale + dx
                    image[y][x][0] = r
                    image[y][x][1] = g
                    image[y][x][2] = b

    rows = [bytes(channel for pixel in row for channel in pixel) for row in image]
    _save_png_rgb(width=width, height=height, rgb_rows=rows, out_path=out_path)


def _write_png_1d(*, x: Sequence[float], y: Sequence[float], out_path: Path, title: str) -> None:
    plt = _load_pyplot()
    if plt is None:
        _write_png_1d_fallback(x=x, y=y, out_path=out_path)
        return
    fig, ax = plt.subplots(figsize=(7.2, 4.4), constrained_layout=True)
    ax.plot([float(v) for v in x], [float(v) for v in y], color="#1f77b4", linewidth=2.0)
    ax.set_xlabel("epsilon_em")
    ax.set_ylabel("marginal posterior")
    ax.set_title(title)
    ax.grid(True, linestyle=":", linewidth=0.7, alpha=0.6)
    _save_png(fig, out_path)
    plt.close(fig)


def _write_png_2d(
    *,
    eps_grid: Sequence[float],
    om_grid: Sequence[float],
    posterior: Sequence[Sequence[float]],
    out_path: Path,
    title: str,
) -> None:
    plt = _load_pyplot()
    if plt is None:
        _write_png_2d_fallback(posterior=posterior, out_path=out_path)
        return
    fig, ax = plt.subplots(figsize=(7.4, 5.4), constrained_layout=True)
    image = ax.imshow(
        [[float(v) for v in row] for row in posterior],
        origin="lower",
        interpolation="nearest",
        aspect="auto",
        extent=[
            float(min(eps_grid)),
            float(max(eps_grid)),
            float(min(om_grid)),
            float(max(om_grid)),
        ],
        cmap="viridis",
    )
    ax.set_xlabel("epsilon_em")
    ax.set_ylabel("omega_m")
    ax.set_title(title)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("posterior probability")
    _save_png(fig, out_path)
    plt.close(fig)


def _render_markdown(payload: Mapping[str, Any]) -> str:
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), Mapping) else {}
    results = payload.get("results") if isinstance(payload.get("results"), Mapping) else {}
    eps = results.get("epsilon_em") if isinstance(results.get("epsilon_em"), Mapping) else {}
    om = results.get("omega_m") if isinstance(results.get("omega_m"), Mapping) else {}
    shift = (
        results.get("h0_equivalent_shift_at_pivot")
        if isinstance(results.get("h0_equivalent_shift_at_pivot"), Mapping)
        else {}
    )
    best = results.get("best_fit") if isinstance(results.get("best_fit"), Mapping) else {}

    lines: List[str] = []
    lines.append("# Pantheon+ Epsilon Posterior (SN-only, deterministic scaffold)")
    lines.append("")
    lines.append("This report is an inference-layer epsilon mapping artifact.")
    if str(payload.get("covariance_mode")) == "diag_only_proof_of_concept":
        lines.append("It is not paper-grade while covariance mode is diagonal-only.")
    else:
        lines.append("Full covariance mode is enabled for paper-grade likelihood evaluation.")
    lines.append("")
    lines.append("## Inputs")
    lines.append(f"- covariance_mode: `{payload.get('covariance_mode')}`")
    lines.append(f"- dataset: `{inputs.get('dataset_relpath')}`")
    if inputs.get("covariance_relpath") is not None:
        lines.append(f"- covariance: `{inputs.get('covariance_relpath')}`")
    if inputs.get("data_manifest_relpath") is not None:
        lines.append(f"- data manifest: `{inputs.get('data_manifest_relpath')}`")
    lines.append(f"- n_points: `{int(inputs.get('n_points', 0))}`")
    lines.append(f"- omega_m grid: `{inputs.get('omega_m_min')} .. {inputs.get('omega_m_max')}` (`n={inputs.get('omega_m_n')}`)")
    lines.append(f"- epsilon grid: `{inputs.get('epsilon_min')} .. {inputs.get('epsilon_max')}` (`n={inputs.get('epsilon_n')}`)")
    lines.append("")
    lines.append("## Posterior summary")
    lines.append(
        f"- epsilon_em (p50 [p16,p84]): `{float(eps.get('p50', float('nan'))):.6g}` [`{float(eps.get('p16', float('nan'))):.6g}`, `{float(eps.get('p84', float('nan'))):.6g}`]"
    )
    lines.append(
        f"- epsilon_em 95%: [`{float(eps.get('p2_5', float('nan'))):.6g}`, `{float(eps.get('p97_5', float('nan'))):.6g}`]"
    )
    lines.append(
        f"- omega_m best-fit: `{float(best.get('omega_m_best_fit', float('nan'))):.6g}`; posterior p50: `{float(om.get('p50', float('nan'))):.6g}`"
    )
    lines.append(
        f"- chi2_best: `{float(best.get('chi2_min', float('nan'))):.6g}`; ndof_approx: `{int(best.get('ndof_approx', 0))}`"
    )
    lines.append("")
    lines.append("## H0-equivalent diagnostic (approximate)")
    lines.append(
        f"- pivot z_obs: `{float(shift.get('pivot_z_obs', float('nan'))):.6g}`"
    )
    lines.append(
        f"- inferred H0 ratio: `{float(shift.get('h0_ratio_equivalent', float('nan'))):.12e}`"
    )
    lines.append(f"- note: {shift.get('note', '')}")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("```bash")
    lines.append(
        "python3 v11.0.0/scripts/phase4_pantheon_plus_epsilon_posterior.py --repo-root v11.0.0 --outdir <outdir> --deterministic 1 --format text --run-mode demo"
    )
    lines.append(
        "python3 v11.0.0/scripts/phase2_schema_validate.py --auto --schema-dir v11.0.0/schemas --json <outdir>/PANTHEON_EPSILON_POSTERIOR_REPORT.json"
    )
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _render_text(payload: Mapping[str, Any]) -> str:
    results = payload.get("results") if isinstance(payload.get("results"), Mapping) else {}
    eps = results.get("epsilon_em") if isinstance(results.get("epsilon_em"), Mapping) else {}
    best = results.get("best_fit") if isinstance(results.get("best_fit"), Mapping) else {}
    lines = [
        f"schema={payload.get('schema')}",
        f"status={payload.get('status')}",
        f"repo_version_dir={payload.get('repo_version_dir')}",
        f"run_mode={payload.get('run_mode')}",
        f"covariance_mode={payload.get('covariance_mode')}",
        f"paths_redacted={bool(payload.get('paths_redacted'))}",
        f"epsilon_p50={float(eps.get('p50', float('nan'))):.12e}",
        f"epsilon_p16={float(eps.get('p16', float('nan'))):.12e}",
        f"epsilon_p84={float(eps.get('p84', float('nan'))):.12e}",
        f"omega_m_best_fit={float(best.get('omega_m_best_fit', float('nan'))):.12e}",
        f"chi2_min={float(best.get('chi2_min', float('nan'))):.12e}",
    ]
    return "\n".join(lines) + "\n"


def _count_forbidden(text: str) -> int:
    total = 0
    for token in ABS_TOKENS:
        total += text.count(token)
    return total


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Deterministic Pantheon+ SN-only epsilon posterior (inference-layer toy scaffold)."
    )
    ap.add_argument("--repo-root", default="v11.0.0")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--run-mode", choices=("demo", "paper_grade"), default="demo")
    ap.add_argument("--deterministic", choices=(0, 1), type=int, default=1)
    ap.add_argument("--created-utc", type=int, default=None)
    ap.add_argument("--toy", choices=(0, 1), type=int, default=0)
    ap.add_argument(
        "--covariance-mode",
        choices=("diag_only_proof_of_concept", "full"),
        default="diag_only_proof_of_concept",
    )

    ap.add_argument(
        "--dataset",
        default="data/sn/pantheon_plus_shoes/pantheon_plus_shoes_mu.csv",
        help="SN mu(z) CSV path (relative to --repo-root unless absolute).",
    )
    ap.add_argument(
        "--covariance",
        default=None,
        help="Covariance matrix file path (required when --covariance-mode full).",
    )
    ap.add_argument(
        "--data-manifest",
        default=None,
        help="Optional pinned fetch manifest JSON; if provided, dataset/covariance SHA256 must match.",
    )
    ap.add_argument("--H0-km-s-Mpc", type=float, default=70.0)
    ap.add_argument("--omega-m-min", type=float, default=0.15)
    ap.add_argument("--omega-m-max", type=float, default=0.45)
    ap.add_argument("--omega-m-n", type=int, default=41)
    ap.add_argument("--epsilon-min", type=float, default=-0.12)
    ap.add_argument("--epsilon-max", type=float, default=0.12)
    ap.add_argument("--epsilon-n", type=int, default=61)
    ap.add_argument("--delta-eps", type=float, default=1.0e-4)
    ap.add_argument("--pivot-z", type=float, default=0.5)
    ap.add_argument("--integration-n", type=int, default=3000)
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
        run_mode = str(args.run_mode)

        deterministic_mode = bool(int(args.deterministic))
        if args.created_utc is not None:
            created_epoch = int(args.created_utc)
        elif deterministic_mode:
            created_epoch = DEFAULT_CREATED_UTC_EPOCH
        else:
            created_epoch = int(time.time())
        created_utc = _to_iso_utc(created_epoch)

        toy_mode = bool(int(args.toy))
        emit_plots = bool(int(args.emit_plots))

        h0_km = _require_finite(float(args.H0_km_s_Mpc), name="H0_km_s_Mpc")
        if h0_km <= 0.0:
            raise UsageError("--H0-km-s-Mpc must be > 0")
        h0_si = H0_to_SI(h0_km)

        omega_grid = _linear_grid(float(args.omega_m_min), float(args.omega_m_max), int(args.omega_m_n), name="omega_m")
        epsilon_grid = _linear_grid(float(args.epsilon_min), float(args.epsilon_max), int(args.epsilon_n), name="epsilon")
        if min(epsilon_grid) <= -0.95:
            raise UsageError("epsilon_min must be > -0.95 for stable z_gr mapping")
        if int(args.integration_n) < 32:
            raise UsageError("--integration-n must be >= 32")

        dataset = _load_dataset(repo_root, str(args.dataset), toy_mode)
        z_obs = list(dataset.z_obs)
        mu_obs = list(dataset.mu_obs)
        sigma_mu = list(dataset.sigma_mu)
        dataset_meta = dict(dataset.meta)
        if len(z_obs) < 3:
            raise PosteriorError("SN dataset must contain at least 3 points")

        covariance_mode = str(args.covariance_mode)
        if run_mode == "paper_grade":
            if covariance_mode != "full":
                raise UsageError("--run-mode paper_grade requires --covariance-mode full")
            if not args.data_manifest:
                raise UsageError("--run-mode paper_grade requires --data-manifest")
            if _load_pyplot() is None:
                raise UsageError("--run-mode paper_grade requires matplotlib for paper-grade plot outputs")
        cov_relpath: Optional[str] = None
        cov_sha256: Optional[str] = None
        cov_dim: Optional[int] = None
        cov_manifest_payload: Optional[Dict[str, Any]] = None
        cov_manifest_relpath: Optional[str] = None
        cov_manifest_sha: Optional[str] = None
        solve_cov: Optional[Any] = None
        c_inv_one: Optional[List[float]] = None
        one_dot_cinv_one: Optional[float] = None

        if covariance_mode == "full":
            if not args.covariance:
                raise UsageError("--covariance is required when --covariance-mode full")
            cov_path = _resolve_path_from_repo(repo_root, str(args.covariance))
            cov_relpath = _relative_or_basename(cov_path, repo_root)
            cov_sha256 = _sha256_file(cov_path)
            cov_matrix = _load_covariance_matrix(cov_path)
            if dataset.row_full is not None:
                cov_matrix = _subset_covariance(cov_matrix, dataset.row_full)
                dataset_meta["row_full_subset_mode"] = True
            else:
                dataset_meta["row_full_subset_mode"] = False

            if len(cov_matrix) != len(z_obs):
                raise PosteriorError(
                    f"covariance dimension mismatch: got {len(cov_matrix)} expected {len(z_obs)} after optional row_full slicing"
                )
            cov_dim = int(len(cov_matrix))
            solve_cov = _make_cov_solver(cov_matrix)
            c_inv_one = solve_cov([1.0 for _ in range(cov_dim)])
            one_dot_cinv_one = _dot([1.0 for _ in range(cov_dim)], c_inv_one)
            if one_dot_cinv_one <= 0.0:
                raise PosteriorError("invalid full-covariance normalization scalar")

            cov_manifest_payload, cov_manifest_path, cov_manifest_sha = _load_data_manifest(
                repo_root, args.data_manifest
            )
            if cov_manifest_payload is not None and cov_manifest_path is not None and cov_manifest_sha is not None:
                manifest_schema = cov_manifest_payload.get("schema")
                if not isinstance(manifest_schema, str) or manifest_schema != FETCH_MANIFEST_SCHEMA:
                    raise UsageError(
                        f"data manifest schema must be {FETCH_MANIFEST_SCHEMA!r}, got {manifest_schema!r}"
                    )
                cov_manifest_relpath = _relative_or_basename(cov_manifest_path, repo_root)
                _verify_manifest_file_hash(
                    manifest_payload=cov_manifest_payload,
                    logical_name="mu",
                    observed_sha256=str(dataset_meta["dataset_sha256"]),
                )
                _verify_manifest_file_hash(
                    manifest_payload=cov_manifest_payload,
                    logical_name="cov",
                    observed_sha256=cov_sha256,
                )

        z_gr_by_eps: List[List[float]] = []
        z_max_gr = 0.0
        for eps in epsilon_grid:
            rows: List[float] = []
            for z in z_obs:
                z_gr = _z_gr_from_z_obs(float(z), float(eps))
                if z_gr < 0.0:
                    raise PosteriorError("z_gr mapping yielded negative redshift; adjust epsilon range")
                rows.append(float(z_gr))
                z_max_gr = max(z_max_gr, float(z_gr))
            z_gr_by_eps.append(rows)
        z_max_gr = max(z_max_gr, float(args.pivot_z), max(z_obs))

        chi2_grid: List[List[float]] = []
        delta_m_grid: List[List[float]] = []
        mu_cache: Dict[Tuple[int, int], float] = {}

        chi2_min = float("inf")
        best_i = 0
        best_j = 0

        for i_om, omega_m in enumerate(omega_grid):
            z_nodes, d_l_nodes = _build_dl_table(
                omega_m=float(omega_m),
                h0_si=h0_si,
                z_max=z_max_gr + 1.0e-4,
                n_steps=int(args.integration_n),
            )
            row_chi2: List[float] = []
            row_dm: List[float] = []

            for j_eps, z_gr_list in enumerate(z_gr_by_eps):
                mu_model: List[float] = []
                for k, z_gr in enumerate(z_gr_list):
                    mu_v = _mu_from_table(float(z_gr), z_nodes, d_l_nodes)
                    mu_cache[(i_om * len(epsilon_grid) + j_eps, k)] = float(mu_v)
                    mu_model.append(float(mu_v))
                if covariance_mode == "full":
                    if solve_cov is None or c_inv_one is None or one_dot_cinv_one is None:
                        raise PosteriorError("internal full-covariance solver is not initialized")
                    chi2, delta_m = _profile_chi2_full_cov(
                        mu_obs=mu_obs,
                        mu_model=mu_model,
                        solve_cov=solve_cov,
                        c_inv_one=c_inv_one,
                        one_dot_cinv_one=one_dot_cinv_one,
                    )
                else:
                    chi2, delta_m = _profile_chi2(mu_obs=mu_obs, sigma_mu=sigma_mu, mu_model=mu_model)
                row_chi2.append(float(chi2))
                row_dm.append(float(delta_m))
                if chi2 < chi2_min:
                    chi2_min = float(chi2)
                    best_i = int(i_om)
                    best_j = int(j_eps)

            chi2_grid.append(row_chi2)
            delta_m_grid.append(row_dm)

        if not math.isfinite(chi2_min):
            raise PosteriorError("failed to compute finite chi2 grid")

        weights: List[List[float]] = []
        norm = 0.0
        for row in chi2_grid:
            w_row: List[float] = []
            for chi2 in row:
                exponent = -0.5 * (float(chi2) - chi2_min)
                if exponent < -745.0:
                    w = 0.0
                else:
                    w = math.exp(exponent)
                w_row.append(float(w))
                norm += float(w)
            weights.append(w_row)
        if norm <= 0.0:
            raise PosteriorError("posterior normalization is non-positive")

        posterior: List[List[float]] = []
        for row in weights:
            posterior.append([float(w) / norm for w in row])

        p_eps = [0.0] * len(epsilon_grid)
        p_om = [0.0] * len(omega_grid)
        for i in range(len(omega_grid)):
            for j in range(len(epsilon_grid)):
                pv = float(posterior[i][j])
                p_om[i] += pv
                p_eps[j] += pv

        eps_stats = _summary_stats(epsilon_grid, p_eps)
        om_stats = _summary_stats(omega_grid, p_om)

        omega_best = float(omega_grid[best_i])
        epsilon_best = float(epsilon_grid[best_j])
        delta_m_best = float(delta_m_grid[best_i][best_j])

        z_nodes_best, d_l_nodes_best = _build_dl_table(
            omega_m=omega_best,
            h0_si=h0_si,
            z_max=max(z_max_gr, float(args.pivot_z)) + 1.0e-4,
            n_steps=int(args.integration_n),
        )
        pivot_z = _require_finite(float(args.pivot_z), name="pivot_z")
        if pivot_z < 0.0:
            raise UsageError("--pivot-z must be >= 0")
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
                            _fmt_e(chi2_grid[i_om][j_eps]),
                            _fmt_e(delta_m_grid[i_om][j_eps]),
                            _fmt_e(posterior[i_om][j_eps]),
                        )
                    )
                    + "\n"
                )
        posterior_grid_digest = _sha256_bytes("".join(row_digest_lines).encode("utf-8"))

        epsilon_marginal_lines = [
            f"{_fmt_e(eps)},{_fmt_e(prob)}\n" for eps, prob in zip(epsilon_grid, p_eps)
        ]
        epsilon_digest = _sha256_bytes("".join(epsilon_marginal_lines).encode("utf-8"))

        snapshot = _snapshot_fingerprint(repo_root)

        warnings: List[str] = []
        if covariance_mode == "diag_only_proof_of_concept":
            warnings.extend(
                [
                    "SN-only posterior in this artifact uses diagonal sigma_mu likelihood.",
                    "Not paper-grade until full covariance is wired and validated.",
                ]
            )

        inputs_payload: Dict[str, Any] = {
            "dataset_mode": dataset_meta["dataset_mode"],
            "dataset_relpath": dataset_meta["dataset_relpath"],
            "dataset_sha256": dataset_meta["dataset_sha256"],
            "n_points": int(dataset_meta["n_points"]),
            "run_mode": run_mode,
            "H0_km_s_Mpc_fixed_for_shape": float(h0_km),
            "epsilon_em_fixed": None,
            "epsilon_qcd_assumed": 0.0,
            "epsilon_gr_assumed": 0.0,
            "omega_m_min": float(min(omega_grid)),
            "omega_m_max": float(max(omega_grid)),
            "omega_m_n": int(len(omega_grid)),
            "epsilon_min": float(min(epsilon_grid)),
            "epsilon_max": float(max(epsilon_grid)),
            "epsilon_n": int(len(epsilon_grid)),
            "delta_eps_fd": float(args.delta_eps),
            "integration_n": int(args.integration_n),
            "pivot_z": float(pivot_z),
            "toy_mode": bool(toy_mode),
        }
        if covariance_mode == "full":
            inputs_payload["covariance_relpath"] = cov_relpath
            inputs_payload["covariance_sha256"] = cov_sha256
            inputs_payload["covariance_n"] = int(cov_dim) if cov_dim is not None else None
            inputs_payload["row_full_subset_mode"] = bool(dataset_meta.get("row_full_subset_mode", False))
            if cov_manifest_relpath is not None and cov_manifest_sha is not None:
                inputs_payload["data_manifest_relpath"] = cov_manifest_relpath
                inputs_payload["data_manifest_sha256"] = cov_manifest_sha
                schema_val = cov_manifest_payload.get("schema") if isinstance(cov_manifest_payload, Mapping) else None
                if isinstance(schema_val, str):
                    inputs_payload["data_manifest_schema"] = schema_val

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "status": "ok",
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "deterministic_mode": bool(deterministic_mode),
            "run_mode": run_mode,
            "plot_backend": "matplotlib" if _load_pyplot() is not None else "fallback",
            "repo_version_dir": str(repo_root.name),
            "paths_redacted": True,
            "repo_snapshot_manifest_sha256": snapshot["repo_snapshot_manifest_sha256"],
            "repo_snapshot_manifest_source": snapshot["repo_snapshot_manifest_source"],
            "covariance_mode": covariance_mode,
            "warnings": warnings,
            "model": "flat_lcdm",
            "inputs": inputs_payload,
            "parameters": {
                "prior_omega_m_uniform": [float(min(omega_grid)), float(max(omega_grid))],
                "prior_epsilon_em_uniform": [float(min(epsilon_grid)), float(max(epsilon_grid))],
                "grid_resolution": {"omega_m_n": int(len(omega_grid)), "epsilon_n": int(len(epsilon_grid))},
                "pivot_redshift_for_h0_equivalent_shift": float(pivot_z),
            },
            "results": {
                "epsilon_em": {
                    **eps_stats,
                    "best_fit": float(epsilon_best),
                },
                "omega_m": {
                    **om_stats,
                    "best_fit": float(omega_best),
                },
                "best_fit": {
                    "omega_m_best_fit": float(omega_best),
                    "epsilon_em_best_fit": float(epsilon_best),
                    "delta_M_profiled_best_fit": float(delta_m_best),
                    "chi2_min": float(chi2_min),
                    "ndof_approx": int(len(z_obs) - 1),
                },
                "h0_equivalent_shift_at_pivot": {
                    "pivot_z_obs": float(pivot_z),
                    "epsilon_em_reference": float(eps_ref),
                    "z_gr_at_pivot": float(z_gr_pivot),
                    "delta_mu_at_pivot": float(delta_mu_pivot),
                    "h0_ratio_equivalent": float(h0_ratio),
                    "note": "Approximate SN-only diagnostic; no absolute H0 inference without external calibration.",
                },
            },
            "digests": {
                "posterior_grid_sha256": posterior_grid_digest,
                "epsilon_marginal_sha256": epsilon_digest,
            },
            "artifacts": [],
            "portability": {
                "forbidden_absolute_path_match_count": 0,
            },
        }
        if cov_manifest_sha is not None:
            payload["data_manifest_sha256"] = str(cov_manifest_sha)

        report_json = outdir / "PANTHEON_EPSILON_POSTERIOR_REPORT.json"
        report_md = outdir / "PANTHEON_EPSILON_POSTERIOR_REPORT.md"
        report_short = outdir / "report.md"
        eps_png = outdir / "epsilon_posterior_1d.png"
        heat_png = outdir / "omega_m_vs_epsilon.png"

        if emit_plots:
            _write_png_1d(
                x=epsilon_grid,
                y=p_eps,
                out_path=eps_png,
                title="Pantheon+ epsilon_em marginal (SN-only)",
            )
            _write_png_2d(
                eps_grid=epsilon_grid,
                om_grid=omega_grid,
                posterior=posterior,
                out_path=heat_png,
                title="Pantheon+ posterior in (omega_m, epsilon_em)",
            )
        else:
            raise UsageError("--emit-plots 0 is no longer supported; plot artifacts are mandatory")

        markdown_text = _render_markdown(payload)
        report_md.write_text(markdown_text, encoding="utf-8")
        report_short.write_text(markdown_text, encoding="utf-8")

        artifact_rows: List[Dict[str, str]] = []
        for name, path in (
            ("PANTHEON_EPSILON_POSTERIOR_REPORT.json", report_json),
            ("PANTHEON_EPSILON_POSTERIOR_REPORT.md", report_md),
            ("report.md", report_short),
            ("epsilon_posterior_1d.png", eps_png),
            ("omega_m_vs_epsilon.png", heat_png),
        ):
            row: Dict[str, str] = {"filename": name}
            if name.endswith(".png"):
                row["kind"] = "plot"
            elif name.endswith(".json"):
                row["kind"] = "report_json"
            elif name.endswith(".md"):
                row["kind"] = "report_markdown"
            if path.is_file() and name != "PANTHEON_EPSILON_POSTERIOR_REPORT.json":
                row["sha256"] = _sha256_file(path)
            artifact_rows.append(row)
        payload["artifacts"] = artifact_rows

        payload["portability"]["forbidden_absolute_path_match_count"] = int(_count_forbidden(markdown_text))
        json_text = _json_pretty(payload)
        payload["portability"]["forbidden_absolute_path_match_count"] += int(_count_forbidden(json_text))
        json_text = _json_pretty(payload)

        report_json.write_text(json_text, encoding="utf-8")

        if str(args.format) == "json":
            print(json_text, end="")
        else:
            print(_render_text(payload), end="")
        return 0

    except (UsageError, PosteriorError) as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
