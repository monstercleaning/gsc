#!/usr/bin/env python3
"""Deterministic epsilon sensitivity matrix (toy scaffold, Phase-4 M149 / Task 4B.2)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.epsilon.sensitivity import (  # noqa: E402
    EPS_KEYS,
    default_probe_configs,
    probe_table,
    sensitivity_matrix,
)


TOOL = "phase4_epsilon_sensitivity_matrix_toy"
TOOL_VERSION = "m149-v1"
SCHEMA = "phase4_epsilon_sensitivity_matrix_report_v1"
FAIL_MARKER = "PHASE4_EPSILON_SENSITIVITY_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
DEFAULT_SELF_CHECK_TOL = 1.0e-10
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


class UsageError(Exception):
    """CLI usage/configuration error."""


class DiagnosticError(Exception):
    """Runtime diagnostic failure (self-check or math domain)."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


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


def _require_finite(value: float, *, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise UsageError(f"{name} must be finite")
    return out


def _redact_text(text: str) -> str:
    out = str(text)
    for token in ABS_TOKENS:
        out = out.replace(token, "[abs]/")
    return out


def _matrix_digest(
    *,
    probes: Sequence[str],
    analytic: Mapping[str, Mapping[str, Mapping[str, float]]],
    numeric: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> str:
    lines: List[str] = []
    a_h0 = analytic["d_ln_H0_inferred_d_epsilon"]
    a_s8 = analytic["d_ln_sigma8_inferred_d_epsilon"]
    n_h0 = numeric["d_ln_H0_inferred_d_epsilon"]
    n_s8 = numeric["d_ln_sigma8_inferred_d_epsilon"]

    for probe in probes:
        for key in EPS_KEYS:
            lines.append(
                ",".join(
                    (
                        str(probe),
                        str(key),
                        f"{float(a_h0[probe][key]):.12e}",
                        f"{float(a_s8[probe][key]):.12e}",
                        f"{float(n_h0[probe][key]):.12e}",
                        f"{float(n_s8[probe][key]):.12e}",
                    )
                )
                + "\n"
            )

    h = hashlib.sha256()
    for row in lines:
        h.update(row.encode("utf-8"))
    return h.hexdigest()


def _render_markdown(payload: Mapping[str, Any]) -> str:
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), Mapping) else {}
    self_check = payload.get("self_check") if isinstance(payload.get("self_check"), Mapping) else {}
    probes = payload.get("probe_definitions") if isinstance(payload.get("probe_definitions"), Mapping) else {}

    lines: List[str] = []
    lines.append("# Epsilon Sensitivity Matrix (Toy)")
    lines.append("")
    lines.append("Deterministic sensitivity scaffold for Phase-4 Task 4B.2.")
    lines.append("This is not a likelihood inference and does not claim validated constraints.")
    lines.append("")
    lines.append("## Inputs")
    lines.append(f"- epsilon_em: `{float(inputs.get('epsilon_em', 0.0)):.12g}`")
    lines.append(f"- epsilon_qcd: `{float(inputs.get('epsilon_qcd', 0.0)):.12g}`")
    lines.append(f"- epsilon_gr: `{float(inputs.get('epsilon_gr', 0.0)):.12g}`")
    lines.append(f"- delta_eps: `{float(inputs.get('delta_eps', 0.0)):.12g}`")
    lines.append(f"- h_exponent_p: `{float(inputs.get('h_exponent_p', 0.0)):.12g}`")
    lines.append(f"- growth_exponent_gamma: `{float(inputs.get('growth_exponent_gamma', 0.0)):.12g}`")
    lines.append("")
    lines.append("## Probe pivots")
    for probe_name in sorted(str(k) for k in probes.keys()):
        row = probes.get(probe_name, {})
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- {probe_name}: z={float(row.get('pivot_z', 0.0)):.6g}, weights={json.dumps(row.get('weights', {}), sort_keys=True)}"
        )
    lines.append("")
    lines.append("## Self-check")
    lines.append(f"- tolerance: `{float(self_check.get('tolerance', 0.0)):.3e}`")
    lines.append(f"- max_abs_diff_overall: `{float(self_check.get('max_abs_diff_overall', float('nan'))):.12e}`")
    lines.append(f"- self_check_ok: `{bool(self_check.get('self_check_ok', False))}`")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("```bash")
    lines.append(
        "python3 v11.0.0/scripts/phase4_epsilon_sensitivity_matrix_toy.py --repo-root v11.0.0 --outdir <outdir> --deterministic 1 --format text"
    )
    lines.append(
        "python3 v11.0.0/scripts/phase2_schema_validate.py --auto --schema-dir v11.0.0/schemas --json <outdir>/EPSILON_SENSITIVITY_MATRIX_TOY.json"
    )
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _render_text(payload: Mapping[str, Any]) -> str:
    self_check = payload.get("self_check") if isinstance(payload.get("self_check"), Mapping) else {}
    lines = [
        f"schema={payload.get('schema')}",
        f"status={payload.get('status')}",
        f"repo_version_dir={payload.get('repo_version_dir')}",
        f"paths_redacted={bool(payload.get('paths_redacted'))}",
        f"self_check_ok={bool(self_check.get('self_check_ok'))}",
        f"max_abs_diff_overall={float(self_check.get('max_abs_diff_overall', float('nan'))):.12e}",
    ]
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic epsilon sensitivity matrix (toy scaffold).")
    ap.add_argument("--repo-root", default="v11.0.0")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--format", choices=("json", "text"), default="text")
    ap.add_argument("--deterministic", choices=(0, 1), type=int, default=1)
    ap.add_argument("--created-utc", type=int, default=None)

    ap.add_argument("--epsilon-em", type=float, default=0.0)
    ap.add_argument("--epsilon-qcd", type=float, default=0.0)
    ap.add_argument("--epsilon-gr", type=float, default=0.0)
    ap.add_argument("--delta-eps", type=float, default=1.0e-4)

    ap.add_argument("--z-sn-pivot", type=float, default=0.1)
    ap.add_argument("--z-bao-pivot", type=float, default=0.6)
    ap.add_argument("--z-cmb-pivot", type=float, default=1100.0)
    ap.add_argument("--z-lensing-pivot", type=float, default=0.5)

    ap.add_argument("--h-exponent-p", type=float, default=1.0)
    ap.add_argument("--growth-exponent-gamma", type=float, default=1.0)
    ap.add_argument("--self-check-tol", type=float, default=DEFAULT_SELF_CHECK_TOL)
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

        epsilon = {
            "epsilon_em": _require_finite(args.epsilon_em, name="epsilon_em"),
            "epsilon_qcd": _require_finite(args.epsilon_qcd, name="epsilon_qcd"),
            "epsilon_gr": _require_finite(args.epsilon_gr, name="epsilon_gr"),
        }
        delta_eps = _require_finite(args.delta_eps, name="delta_eps")
        if delta_eps <= 0.0:
            raise UsageError("--delta-eps must be > 0")

        h_exponent_p = _require_finite(args.h_exponent_p, name="h_exponent_p")
        growth_exponent_gamma = _require_finite(args.growth_exponent_gamma, name="growth_exponent_gamma")

        probes = default_probe_configs(
            z_sn_pivot=_require_finite(args.z_sn_pivot, name="z_sn_pivot"),
            z_bao_pivot=_require_finite(args.z_bao_pivot, name="z_bao_pivot"),
            z_cmb_pivot=_require_finite(args.z_cmb_pivot, name="z_cmb_pivot"),
            z_lensing_pivot=_require_finite(args.z_lensing_pivot, name="z_lensing_pivot"),
        )

        matrix = sensitivity_matrix(
            probes=probes,
            epsilon=epsilon,
            h_exponent_p=h_exponent_p,
            growth_exponent_gamma=growth_exponent_gamma,
            delta_eps=delta_eps,
        )
        analytic = matrix["analytic"]
        numeric = matrix["finite_difference"]
        check_raw = matrix["self_check"]

        tolerance = _require_finite(args.self_check_tol, name="self_check_tol")
        if tolerance <= 0.0:
            raise UsageError("--self-check-tol must be > 0")

        max_abs_diff_h0 = float(check_raw["max_abs_diff_d_ln_H0"])
        max_abs_diff_s8 = float(check_raw["max_abs_diff_d_ln_sigma8"])
        max_abs_diff_overall = float(check_raw["max_abs_diff_overall"])
        self_check_ok = bool(max_abs_diff_overall <= tolerance)

        probe_names = [str(p.name) for p in probes]
        digest = _matrix_digest(
            probes=probe_names,
            analytic=analytic,
            numeric=numeric,
        )

        snapshot = _snapshot_fingerprint(repo_root)

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "status": "ok" if self_check_ok else "fail",
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "deterministic_mode": bool(deterministic_mode),
            "repo_version_dir": str(repo_root.name),
            "paths_redacted": True,
            **snapshot,
            "inputs": {
                "epsilon_em": float(epsilon["epsilon_em"]),
                "epsilon_qcd": float(epsilon["epsilon_qcd"]),
                "epsilon_gr": float(epsilon["epsilon_gr"]),
                "delta_eps": float(delta_eps),
                "z_sn_pivot": float(args.z_sn_pivot),
                "z_bao_pivot": float(args.z_bao_pivot),
                "z_cmb_pivot": float(args.z_cmb_pivot),
                "z_lensing_pivot": float(args.z_lensing_pivot),
                "h_exponent_p": float(h_exponent_p),
                "growth_exponent_gamma": float(growth_exponent_gamma),
            },
            "probe_definitions": probe_table(probes),
            "analytic_sensitivities": {
                "d_ln_H0_inferred_d_epsilon": analytic["d_ln_H0_inferred_d_epsilon"],
                "d_ln_sigma8_inferred_d_epsilon": analytic["d_ln_sigma8_inferred_d_epsilon"],
            },
            "finite_difference_sensitivities": {
                "d_ln_H0_inferred_d_epsilon": numeric["d_ln_H0_inferred_d_epsilon"],
                "d_ln_sigma8_inferred_d_epsilon": numeric["d_ln_sigma8_inferred_d_epsilon"],
            },
            "self_check": {
                "max_abs_diff_d_ln_H0": float(max_abs_diff_h0),
                "max_abs_diff_d_ln_sigma8": float(max_abs_diff_s8),
                "max_abs_diff_overall": float(max_abs_diff_overall),
                "tolerance": float(tolerance),
                "self_check_ok": bool(self_check_ok),
            },
            "digests": {
                "sensitivity_table_sha256": str(digest),
            },
            "disclaimers": [
                "toy sensitivity scaffold only",
                "not a likelihood inference",
                "pivot-z probe proxies only",
                "h_exponent_p and growth_exponent_gamma are placeholders",
            ],
            "artifact_paths": {
                "json": "EPSILON_SENSITIVITY_MATRIX_TOY.json",
                "markdown": "EPSILON_SENSITIVITY_MATRIX_TOY.md",
            },
        }

        report_json = outdir / "EPSILON_SENSITIVITY_MATRIX_TOY.json"
        report_md = outdir / "EPSILON_SENSITIVITY_MATRIX_TOY.md"

        report_json.write_text(_json_pretty(payload), encoding="utf-8")
        report_md.write_text(_render_markdown(payload), encoding="utf-8")

        if args.format == "json":
            print(_json_pretty(payload), end="")
        else:
            print(_render_text(payload), end="")

        if not self_check_ok:
            print(
                f"{FAIL_MARKER}: self-check failed (max_abs_diff_overall={max_abs_diff_overall:.12e}, tolerance={tolerance:.12e})",
                file=sys.stderr,
            )
            return 2

        return 0
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (ValueError, DiagnosticError) as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive
        print(f"ERROR: unexpected failure: {_redact_text(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
