#!/usr/bin/env python3
"""Build deterministic Paper-2 artifact pack from Phase-4 SN/BAO/Triangle-1 runners."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


SCHEMA = "phase4_paper2_artifacts_manifest_v1"
TOOL = "phase4_make_paper2_artifacts"
TOOL_VERSION = "m158-v1"
FAIL_MARKER = "PHASE4_PAPER2_ARTIFACTS_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


class UsageError(Exception):
    """CLI/configuration error."""


class ArtifactError(Exception):
    """Runtime failure while building artifacts."""


@dataclass(frozen=True)
class RunResult:
    name: str
    outdir: Path
    report_json: Path
    payload: Dict[str, Any]


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
        raise UsageError("--created-utc must be integer epoch seconds") from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_path_from_repo(repo_root: Path, raw_path: str) -> Path:
    p = Path(str(raw_path)).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (repo_root / p).resolve()


def _path_arg(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
        if rel in ("", "."):
            return repo_root.name
        return f"{repo_root.name}/{rel}"
    except Exception:
        return str(path.resolve())


def _load_json(path: Path, *, name: str) -> Dict[str, Any]:
    if not path.is_file():
        raise ArtifactError(f"missing {name}: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ArtifactError(f"failed to parse {name}: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ArtifactError(f"{name} must be JSON object")
    return payload


def _manifest_sha(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    if not path.is_file():
        raise UsageError(f"manifest file not found: {path}")
    return _sha256_file(path)


def _sanitize_text(text: str, repo_root: Path) -> str:
    out = str(text)
    for token in ABS_TOKENS:
        out = out.replace(token, "<ABS>/")
    out = out.replace(str(repo_root.resolve()), repo_root.name)
    return out


def _require_file(path: Path, *, label: str) -> Path:
    if not path.is_file():
        raise ArtifactError(f"missing {label}: {path}")
    return path


def _extract_from_manifest(manifest_path: Optional[Path], key: str) -> Optional[Path]:
    if manifest_path is None:
        return None
    payload = _load_json(manifest_path, name="manifest")
    files = payload.get("files")
    if not isinstance(files, Mapping):
        return None
    entry = files.get(key)
    if not isinstance(entry, Mapping):
        return None

    name = entry.get("filename")
    if not isinstance(name, str) or not name.strip():
        name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    p = Path(name)
    if p.is_absolute():
        return p if p.is_file() else None
    cand = (manifest_path.parent / p).resolve()
    if cand.is_file():
        return cand
    return None


def _subprocess_run(cmd_exec: Sequence[str], *, cwd: Path, name: str, repo_root: Path) -> None:
    proc = subprocess.run(
        list(cmd_exec),
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        err = _sanitize_text((proc.stdout or "") + "\n" + (proc.stderr or ""), repo_root)
        err = err[-1200:]
        raise ArtifactError(f"{name} failed (exit={proc.returncode}): {err}")


def _write_summary(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(_json_pretty(payload), encoding="utf-8")


def _copy_artifact(src: Path, dst: Path) -> Dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return {
        "filename": dst.name,
        "sha256": _sha256_file(dst),
        "bytes": int(dst.stat().st_size),
    }


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


def _run_pantheon(
    *,
    repo_root: Path,
    outdir: Path,
    run_mode: str,
    created_epoch: int,
    pantheon_manifest: Optional[Path],
    dataset: Optional[Path],
    covariance: Optional[Path],
) -> RunResult:
    rel_script = f"{repo_root.name}/scripts/phase4_pantheon_plus_epsilon_posterior.py"
    cmd_display: List[str] = [
        "python3",
        rel_script,
        "--repo-root",
        repo_root.name,
        "--outdir",
        _path_arg(outdir, repo_root),
        "--deterministic",
        "1",
        "--created-utc",
        str(int(created_epoch)),
        "--run-mode",
        run_mode,
        "--format",
        "text",
    ]

    if run_mode == "demo":
        cmd_display.extend(["--toy", "1", "--omega-m-n", "9", "--epsilon-n", "9", "--integration-n", "512"])
    else:
        cmd_display.extend(["--covariance-mode", "full"])
        if dataset is None:
            raise UsageError("paper_grade requires Pantheon dataset path")
        if covariance is None:
            raise UsageError("paper_grade requires Pantheon covariance path")
        cmd_display.extend(["--dataset", _path_arg(dataset, repo_root)])
        cmd_display.extend(["--covariance", _path_arg(covariance, repo_root)])
        if pantheon_manifest is None:
            raise UsageError("paper_grade requires --pantheon-manifest")
        cmd_display.extend(["--data-manifest", _path_arg(pantheon_manifest, repo_root)])

    cmd_exec = [sys.executable] + cmd_display[1:]
    _subprocess_run(cmd_exec, cwd=repo_root.parent, name="pantheon", repo_root=repo_root)

    report = _require_file(outdir / "PANTHEON_EPSILON_POSTERIOR_REPORT.json", label="Pantheon report")
    payload = _load_json(report, name="Pantheon report")
    return RunResult(name="pantheon", outdir=outdir, report_json=report, payload=payload)


def _run_bao(
    *,
    repo_root: Path,
    outdir: Path,
    run_mode: str,
    created_epoch: int,
    desi_manifest: Optional[Path],
    bao_dataset: Path,
) -> RunResult:
    rel_script = f"{repo_root.name}/scripts/phase4_desi_bao_epsilon_or_rd_diagnostic.py"
    cmd_display: List[str] = [
        "python3",
        rel_script,
        "--repo-root",
        repo_root.name,
        "--outdir",
        _path_arg(outdir, repo_root),
        "--deterministic",
        "1",
        "--created-utc",
        str(int(created_epoch)),
        "--format",
        "text",
    ]

    if run_mode == "demo":
        cmd_display.extend(["--toy", "1", "--omega-m-n", "9", "--epsilon-n", "9"])
    else:
        cmd_display.extend(["--dataset", _path_arg(bao_dataset, repo_root)])
        if desi_manifest is None:
            raise UsageError("paper_grade requires --desi-bao-manifest")
        cmd_display.extend(["--data-manifest", _path_arg(desi_manifest, repo_root)])

    cmd_exec = [sys.executable] + cmd_display[1:]
    _subprocess_run(cmd_exec, cwd=repo_root.parent, name="desi_bao", repo_root=repo_root)

    report = _require_file(outdir / "DESI_BAO_TRIANGLE1_REPORT.json", label="DESI BAO report")
    payload = _load_json(report, name="DESI BAO report")
    return RunResult(name="desi_bao", outdir=outdir, report_json=report, payload=payload)


def _run_joint(
    *,
    repo_root: Path,
    outdir: Path,
    run_mode: str,
    created_epoch: int,
    pantheon_manifest: Optional[Path],
    desi_manifest: Optional[Path],
    dataset: Optional[Path],
    covariance: Optional[Path],
    bao_dataset: Path,
) -> RunResult:
    rel_script = f"{repo_root.name}/scripts/phase4_triangle1_joint_sn_bao_epsilon_posterior.py"
    cmd_display: List[str] = [
        "python3",
        rel_script,
        "--repo-root",
        repo_root.name,
        "--outdir",
        _path_arg(outdir, repo_root),
        "--deterministic",
        "1",
        "--created-utc",
        str(int(created_epoch)),
        "--run-mode",
        run_mode,
        "--format",
        "text",
    ]

    if run_mode == "demo":
        cmd_display.extend(["--toy", "1", "--omega-m-steps", "9", "--epsilon-steps", "9", "--integration-n", "512"])
    else:
        cmd_display.extend(["--covariance-mode", "full"])
        if dataset is None:
            raise UsageError("paper_grade requires Pantheon mu dataset path")
        if covariance is None:
            raise UsageError("paper_grade requires Pantheon covariance path")
        if pantheon_manifest is None:
            raise UsageError("paper_grade requires --pantheon-manifest")
        cmd_display.extend(["--pantheon-mu-csv", _path_arg(dataset, repo_root)])
        cmd_display.extend(["--pantheon-covariance", _path_arg(covariance, repo_root)])
        cmd_display.extend(["--pantheon-data-manifest", _path_arg(pantheon_manifest, repo_root)])
        cmd_display.extend(["--bao-baseline-csv", _path_arg(bao_dataset, repo_root)])
        if desi_manifest is not None:
            cmd_display.extend(["--bao-data-manifest", _path_arg(desi_manifest, repo_root)])

    cmd_exec = [sys.executable] + cmd_display[1:]
    _subprocess_run(cmd_exec, cwd=repo_root.parent, name="triangle1_joint", repo_root=repo_root)

    report = _require_file(outdir / "TRIANGLE1_JOINT_SN_BAO_REPORT.json", label="Triangle-1 joint report")
    payload = _load_json(report, name="Triangle-1 joint report")
    return RunResult(name="triangle1_joint", outdir=outdir, report_json=report, payload=payload)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build deterministic Paper-2 SN/BAO/Triangle-1 artifact pack.")
    ap.add_argument("--repo-root", default="v11.0.0")
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--run-mode", choices=("demo", "paper_grade"), default="demo")
    ap.add_argument("--pantheon-manifest", default=None)
    ap.add_argument("--desi-bao-manifest", default=None)
    ap.add_argument("--pantheon-dataset", default=None)
    ap.add_argument("--pantheon-covariance", default=None)
    ap.add_argument("--bao-baseline-csv", default="data/bao/desi/desi_dr1_bao_baseline.csv")
    ap.add_argument("--created-utc", type=int, default=None)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        repo_root = Path(str(args.repo_root)).expanduser().resolve()
        if not repo_root.is_dir():
            raise UsageError(f"repo-root not found: {repo_root}")

        if args.created_utc is None:
            created_epoch = DEFAULT_CREATED_UTC_EPOCH
        else:
            created_epoch = int(args.created_utc)
        created_utc = _to_iso_utc(created_epoch)

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        run_mode = str(args.run_mode)
        seed = int(args.seed)

        pantheon_manifest = _resolve_path_from_repo(repo_root, args.pantheon_manifest) if args.pantheon_manifest else None
        desi_manifest = _resolve_path_from_repo(repo_root, args.desi_bao_manifest) if args.desi_bao_manifest else None

        pantheon_dataset = _resolve_path_from_repo(repo_root, args.pantheon_dataset) if args.pantheon_dataset else None
        pantheon_cov = _resolve_path_from_repo(repo_root, args.pantheon_covariance) if args.pantheon_covariance else None
        if run_mode == "paper_grade":
            if pantheon_manifest is None:
                raise UsageError("--run-mode paper_grade requires --pantheon-manifest")
            if desi_manifest is None:
                raise UsageError("--run-mode paper_grade requires --desi-bao-manifest")
            if pantheon_dataset is None:
                pantheon_dataset = _extract_from_manifest(pantheon_manifest, "mu")
            if pantheon_cov is None:
                pantheon_cov = _extract_from_manifest(pantheon_manifest, "cov")
            if pantheon_dataset is None or pantheon_cov is None:
                raise UsageError(
                    "paper_grade requires --pantheon-dataset/--pantheon-covariance or resolvable mu/cov entries in pantheon manifest"
                )

        bao_dataset = _resolve_path_from_repo(repo_root, str(args.bao_baseline_csv))
        if not bao_dataset.is_file():
            raise UsageError(f"BAO dataset not found: {bao_dataset}")

        subroot = outdir / "_subruns"
        sn_out = subroot / "sn"
        bao_out = subroot / "bao"
        joint_out = subroot / "joint"
        for d in (sn_out, bao_out, joint_out):
            d.mkdir(parents=True, exist_ok=True)

        sn_res = _run_pantheon(
            repo_root=repo_root,
            outdir=sn_out,
            run_mode=run_mode,
            created_epoch=created_epoch,
            pantheon_manifest=pantheon_manifest,
            dataset=pantheon_dataset,
            covariance=pantheon_cov,
        )
        bao_res = _run_bao(
            repo_root=repo_root,
            outdir=bao_out,
            run_mode=run_mode,
            created_epoch=created_epoch,
            desi_manifest=desi_manifest,
            bao_dataset=bao_dataset,
        )
        joint_res = _run_joint(
            repo_root=repo_root,
            outdir=joint_out,
            run_mode=run_mode,
            created_epoch=created_epoch,
            pantheon_manifest=pantheon_manifest,
            desi_manifest=desi_manifest,
            dataset=pantheon_dataset,
            covariance=pantheon_cov,
            bao_dataset=bao_dataset,
        )

        # Summary JSONs for paper drafting.
        sn_summary = {
            "schema": str(sn_res.payload.get("schema", "")),
            "run_mode": str(sn_res.payload.get("run_mode", "")),
            "covariance_mode": str(sn_res.payload.get("covariance_mode", "")),
            "best_fit": dict(sn_res.payload.get("results", {}).get("best_fit", {})),
            "epsilon_em": dict(sn_res.payload.get("results", {}).get("epsilon_em", {})),
            "omega_m": dict(sn_res.payload.get("results", {}).get("omega_m", {})),
        }
        bao_summary = {
            "schema": str(bao_res.payload.get("schema", "")),
            "run_mode": str(bao_res.payload.get("run_mode", "")),
            "rd_handling": dict(bao_res.payload.get("rd_handling", {})),
            "best_fit": dict(bao_res.payload.get("results", {}).get("best_fit", {})),
            "epsilon_em": dict(bao_res.payload.get("results", {}).get("epsilon_em", {})),
            "omega_m": dict(bao_res.payload.get("results", {}).get("omega_m", {})),
        }
        joint_summary = {
            "schema": str(joint_res.payload.get("schema", "")),
            "run_mode": str(joint_res.payload.get("run_mode", "")),
            "covariance_mode": str(joint_res.payload.get("covariance_mode", "")),
            "best_fit": dict(joint_res.payload.get("results", {}).get("best_fit", {})),
            "epsilon_em": dict(joint_res.payload.get("results", {}).get("epsilon_em", {})),
            "omega_m": dict(joint_res.payload.get("results", {}).get("omega_m", {})),
            "assumptions": dict(joint_res.payload.get("assumptions", {})),
        }

        sn_summary_path = outdir / "sn_epsilon_posterior_summary.json"
        bao_summary_path = outdir / "bao_leg_summary.json"
        joint_summary_path = outdir / "sn_bao_joint_summary.json"
        _write_summary(sn_summary_path, sn_summary)
        _write_summary(bao_summary_path, bao_summary)
        _write_summary(joint_summary_path, joint_summary)

        # Paper-facing figure names.
        artifacts: List[Dict[str, Any]] = []
        artifacts.append(_copy_artifact(joint_out / "epsilon_posterior_1d.png", outdir / "epsilon_posterior_1d.png"))
        artifacts.append(_copy_artifact(joint_out / "omega_m_vs_epsilon.png", outdir / "omega_m_vs_epsilon.png"))
        artifacts.append(_copy_artifact(bao_out / "omega_m_vs_epsilon.png", outdir / "bao_rd_degeneracy.png"))
        artifacts.append(_copy_artifact(joint_out / "omega_m_vs_epsilon.png", outdir / "joint_corner_or_equivalent.png"))

        # Include summaries/report json in artifact listing.
        for p in (sn_summary_path, bao_summary_path, joint_summary_path):
            artifacts.append({"filename": p.name, "sha256": _sha256_file(p), "bytes": int(p.stat().st_size)})

        manifest_payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "deterministic_mode": True,
            "paths_redacted": True,
            "run_mode": run_mode,
            "seed": seed,
            "inputs": {
                "pantheon_manifest_basename": pantheon_manifest.name if pantheon_manifest is not None else None,
                "pantheon_manifest_sha256": _manifest_sha(pantheon_manifest),
                "desi_bao_manifest_basename": desi_manifest.name if desi_manifest is not None else None,
                "desi_bao_manifest_sha256": _manifest_sha(desi_manifest),
                "bao_dataset": bao_dataset.relative_to(repo_root).as_posix() if bao_dataset.is_file() else bao_dataset.name,
            },
            "subtool_reports": {
                "pantheon": {
                    "report": sn_res.report_json.name,
                    "report_sha256": _sha256_file(sn_res.report_json),
                },
                "desi_bao": {
                    "report": bao_res.report_json.name,
                    "report_sha256": _sha256_file(bao_res.report_json),
                },
                "triangle1_joint": {
                    "report": joint_res.report_json.name,
                    "report_sha256": _sha256_file(joint_res.report_json),
                },
            },
            "artifacts": sorted(artifacts, key=lambda row: str(row.get("filename", ""))),
            **_snapshot_fingerprint(repo_root),
        }

        row_lines = [
            f"{row['filename']},{row['sha256']},{row['bytes']}\n"
            for row in manifest_payload["artifacts"]
            if isinstance(row, Mapping) and row.get("filename") and row.get("sha256")
        ]
        manifest_payload["digests"] = {
            "artifact_table_sha256": _sha256_bytes("".join(sorted(row_lines)).encode("utf-8")),
        }

        manifest_json = _json_pretty(manifest_payload)
        if any(tok in manifest_json for tok in ABS_TOKENS):
            raise ArtifactError("manifest contains absolute-path tokens")

        manifest_path = outdir / "artifacts_manifest.json"
        manifest_path.write_text(manifest_json, encoding="utf-8")

        if str(args.format) == "json":
            print(manifest_json, end="")
        else:
            print(f"schema={SCHEMA}")
            print(f"run_mode={run_mode}")
            print(f"seed={seed}")
            print(f"artifacts={len(manifest_payload['artifacts'])}")
            print(f"manifest={manifest_path.name}")
        return 0

    except (UsageError, ArtifactError) as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
