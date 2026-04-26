"""Unified CLI entrypoint for Phase-2 operational scripts (additive wrapper)."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Optional, Sequence


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def _add_leaf(
    subparsers: argparse._SubParsersAction,
    *,
    name: str,
    script_name: str,
    command_label: str,
    help_text: str,
) -> None:
    parser = subparsers.add_parser(
        name,
        help=help_text,
        description=f"{command_label} -> {script_name}",
    )
    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the wrapped script. Use '-- <args>' for clarity.",
    )
    parser.set_defaults(script_name=script_name, command_label=command_label)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="gsc",
        description="Unified additive wrapper for GSC Phase-2 scripts.",
    )
    level1 = ap.add_subparsers(dest="scope", required=True)

    phase2 = level1.add_parser("phase2", help="Phase-2 operational tools")
    level2 = phase2.add_subparsers(dest="domain", required=True)

    e2 = level2.add_parser("e2", help="Early-time E2 scan/bundle tooling")
    e2_level = e2.add_subparsers(dest="command", required=True)
    _add_leaf(
        e2_level,
        name="scan",
        script_name="phase2_e2_scan.py",
        command_label="gsc phase2 e2 scan",
        help_text="Run Phase-2 E2 scan",
    )
    _add_leaf(
        e2_level,
        name="merge",
        script_name="phase2_e2_merge_jsonl.py",
        command_label="gsc phase2 e2 merge",
        help_text="Merge Phase-2 E2 JSONL shards",
    )
    _add_leaf(
        e2_level,
        name="bundle",
        script_name="phase2_e2_bundle.py",
        command_label="gsc phase2 e2 bundle",
        help_text="Create Phase-2 E2 bundle",
    )
    _add_leaf(
        e2_level,
        name="verify",
        script_name="phase2_e2_verify_bundle.py",
        command_label="gsc phase2 e2 verify",
        help_text="Verify Phase-2 E2 bundle",
    )

    pt = level2.add_parser("pt", help="Perturbations handoff/export tooling")
    pt_level = pt.add_subparsers(dest="command", required=True)
    _add_leaf(
        pt_level,
        name="export",
        script_name="phase2_pt_boltzmann_export_pack.py",
        command_label="gsc phase2 pt export",
        help_text="Build deterministic Boltzmann export pack",
    )
    _add_leaf(
        pt_level,
        name="run",
        script_name="phase2_pt_boltzmann_run_harness.py",
        command_label="gsc phase2 pt run",
        help_text="Run external CLASS/CAMB harness",
    )
    _add_leaf(
        pt_level,
        name="results",
        script_name="phase2_pt_boltzmann_results_pack.py",
        command_label="gsc phase2 pt results",
        help_text="Package external Boltzmann run outputs",
    )
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    script_name = getattr(args, "script_name", None)
    if script_name is None:
        parser.print_help()
        return 2

    script_path = (SCRIPTS_ROOT / str(script_name)).resolve()
    if not script_path.is_file():
        print(f"ERROR: wrapped script not found: {script_path}", file=sys.stderr)
        return 1

    forwarded = list(getattr(args, "script_args", []))
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]

    cmd = [sys.executable, str(script_path), *forwarded]
    return int(subprocess.call(cmd))


if __name__ == "__main__":
    raise SystemExit(main())
