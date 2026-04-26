#!/usr/bin/env python3
"""Deterministic epsilon translator MVP report (Phase-4 M148 / Task 4B.1)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.epsilon.translator import (  # noqa: E402
    EpsilonVectorV1,
    mismatch_metrics,
    one_plus_z_from_sigma_ratio,
)


TOOL = "phase4_epsilon_translator_mvp"
TOOL_VERSION = "m148-v1"
SCHEMA = "phase4_epsilon_translator_report_v1"
FAIL_MARKER = "PHASE4_EPSILON_TRANSLATOR_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


class UsageError(Exception):
    """CLI usage/configuration error."""


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


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _linear_grid(vmin: float, vmax: float, n: int) -> List[float]:
    if int(n) < 2:
        raise UsageError("--n must be >= 2")
    lo = float(vmin)
    hi = float(vmax)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise UsageError("sigma-ratio bounds must be finite")
    if lo <= 0.0:
        raise UsageError("--sigma-ratio-min must be > 0")
    if hi < lo:
        raise UsageError("--sigma-ratio-max must be >= --sigma-ratio-min")
    if int(n) == 2:
        return [lo, hi]
    step = (hi - lo) / float(int(n) - 1)
    return [float(lo + i * step) for i in range(int(n))]


def _redact_text(text: str) -> str:
    out = str(text)
    for token in ABS_TOKENS:
        out = out.replace(token, "[abs]/")
    return out


def _render_markdown(payload: Mapping[str, Any]) -> str:
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), Mapping) else {}
    summary = payload.get("grid_summary") if isinstance(payload.get("grid_summary"), Mapping) else {}
    mismatch = payload.get("mismatch_metrics") if isinstance(payload.get("mismatch_metrics"), Mapping) else {}

    lines: List[str] = []
    lines.append("# Epsilon Translator MVP Report")
    lines.append("")
    lines.append("Deterministic translator MVP artifact for Phase-4 Task 4B.1.")
    lines.append("This report uses a toy ansatz and does not claim validated physics constraints.")
    lines.append("")
    lines.append("## Inputs")
    lines.append(f"- epsilon_em: `{float(inputs.get('epsilon_em', 0.0)):.12g}`")
    lines.append(f"- epsilon_qcd: `{float(inputs.get('epsilon_qcd', 0.0)):.12g}`")
    if inputs.get("epsilon_gr") is None:
        lines.append("- epsilon_gr: `null`")
    else:
        lines.append(f"- epsilon_gr: `{float(inputs.get('epsilon_gr')):.12g}`")
    lines.append(f"- sigma_ratio_min: `{float(inputs.get('sigma_ratio_min', 0.0)):.12g}`")
    lines.append(f"- sigma_ratio_max: `{float(inputs.get('sigma_ratio_max', 0.0)):.12g}`")
    lines.append(f"- n: `{int(inputs.get('n', 0))}`")
    lines.append("")
    lines.append("## Grid summary")
    lines.append(f"- n_points: `{int(summary.get('n_points', 0))}`")
    lines.append(
        f"- delta_ln_1pz range: `[{float(summary.get('delta_ln_1pz_min', float('nan'))):.12e}, {float(summary.get('delta_ln_1pz_max', float('nan'))):.12e}]`"
    )
    lines.append(
        f"- delta_z range: `[{float(summary.get('delta_z_min', float('nan'))):.12e}, {float(summary.get('delta_z_max', float('nan'))):.12e}]`"
    )
    lines.append("")
    lines.append("## Mismatch metrics")
    lines.append(
        f"- max_abs_delta_ln_1pz_em_minus_qcd: `{float(mismatch.get('max_abs_delta_ln_1pz_em_minus_qcd', float('nan'))):.12e}`"
    )
    lines.append(
        f"- rms_delta_ln_1pz_em_minus_qcd: `{float(mismatch.get('rms_delta_ln_1pz_em_minus_qcd', float('nan'))):.12e}`"
    )
    lines.append(
        f"- max_abs_delta_z_em_minus_qcd: `{float(mismatch.get('max_abs_delta_z_em_minus_qcd', float('nan'))):.12e}`"
    )
    lines.append("")
    lines.append("## Reproduce")
    lines.append("```bash")
    lines.append(
        "python3 v11.0.0/scripts/phase4_epsilon_translator_mvp.py --repo-root v11.0.0 --outdir <outdir> --deterministic 1 --format text"
    )
    lines.append("python3 v11.0.0/scripts/phase2_schema_validate.py --auto --schema-dir v11.0.0/schemas --json <outdir>/EPSILON_TRANSLATOR_MVP.json")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _render_text(payload: Mapping[str, Any]) -> str:
    mismatch = payload.get("mismatch_metrics") if isinstance(payload.get("mismatch_metrics"), Mapping) else {}
    lines = [
        f"schema={payload.get('schema')}",
        f"status={payload.get('status')}",
        f"repo_version_dir={payload.get('repo_version_dir')}",
        f"paths_redacted={bool(payload.get('paths_redacted'))}",
        f"n_points={int(mismatch.get('n_points', 0))}",
        "metrics="
        + f"max_abs_delta_ln_1pz={float(mismatch.get('max_abs_delta_ln_1pz_em_minus_qcd', float('nan'))):.12e} "
        + f"max_abs_delta_z={float(mismatch.get('max_abs_delta_z_em_minus_qcd', float('nan'))):.12e}",
    ]
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic epsilon translator MVP report generator.")
    ap.add_argument("--repo-root", default="v11.0.0")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--deterministic", choices=(0, 1), type=int, default=1)
    ap.add_argument("--format", choices=("json", "text"), default="json")
    ap.add_argument("--created-utc", type=int, default=None)

    ap.add_argument("--epsilon-em", type=float, default=0.0)
    ap.add_argument("--epsilon-qcd", type=float, default=0.0)
    ap.add_argument("--epsilon-gr", type=float, default=None)

    ap.add_argument("--sigma-ratio-min", type=float, default=1.0)
    ap.add_argument("--sigma-ratio-max", type=float, default=6.0)
    ap.add_argument("--n", type=int, default=11)
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

        eps_vec = EpsilonVectorV1(
            epsilon_em=float(args.epsilon_em),
            epsilon_qcd=float(args.epsilon_qcd),
            epsilon_gr=None if args.epsilon_gr is None else float(args.epsilon_gr),
        )

        sigma_ratio_grid = _linear_grid(float(args.sigma_ratio_min), float(args.sigma_ratio_max), int(args.n))

        rows: List[Dict[str, Any]] = []
        delta_ln_values: List[float] = []
        delta_z_values: List[float] = []

        for sr in sigma_ratio_grid:
            onepz_em = one_plus_z_from_sigma_ratio(sr, eps_vec.epsilon_em)
            onepz_qcd = one_plus_z_from_sigma_ratio(sr, eps_vec.epsilon_qcd)
            z_em = onepz_em - 1.0
            z_qcd = onepz_qcd - 1.0
            delta_ln = math.log(onepz_em) - math.log(onepz_qcd)
            delta_z = z_em - z_qcd

            row: Dict[str, Any] = {
                "sigma_ratio": float(sr),
                "one_plus_z_em": float(onepz_em),
                "one_plus_z_qcd": float(onepz_qcd),
                "delta_ln_1pz_em_minus_qcd": float(delta_ln),
                "delta_z_em_minus_qcd": float(delta_z),
            }
            if eps_vec.epsilon_gr is not None:
                row["one_plus_z_gr"] = float(one_plus_z_from_sigma_ratio(sr, eps_vec.epsilon_gr))
            rows.append(row)
            delta_ln_values.append(float(delta_ln))
            delta_z_values.append(float(delta_z))

        mismatch = mismatch_metrics(
            sigma_ratio_grid=sigma_ratio_grid,
            eps_em=eps_vec.epsilon_em,
            eps_qcd=eps_vec.epsilon_qcd,
        )

        snapshot = _snapshot_fingerprint(repo_root)

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "status": "ok",
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "deterministic_mode": bool(deterministic_mode),
            "repo_version_dir": str(repo_root.name),
            "repo_snapshot_manifest_sha256": str(snapshot["repo_snapshot_manifest_sha256"]),
            "repo_snapshot_manifest_source": str(snapshot["repo_snapshot_manifest_source"]),
            "paths_redacted": True,
            "toy_ansatz": {
                "name": "sigma_ratio_power_law_mvp",
                "definition": "1_plus_z_sector = sigma_ratio ** (1 + epsilon_sector)",
                "scope_note": "MVP translator toy ansatz; not a validated physical derivation.",
            },
            "inputs": {
                "epsilon_em": float(eps_vec.epsilon_em),
                "epsilon_qcd": float(eps_vec.epsilon_qcd),
                "epsilon_gr": None if eps_vec.epsilon_gr is None else float(eps_vec.epsilon_gr),
                "sigma_ratio_min": float(sigma_ratio_grid[0]),
                "sigma_ratio_max": float(sigma_ratio_grid[-1]),
                "n": int(len(sigma_ratio_grid)),
            },
            "grid_summary": {
                "n_points": int(len(rows)),
                "sigma_ratio_min": float(sigma_ratio_grid[0]),
                "sigma_ratio_max": float(sigma_ratio_grid[-1]),
                "delta_ln_1pz_min": float(min(delta_ln_values)),
                "delta_ln_1pz_max": float(max(delta_ln_values)),
                "delta_z_min": float(min(delta_z_values)),
                "delta_z_max": float(max(delta_z_values)),
                "grid_digest_sha256": hashlib.sha256(
                    "".join(
                        f"{_fmt_e(r['sigma_ratio'])},{_fmt_e(r['one_plus_z_em'])},{_fmt_e(r['one_plus_z_qcd'])},{_fmt_e(r['delta_ln_1pz_em_minus_qcd'])},{_fmt_e(r['delta_z_em_minus_qcd'])}\n"
                        for r in rows
                    ).encode("utf-8")
                ).hexdigest(),
            },
            "mismatch_metrics": mismatch,
            "grid_rows": rows,
            "artifact_paths": {
                "json": "EPSILON_TRANSLATOR_MVP.json",
                "markdown": "EPSILON_TRANSLATOR_MVP.md",
            },
            "runtime": {
                "python": platform.python_version(),
                "platform": _redact_text(platform.platform()),
            },
        }

        report_json = outdir / "EPSILON_TRANSLATOR_MVP.json"
        report_md = outdir / "EPSILON_TRANSLATOR_MVP.md"

        report_json.write_text(_json_pretty(payload), encoding="utf-8")
        report_md.write_text(_render_markdown(payload), encoding="utf-8")

        if str(args.format) == "json":
            print(_json_pretty(payload), end="")
        else:
            print(_render_text(payload), end="")

        return 0
    except UsageError as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
