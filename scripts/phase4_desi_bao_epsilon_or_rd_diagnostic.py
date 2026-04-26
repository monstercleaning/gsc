#!/usr/bin/env python3
"""Deterministic DESI BAO baseline leg diagnostic (Phase-4 M156 / Triangle-1)."""

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
from gsc.epsilon.translator import one_plus_z_from_sigma_ratio  # noqa: E402
from gsc.histories.full_range import FlatLCDMRadHistory  # noqa: E402
from gsc.measurement_model import H0_to_SI  # noqa: E402


TOOL = "phase4_desi_bao_epsilon_or_rd_diagnostic"
TOOL_VERSION = "m156-v1"
SCHEMA = "phase4_desi_bao_triangle1_report_v1"
FETCH_SCHEMA = "phase4_desi_bao_fetch_manifest_v1"
FAIL_MARKER = "PHASE4_DESI_BAO_DIAGNOSTIC_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


class UsageError(Exception):
    """CLI usage/configuration error."""


class DiagnosticError(Exception):
    """Runtime diagnostic failure."""


@dataclass(frozen=True)
class DatasetBundle:
    dataset: BAODataset
    relpath: str
    sha256: str
    mode: str


@dataclass(frozen=True)
class RowResult:
    omega_m: float
    epsilon_em: float
    chi2: float
    ndof: int
    rd_m: float


