#!/usr/bin/env python3
"""Write a reproducibility manifest for a late-time fit run (v11.0.0).

This is meant for referee-grade reproducibility. It records:
- git commit + dirty state
- python executable + version
- `pip freeze`
- sha256 of input datasets actually referenced by the fit JSONs
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from _outdir import resolve_outdir


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception as e:
        return f"<error: {e}>"


def _git_info(repo_root: Path) -> Dict[str, Any]:
    # Best-effort; do not fail if git is unavailable.
    info: Dict[str, Any] = {}
    info["git_commit"] = _run(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
    info["git_branch"] = _run(["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"])
    status = _run(["git", "-C", str(repo_root), "status", "--porcelain=v1"])
    info["git_dirty"] = bool(status and not status.startswith("<error:"))
    if info["git_dirty"]:
        info["git_status_porcelain"] = status.splitlines()[:200]
    return info


def _collect_input_files_from_bao_csv(bao_csv: Path) -> Set[Path]:
    files: Set[Path] = {bao_csv}
    try:
        with bao_csv.open("r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            if r.fieldnames is None:
                return files
            for row in r:
                if not row:
                    continue
                t = (row.get("type") or "").strip()
                if t != "VECTOR_over_rd":
                    continue
                v = (row.get("values_path") or "").strip()
                c = (row.get("cov_path") or "").strip()
                if v:
                    files.add((bao_csv.parent / v).resolve())
                if c:
                    files.add((bao_csv.parent / c).resolve())
    except Exception:
        # Keep best-effort behavior.
        return files
    return files


def _read_csv_column(path: Path, col: str) -> Optional[List[str]]:
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            if r.fieldnames is None or col not in r.fieldnames:
                return None
            out: List[str] = []
            for row in r:
                if not row:
                    continue
                v = (row.get(col) or "").strip()
                if v:
                    out.append(v)
            return out
    except Exception:
        return None


_DATASET_PATH_KEYS = {"sn", "sn_cov", "bao", "drift", "cmb", "cmb_cov"}


def _pantheon_plus_shoes_provenance(path: Path) -> Optional[Dict[str, Any]]:
    # Known fetch URLs from scripts/fetch_pantheon_plus_shoes.sh
    name = path.name
    if name == "Pantheon+SH0ES.dat":
        return {
            "url": "https://raw.githubusercontent.com/PantheonPlusSH0ES/DataRelease/main/Pantheon%2B_Data/4_DISTANCES_AND_COVAR/Pantheon%2BSH0ES.dat",
            "kind": "pantheon_plus_shoes_dat",
        }
    if name == "Pantheon+SH0ES_STAT+SYS.cov":
        return {
            "url": "https://raw.githubusercontent.com/PantheonPlusSH0ES/DataRelease/main/Pantheon%2B_Data/4_DISTANCES_AND_COVAR/Pantheon%2BSH0ES_STAT%2BSYS.cov",
            "kind": "pantheon_plus_shoes_cov_stat_sys",
        }
    return None


def _sha256_text(s: str) -> str:
    h = hashlib.sha256()
    h.update(s.encode("utf-8"))
    return h.hexdigest()


def _relpath(path: Path, *, repo_root: Path) -> str:
    """Return a repo-relative path string if possible (avoids machine-specific absolute paths)."""
    try:
        return str(path.relative_to(repo_root))
    except Exception:
        return str(path)


def _is_chw2018_distance_priors_csv(path: str) -> bool:
    try:
        return Path(path).name.startswith("planck2018_distance_priors_chw2018_")
    except Exception:
        return False


def _rs_star_calibration_for_cmb_path(
    *,
    cmb_path: str,
    cmb_mode: str,
    repo_root: Path,
) -> tuple[float, bool, Optional[str]]:
    """Return (rs_star_calibration, applied, source) for manifest provenance.

    This mirrors the scorecard/fit_grid behavior:
    - apply CHW2018 stopgap calibration only for CHW2018 distance priors in vector mode
    - otherwise calibration is identity (1.0)
    """
    if cmb_mode != "distance_priors" or not _is_chw2018_distance_priors_csv(cmb_path):
        return 1.0, False, None

    try:
        # Keep this import best-effort and local; do not hard-fail manifest generation.
        v101_root = repo_root / "v11.0.0"
        sys.path.insert(0, str(v101_root))
        from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # type: ignore

        return float(_RS_STAR_CALIB_CHW2018), True, "CHW2018 stopgap calibration"
    except Exception:
        # Still record that calibration was intended to be applied, even if we
        # could not import the constant in this environment.
        return 1.0, True, "CHW2018 stopgap calibration (import failed; recorded as 1.0)"


def _python_for_manifest(*, repo_root: Path) -> Path:
    """Choose a stable, portable python path to record in the manifest.

    On macOS, venv python binaries can be symlinks to a system framework python,
    and `sys.executable` may point outside the repo. For portability, prefer a
    path under the repo root when available (typically `sys.prefix/bin/python`).
    """
    exe = Path(sys.executable)
    exe = exe.absolute() if not exe.is_absolute() else exe
    try:
        exe.relative_to(repo_root)
        return exe
    except Exception:
        pass

    prefix = Path(getattr(sys, "prefix", "")).absolute()
    for name in ("python", "python3", f"python{sys.version_info.major}", f"python{sys.version_info.major}.{sys.version_info.minor}"):
        cand = prefix / "bin" / name
        if cand.exists():
            try:
                cand.relative_to(repo_root)
                return cand
            except Exception:
                continue

    # Fall back to sys.executable (may be absolute outside the repo).
    return exe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit-dir", type=Path, default=Path("v11.0.0/results/late_time_fit"))
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="outdir",
        type=Path,
        default=None,
        help="Output root used when --out is not set (CLI > GSC_OUTDIR > artifacts/release).",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    fit_dir = args.fit_dir.resolve()
    if args.out is not None:
        out_path = Path(args.out).expanduser().resolve()
    else:
        out_root = resolve_outdir(args.outdir, v101_dir=Path(__file__).resolve().parents[1])
        out_path = (out_root / "manifest" / "manifest.json").resolve()
    print(f"[info] OUTDIR={out_path.parent}")

    repo_root = Path(__file__).resolve().parents[2]

    # Load fit JSONs to discover inputs.
    fit_jsons = sorted(fit_dir.glob("*_bestfit.json"))
    if not fit_jsons:
        raise SystemExit(f"No bestfit JSONs found in: {fit_dir}")

    inputs: Set[Path] = set()
    datasets_by_model: Dict[str, Dict[str, str]] = {}
    early_time_by_model: Dict[str, Dict[str, Any]] = {}
    cmb_by_model: Dict[str, Dict[str, Any]] = {}
    for p in fit_jsons:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        model = str(obj.get("model", p.stem.replace("_bestfit", "")))
        ds = obj.get("datasets", {}) if isinstance(obj.get("datasets"), dict) else {}
        ds_str: Dict[str, str] = {}
        for k, v in ds.items():
            if k not in _DATASET_PATH_KEYS or not v:
                continue
            try:
                ds_str[k] = _relpath(Path(str(v)).resolve(), repo_root=repo_root)
            except Exception:
                ds_str[k] = str(v)
        datasets_by_model[model] = ds_str
        et = obj.get("early_time", {}) if isinstance(obj.get("early_time"), dict) else {}
        early_time_by_model[model] = et
        cmb_cfg = obj.get("cmb", {}) if isinstance(obj.get("cmb"), dict) else {}
        # Normalize any embedded file paths to repo-relative strings for portability.
        cmb_norm: Dict[str, Any] = {}
        for k, v in cmb_cfg.items():
            if k in {"path", "cov_path"} and v:
                try:
                    cmb_norm[k] = _relpath(Path(str(v)).resolve(), repo_root=repo_root)
                except Exception:
                    cmb_norm[k] = v
            else:
                cmb_norm[k] = v

        # Record rs*(z*) calibration provenance when CMB priors are used.
        if cmb_norm.get("path") and cmb_norm.get("mode"):
            rs_star_calib, rs_applied, rs_source = _rs_star_calibration_for_cmb_path(
                cmb_path=str(cmb_norm["path"]),
                cmb_mode=str(cmb_norm["mode"]),
                repo_root=repo_root,
            )
            cmb_norm["rs_star_calibration"] = rs_star_calib
            cmb_norm["rs_star_calibration_applied"] = rs_applied
            if rs_source:
                cmb_norm["rs_star_calibration_source"] = rs_source
        cmb_by_model[model] = cmb_norm
        for k, v in ds_str.items():
            try:
                # ds_str is stored as repo-relative; resolve for hashing.
                inputs.add((repo_root / Path(v)).resolve())
            except Exception:
                continue

    # Expand BAO referenced files (values/cov) for each BAO CSV we saw.
    for p in list(inputs):
        if p.name.endswith(".csv") and ("data/bao" in str(p).replace("\\", "/")):
            inputs |= _collect_input_files_from_bao_csv(p)

    # Compute hashes (best-effort).
    inputs_sha256: Dict[str, str] = {}
    inputs_size_bytes: Dict[str, int] = {}
    fetched: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    for p in sorted(inputs):
        key = _relpath(p, repo_root=repo_root)
        if not p.exists():
            missing.append(key)
            continue
        try:
            inputs_sha256[key] = _sha256(p)
            inputs_size_bytes[key] = int(p.stat().st_size)
        except Exception as e:
            inputs_sha256[key] = f"<error: {e}>"

        prov = _pantheon_plus_shoes_provenance(p)
        if prov is not None:
            fetched[key] = {
                **prov,
                "size_bytes": int(p.stat().st_size),
                "sha256": inputs_sha256.get(key),
            }

    # Record exact SN row selection when available (row_full indices).
    sn_row_full: Dict[str, Any] = {}
    for model, ds in datasets_by_model.items():
        sn_csv = ds.get("sn")
        if not sn_csv:
            continue
        sn_p = repo_root / Path(sn_csv)
        if not sn_p.exists():
            continue
        col = _read_csv_column(sn_p, "row_full")
        if not col:
            continue
        try:
            idx = [int(float(x)) for x in col]
        except Exception:
            continue
        # Store a compact summary + the exact list for dispute-free provenance.
        idx_str = ",".join(str(i) for i in idx)
        sn_row_full[model] = {
            "sn_csv": _relpath(sn_p.resolve(), repo_root=repo_root),
            "n_subset": int(len(idx)),
            "min": int(min(idx)) if idx else None,
            "max": int(max(idx)) if idx else None,
            "sha256": _sha256_text(idx_str),
            "indices": idx,
        }

    manifest: Dict[str, Any] = {
        "manifest_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "python": _relpath(_python_for_manifest(repo_root=repo_root), repo_root=repo_root),
        "python_version": sys.version,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "pip_freeze": _run([sys.executable, "-m", "pip", "freeze"]),
        "fit_dir": _relpath(fit_dir, repo_root=repo_root),
        "fit_jsons": [_relpath(p, repo_root=repo_root) for p in fit_jsons],
        "datasets_by_model": datasets_by_model,
        "early_time_by_model": early_time_by_model,
        "cmb_by_model": cmb_by_model,
        "inputs_sha256": inputs_sha256,
        "inputs_size_bytes": inputs_size_bytes,
        "sn_row_full": sn_row_full,
        "fetched_artifacts": fetched,
        "missing_inputs": missing,
        "env": {
            "MPLBACKEND": os.environ.get("MPLBACKEND"),
            "MPLCONFIGDIR": (
                _relpath(Path(os.environ["MPLCONFIGDIR"]).resolve(), repo_root=repo_root)
                if os.environ.get("MPLCONFIGDIR")
                else None
            ),
        },
    }
    manifest.update(_git_info(repo_root))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {out_path}")


if __name__ == "__main__":
    main()