class EpsilonMappedLCDMHistory:
    """Flat LCDM history with inference-layer epsilon redshift remapping.

    Mapping used (same toy ansatz family as M148 translator):
      1 + z_em = sigma_ratio^(1 + epsilon_em), epsilon_gr=0
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
            raise DiagnosticError("epsilon_em must be finite")
        if abs(1.0 + self._epsilon_em) < 1.0e-12:
            raise DiagnosticError("epsilon_em too close to -1 makes mapping undefined")
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
            raise DiagnosticError("observed redshift must satisfy 1+z>0")

        # Invert one_plus_z_from_sigma_ratio(sigma_ratio, epsilon_em)=1+z_obs
        sigma_ratio = one_plus_z_obs ** (1.0 / (1.0 + self._epsilon_em))
        one_plus_z_em_check = one_plus_z_from_sigma_ratio(sigma_ratio, self._epsilon_em)
        if abs(one_plus_z_em_check - one_plus_z_obs) > 1.0e-10 * max(1.0, one_plus_z_obs):
            raise DiagnosticError("epsilon mapping inversion consistency check failed")
        return float(sigma_ratio - 1.0)

    def H(self, z: float) -> float:
        z_gr = self._z_gr_from_z_obs(float(z))
        return float(self._base.H(z_gr))


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


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
    schema_id = payload.get("schema")
    if not isinstance(schema_id, str) or schema_id != FETCH_SCHEMA:
        raise UsageError(f"data manifest schema must be {FETCH_SCHEMA!r}")
    return payload, path, _sha256_file(path)


def _verify_manifest_dataset_hash(manifest_payload: Mapping[str, Any], dataset_filename: str, observed_sha256: str) -> None:
    files = manifest_payload.get("files")
    if not isinstance(files, Mapping):
        raise UsageError("data manifest is missing 'files' object")
    entry = files.get(dataset_filename)
    if not isinstance(entry, Mapping):
        raise UsageError(f"data manifest is missing files.{dataset_filename}")
    expected = entry.get("sha256")
    if not isinstance(expected, str) or len(expected.strip()) != 64:
        raise UsageError(f"data manifest files.{dataset_filename}.sha256 is missing/invalid")
    if expected.strip().lower() != observed_sha256.lower():
        raise DiagnosticError(
            f"data manifest sha256 mismatch for {dataset_filename}: expected {expected.strip().lower()} got {observed_sha256.lower()}"
        )


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


def _cdf_quantile(xs: Sequence[float], probs: Sequence[float], q: float) -> float:
    qq = min(1.0, max(0.0, float(q)))
    if len(xs) != len(probs) or len(xs) == 0:
        raise DiagnosticError("quantile inputs must be non-empty aligned arrays")
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
        raise DiagnosticError("stats inputs must be non-empty aligned arrays")
    norm = float(sum(float(p) for p in probs))
    if norm <= 0.0:
        raise DiagnosticError("posterior marginal has non-positive normalization")
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


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def _save_png_rgb(*, width: int, height: int, rgb_rows: Sequence[bytes], out_path: Path) -> None:
    if width <= 0 or height <= 0:
        raise DiagnosticError("PNG dimensions must be positive")
    if len(rgb_rows) != height:
        raise DiagnosticError("PNG row count mismatch")
    for row in rgb_rows:
        if len(row) != width * 3:
            raise DiagnosticError("PNG row width mismatch")

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


def _write_png_2d_heatmap_fallback(*, x: Sequence[float], y: Sequence[float], z_grid: Sequence[Sequence[float]], out_path: Path) -> None:
    width = 860
    height = 560
    image: List[List[List[int]]] = [[[255, 255, 255] for _ in range(width)] for _ in range(height)]
    margin_left = 80
    margin_right = 24
    margin_top = 24
    margin_bottom = 72
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    x_min = float(min(x))
    x_max = float(max(x))
    y_min = float(min(y))
    y_max = float(max(y))

    vals: List[float] = []
    for row in z_grid:
        vals.extend(float(v) for v in row)
    z_min = min(vals) if vals else 0.0
    z_max = max(vals) if vals else 1.0
    if z_max <= z_min:
        z_max = z_min + 1.0

    nx = max(2, len(x))
    ny = max(2, len(y))

    for py in range(plot_h):
        fy = py / max(1, plot_h - 1)
        yi = int(round((1.0 - fy) * (ny - 1)))
        yi = max(0, min(ny - 1, yi))
        for px in range(plot_w):
            fx = px / max(1, plot_w - 1)
            xi = int(round(fx * (nx - 1)))
            xi = max(0, min(nx - 1, xi))
            z = float(z_grid[yi][xi])
            t = (z - z_min) / (z_max - z_min)
            t = max(0.0, min(1.0, t))
            r = int(round(20 + 220 * t))
            g = int(round(40 + 140 * (1.0 - abs(t - 0.5) * 2.0)))
            b = int(round(220 - 180 * t))
            image[margin_top + py][margin_left + px] = [r, g, b]

    axis_color = (30, 30, 30)
    x_axis_y = margin_top + plot_h
    for xx in range(margin_left, margin_left + plot_w + 1):
        _draw_line_rgb(image, x0=xx, y0=x_axis_y, x1=xx, y1=x_axis_y, color=axis_color)
    for yy in range(margin_top, margin_top + plot_h + 1):
        _draw_line_rgb(image, x0=margin_left, y0=yy, x1=margin_left, y1=yy, color=axis_color)

    rows = [bytes(ch for pix in row for ch in pix) for row in image]
    _save_png_rgb(width=width, height=height, rgb_rows=rows, out_path=out_path)


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


def _count_abs_tokens(text: str) -> int:
    return int(sum(text.count(tok) for tok in ABS_TOKENS))


def _extract_dataset_meta(dataset: BAODataset) -> Dict[str, Any]:
    block_types: Dict[str, int] = {}
    n_obs = 0
    z_values: List[float] = []
    for block in dataset.blocks:
        bt = str(getattr(block, "kind", "unknown"))
        block_types[bt] = int(block_types.get(bt, 0) + 1)
        if isinstance(block, BAOBlock1D):
            n_obs += 1
            z_values.append(float(block.z))
        elif isinstance(block, BAOBlock2D):
            n_obs += 2
            z_values.append(float(block.z))
        else:
            ys = list(getattr(block, "y", ()))
            zs = list(getattr(block, "zs", ()))
            n_obs += len(ys)
            for z in zs:
                z_values.append(float(z))
    return {
        "n_blocks": int(len(dataset.blocks)),
        "n_observables": int(n_obs),
        "block_type_counts": {k: int(block_types[k]) for k in sorted(block_types)},
        "z_min": float(min(z_values) if z_values else 0.0),
        "z_max": float(max(z_values) if z_values else 0.0),
    }


def _make_toy_dataset() -> DatasetBundle:
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
    return DatasetBundle(
        dataset=dataset,
        relpath="toy_embedded_desi_bao.csv",
        sha256=_sha256_bytes(toy_csv.encode("utf-8")),
        mode="toy_embedded",
    )


def _load_dataset(repo_root: Path, dataset_arg: str, toy_mode: bool) -> DatasetBundle:
    if toy_mode:
        return _make_toy_dataset()

    dataset_path = _resolve_path_from_repo(repo_root, str(dataset_arg))
    if not dataset_path.is_file():
        raise UsageError(f"dataset file not found: {dataset_path}")
    dataset = BAODataset.from_csv(dataset_path, name="desi_bao_baseline")
    return DatasetBundle(
        dataset=dataset,
        relpath=_relative_or_basename(dataset_path, repo_root),
        sha256=_sha256_file(dataset_path),
        mode="desi_dr1_baseline_compact",
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic DESI BAO baseline leg diagnostic for Triangle-1.")
    ap.add_argument("--repo-root", default="v11.0.0")
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--deterministic", choices=(0, 1), type=int, default=1)
    ap.add_argument("--created-utc", type=int, default=None)

    ap.add_argument("--toy", choices=(0, 1), type=int, default=0)
    ap.add_argument("--dataset", default="data/bao/desi/desi_dr1_bao_baseline.csv")
    ap.add_argument("--data-manifest", default=None)

    ap.add_argument("--covariance-mode", choices=("diag_compact", "full_bundle"), default="diag_compact")
    ap.add_argument("--rd-mode", choices=("profile", "fixed"), default="profile")
    ap.add_argument("--rd-m", type=float, default=None)

    ap.add_argument("--H0-km-s-Mpc", type=float, default=70.0)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)
    ap.add_argument("--N-eff", type=float, default=3.046)

    ap.add_argument("--omega-m-min", type=float, default=0.20)
    ap.add_argument("--omega-m-max", type=float, default=0.40)
    ap.add_argument("--omega-m-n", type=int, default=41)

    ap.add_argument("--epsilon-min", type=float, default=-0.10)
    ap.add_argument("--epsilon-max", type=float, default=0.10)
    ap.add_argument("--epsilon-n", type=int, default=81)

    ap.add_argument("--emit-plot", choices=(0, 1), type=int, default=1)
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)

        deterministic_mode = bool(int(args.deterministic))
        if args.created_utc is not None:
            created_epoch = int(args.created_utc)
        elif deterministic_mode:
            created_epoch = DEFAULT_CREATED_UTC_EPOCH
        else:
            created_epoch = int(time.time())
        created_utc = _to_iso_utc(created_epoch)

        repo_root = _resolve_path_from_repo(Path.cwd(), str(args.repo_root))
        if not repo_root.is_dir():
            raise UsageError(f"repo root not found: {repo_root}")

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        h0_km = _require_finite(args.H0_km_s_Mpc, name="H0-km-s-Mpc")
        if h0_km <= 0.0:
            raise UsageError("--H0-km-s-Mpc must be > 0")
        h0_si = float(H0_to_SI(h0_km))

        rd_mode = str(args.rd_mode)
        rd_m_input = None if args.rd_m is None else _require_finite(args.rd_m, name="rd_m")
        if rd_mode == "fixed":
            if rd_m_input is None:
                raise UsageError("--rd-mode fixed requires --rd-m")
            if rd_m_input <= 0.0:
                raise UsageError("--rd-m must be > 0")
        elif rd_m_input is not None and rd_m_input <= 0.0:
            raise UsageError("--rd-m must be > 0 when provided")

        toy_mode = bool(int(args.toy))
        bundle = _load_dataset(repo_root, str(args.dataset), toy_mode)

        manifest_payload, manifest_path, manifest_sha = _load_data_manifest(repo_root, args.data_manifest)
        if manifest_payload is not None and not toy_mode:
            _verify_manifest_dataset_hash(manifest_payload, Path(str(args.dataset)).name, bundle.sha256)

        omega_grid = _linear_grid(args.omega_m_min, args.omega_m_max, int(args.omega_m_n), name="omega_m")
        eps_grid = _linear_grid(args.epsilon_min, args.epsilon_max, int(args.epsilon_n), name="epsilon")

        rows: List[RowResult] = []
        chi2_grid: List[List[float]] = []
        rd_grid: List[List[float]] = []
        ndof_ref: Optional[int] = None

        for om in omega_grid:
            chi2_row: List[float] = []
            rd_row: List[float] = []
            for eps in eps_grid:
                model = EpsilonMappedLCDMHistory(
                    h0_si=h0_si,
                    omega_m=float(om),
                    epsilon_em=float(eps),
                    Tcmb_K=float(args.Tcmb_K),
                    N_eff=float(args.N_eff),
                )
                if rd_mode == "fixed":
                    res = bundle.dataset.chi2(model, rd_m=float(rd_m_input))
                else:
                    res = bundle.dataset.chi2(model, fit_rd=True)
                chi2 = float(res.chi2)
                ndof = int(res.ndof)
                rd_m = float(res.params.get("rd_m", rd_m_input if rd_m_input is not None else float("nan")))
                if not math.isfinite(chi2):
                    raise DiagnosticError("non-finite chi2 encountered")
                if not math.isfinite(rd_m) or rd_m <= 0.0:
                    raise DiagnosticError("non-physical rd_m encountered")
                if ndof_ref is None:
                    ndof_ref = ndof
                elif ndof != ndof_ref:
                    raise DiagnosticError("ndof changed across grid; unexpected BAO setup")

                rows.append(RowResult(omega_m=float(om), epsilon_em=float(eps), chi2=chi2, ndof=ndof, rd_m=rd_m))
                chi2_row.append(chi2)
                rd_row.append(rd_m)
            chi2_grid.append(chi2_row)
            rd_grid.append(rd_row)

        if not rows:
            raise DiagnosticError("empty result grid")

        best = min(rows, key=lambda r: (r.chi2, r.omega_m, r.epsilon_em))
        min_chi2 = float(best.chi2)

        # Posterior weights on uniform grid.
        weights_2d: List[List[float]] = []
        total_w = 0.0
        for row_vals in chi2_grid:
            ww_row: List[float] = []
            for v in row_vals:
                w = math.exp(-0.5 * (float(v) - min_chi2))
                ww_row.append(w)
                total_w += w
            weights_2d.append(ww_row)
        if not (total_w > 0.0 and math.isfinite(total_w)):
            raise DiagnosticError("posterior normalization failed")

        for i in range(len(weights_2d)):
            for j in range(len(weights_2d[i])):
                weights_2d[i][j] = float(weights_2d[i][j] / total_w)

        eps_probs = [0.0 for _ in eps_grid]
        om_probs = [0.0 for _ in omega_grid]
        for i in range(len(omega_grid)):
            for j in range(len(eps_grid)):
                w = weights_2d[i][j]
                om_probs[i] += w
                eps_probs[j] += w

        eps_stats = _summary_stats(eps_grid, eps_probs)
        om_stats = _summary_stats(omega_grid, om_probs)

        eps_zero_idx = min(range(len(eps_grid)), key=lambda j: abs(float(eps_grid[j])))
        chi2_at_eps0 = min(float(chi2_grid[i][eps_zero_idx]) for i in range(len(omega_grid)))

        plot_backend = "fallback"
        plot_1d_path = outdir / "epsilon_posterior_1d.png"
        plot_2d_path = outdir / "omega_m_vs_epsilon.png"
        plt = _optional_matplotlib()
        if plt is not None:
            plot_backend = "matplotlib"
            fig1, ax1 = plt.subplots(figsize=(6.0, 4.0), dpi=140)
            ax1.plot(eps_grid, eps_probs, color="#1f77b4", linewidth=2.0)
            ax1.set_xlabel("epsilon_em")
            ax1.set_ylabel("p(epsilon_em | BAO)")
            ax1.grid(True, alpha=0.25)
            fig1.tight_layout()
            fig1.savefig(
                str(plot_1d_path),
                format="png",
                dpi=140,
                metadata={
                    "Software": "GSC phase4_desi_bao_epsilon_or_rd_diagnostic",
                    "Creation Time": "2000-01-01T00:00:00Z",
                },
            )
            plt.close(fig1)

            fig2, ax2 = plt.subplots(figsize=(6.2, 4.6), dpi=140)
            data2d = [[weights_2d[i][j] for j in range(len(eps_grid))] for i in range(len(omega_grid))]
            mesh = ax2.imshow(
                data2d,
                origin="lower",
                aspect="auto",
                extent=[min(eps_grid), max(eps_grid), min(omega_grid), max(omega_grid)],
                cmap="viridis",
                interpolation="nearest",
            )
            ax2.set_xlabel("epsilon_em")
            ax2.set_ylabel("Omega_m")
            fig2.colorbar(mesh, ax=ax2, label="posterior weight")
            fig2.tight_layout()
            fig2.savefig(
                str(plot_2d_path),
                format="png",
                dpi=140,
                metadata={
                    "Software": "GSC phase4_desi_bao_epsilon_or_rd_diagnostic",
                    "Creation Time": "2000-01-01T00:00:00Z",
                },
            )
            plt.close(fig2)
        else:
            _write_png_1d_fallback(x=eps_grid, y=eps_probs, out_path=plot_1d_path)
            _write_png_2d_heatmap_fallback(x=eps_grid, y=omega_grid, z_grid=weights_2d, out_path=plot_2d_path)

        dataset_meta = _extract_dataset_meta(bundle.dataset)

        warnings: List[str] = []
        if str(args.covariance_mode) != "full_bundle":
            warnings.append("compact BAO covariance mode: suitable for deterministic baseline diagnostics, not full survey-likelihood replacement")
        if not bool(int(args.emit_plot)):
            warnings.append("emit_plot=0 was requested; plot emission is still enforced for reviewer artifacts")

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "status": "ok",
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "deterministic_mode": bool(deterministic_mode),
            "repo_version_dir": repo_root.name,
            "paths_redacted": True,
            "run_mode": "toy" if toy_mode else "baseline",
            "plot_backend": plot_backend,
            "covariance_mode": str(args.covariance_mode),
            "rd_handling": {
                "mode": "profile_rd" if rd_mode == "profile" else "fixed_rd",
                "rd_m_input": None if rd_m_input is None else float(rd_m_input),
                "profiles_rd_nuisance": bool(rd_mode == "profile"),
                "note": "BAO chi2 handles r_d degeneracy via analytical profiling when rd_mode=profile.",
            },
            "inputs": {
                "dataset_mode": bundle.mode,
                "dataset_relpath": bundle.relpath,
                "dataset_sha256": bundle.sha256,
                "H0_km_s_Mpc": float(h0_km),
                "H0_si": float(h0_si),
                "Tcmb_K": float(args.Tcmb_K),
                "N_eff": float(args.N_eff),
                "omega_m_min": float(args.omega_m_min),
                "omega_m_max": float(args.omega_m_max),
                "omega_m_n": int(args.omega_m_n),
                "epsilon_min": float(args.epsilon_min),
                "epsilon_max": float(args.epsilon_max),
                "epsilon_n": int(args.epsilon_n),
            },
            "dataset_summary": dataset_meta,
            "results": {
                "best_fit": {
                    "chi2_min": float(best.chi2),
                    "ndof": int(best.ndof),
                    "omega_m": float(best.omega_m),
                    "epsilon_em": float(best.epsilon_em),
                    "rd_m": float(best.rd_m),
                },
                "chi2_at_nearest_epsilon_zero": float(chi2_at_eps0),
                "delta_chi2_vs_epsilon_zero": float(best.chi2 - chi2_at_eps0),
                "epsilon_em": eps_stats,
                "omega_m": om_stats,
            },
            "disclaimers": [
                "DR1 compact BAO baseline for deterministic Triangle-1 leg diagnostics.",
                "DR2 BAO/cosmology products are robustness checks when public/available in chosen tooling.",
                "This report is a baseline leg artifact; it is not a full DESI collaboration likelihood replacement.",
            ],
            "warnings": warnings,
            "artifacts": [],
            "portability": {
                "forbidden_absolute_path_match_count": 0,
            },
            **_snapshot_fingerprint(repo_root),
        }

        if manifest_payload is not None and manifest_path is not None:
            payload["data_manifest"] = {
                "relpath": _relative_or_basename(manifest_path, repo_root),
                "sha256": str(manifest_sha),
                "schema": str(manifest_payload.get("schema", "")),
            }
            payload["data_manifest_sha256"] = str(manifest_sha)

        md_lines = [
            "# DESI BAO Triangle-1 Baseline Diagnostic (Phase-4 M156)",
            "",
            "This artifact is a deterministic BAO baseline-leg diagnostic for Triangle-1.",
            "",
            f"- run_mode: `{payload['run_mode']}`",
            f"- covariance_mode: `{payload['covariance_mode']}`",
            f"- rd handling: `{payload['rd_handling']['mode']}`",
            f"- plot backend: `{plot_backend}`",
            "",
            "## Best fit",
            "",
            f"- chi2_min: `{best.chi2:.6f}`",
            f"- ndof: `{best.ndof}`",
            f"- Omega_m_best: `{best.omega_m:.6f}`",
            f"- epsilon_em_best: `{best.epsilon_em:.6f}`",
            f"- rd_m_best: `{best.rd_m:.12e}`",
            "",
            "## Epsilon summary",
            "",
            f"- mean: `{eps_stats['mean']:.6e}`",
            f"- std: `{eps_stats['std']:.6e}`",
            f"- p16/p50/p84: `{eps_stats['p16']:.6e}`, `{eps_stats['p50']:.6e}`, `{eps_stats['p84']:.6e}`",
            "",
            "## Scope note",
            "",
            "- DR1 baseline; DR2 BAO/cosmology products are robustness checks when public/available in chosen likelihood tooling.",
            "- This compact BAO leg is deterministic and schema-validated for reviewer checks.",
        ]
        md_text = "\n".join(md_lines).rstrip() + "\n"
        md_path = outdir / "DESI_BAO_TRIANGLE1_REPORT.md"
        md_path.write_text(md_text, encoding="utf-8")

        # Refresh artifact rows after markdown + plots exist.
        artifacts = []
        for rel, kind in (
            ("epsilon_posterior_1d.png", "plot"),
            ("omega_m_vs_epsilon.png", "plot"),
            ("DESI_BAO_TRIANGLE1_REPORT.md", "report_markdown"),
        ):
            p = outdir / rel
            if p.is_file():
                artifacts.append({"filename": rel, "sha256": _sha256_file(p), "kind": kind})
        payload["artifacts"] = sorted(artifacts, key=lambda row: str(row.get("filename", "")))

        # First JSON render for portability count.
        json_text = _json_pretty(payload)
        abs_count = _count_abs_tokens(json_text) + _count_abs_tokens(md_text)
        payload["portability"]["forbidden_absolute_path_match_count"] = int(abs_count)

        json_text = _json_pretty(payload)
        json_path = outdir / "DESI_BAO_TRIANGLE1_REPORT.json"
        json_path.write_text(json_text, encoding="utf-8")

        if str(args.format) == "json":
            print(json_text, end="")
        else:
            print(f"schema={SCHEMA}")
            print(f"run_mode={payload.get('run_mode')}")
            print(f"dataset={bundle.relpath}")
            print(f"covariance_mode={payload.get('covariance_mode')}")
            print(f"rd_mode={payload['rd_handling']['mode']}")
            print(f"best.chi2={best.chi2:.6f}")
            print(f"best.omega_m={best.omega_m:.6f}")
            print(f"best.epsilon_em={best.epsilon_em:.6f}")
            print(f"best.rd_m={best.rd_m:.12e}")
            print(f"plot_backend={plot_backend}")
            print(f"report_json=DESI_BAO_TRIANGLE1_REPORT.json")

        return 0

    except (UsageError, DiagnosticError) as exc:
        print(f"{FAIL_MARKER}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
