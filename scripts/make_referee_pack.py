#!/usr/bin/env python3
"""
Build a "referee pack" zip for v11.0.0 late-time (docs + tooling + nested submission bundle).

Design goals:
- Docs/tooling only: do not alter physics, fits, or canonical outputs.
- Offline-safe: stdlib-only; does not require LaTeX.
- Exclude popular/TOE notes (docs/popular/**).
- Portability: zip entries are repo-relative; no machine-local absolute paths.

The referee pack is intentionally separate from the arXiv-style submission bundle:
- submission bundle = TeX + paper_assets only (LaTeX-compileable standalone)
- referee pack = submission bundle (nested) + key docs + minimal helper scripts
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import shutil
import sys
import textwrap
import zipfile
from pathlib import Path, PurePosixPath
from typing import Dict, List


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _derive_tag_from_name(name: str) -> str:
    for prefix in ("paper_assets_", "submission_bundle_", "referee_pack_"):
        if name.startswith(prefix) and name.endswith(".zip"):
            return name[len(prefix) : -len(".zip")]
    return "unknown"


def _zip_dir(root_dir: Path, out_zip: Path) -> None:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        fixed_dt = (1980, 1, 1, 0, 0, 0)

        for p in sorted(root_dir.rglob("*")):
            if p.is_dir():
                continue
            arc = p.relative_to(root_dir).as_posix()
            if arc.startswith(("/", "\\")):
                raise ValueError(f"refusing to write absolute arcname: {arc!r}")
            if ".." in PurePosixPath(arc).parts:
                raise ValueError(f"refusing to write path-traversal arcname: {arc!r}")

            data = p.read_bytes()
            info = zipfile.ZipInfo(filename=arc, date_time=fixed_dt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # UNIX
            info.external_attr = (0o100644 & 0xFFFF) << 16
            zf.writestr(info, data)


def _write_readme(
    path: Path,
    *,
    late_time_tag: str,
    assets_zip_name: str | None,
    assets_sha256: str | None,
    submission_zip_name: str,
    submission_sha256: str,
    diagnostic_assets: List[Dict[str, str | None]] | None = None,
) -> None:
    assets_block = ""
    if assets_zip_name and assets_sha256:
        assets_block = textwrap.dedent(
            f"""\

            ## Canonical assets provenance

            - Canonical paper-assets zip: `{assets_zip_name}`
            - SHA256 (assets zip): `{assets_sha256}`
            """
        )

    text = textwrap.dedent(
        f"""\
        # GSC referee pack (v11.0.0 late-time)

        This zip is a reviewer/referee companion pack (docs + minimal tooling).
        It is **not** the arXiv submission bundle itself, but it **includes** the submission bundle as a nested zip.

        ## Canonical late-time release

        - Tag/Release: `{late_time_tag}`
        {assets_block.rstrip()}

        ## Included

        - `paper/{submission_zip_name}` (nested submission bundle; standalone TeX + paper_assets)
        - `docs/` (reviewer FAQ, risk register, early-time bridge notes, reproducibility, measurement model)
        - `docs/diagnostics_index.md` (single index of diagnostic tags/assets/checksums/entrypoints)
        - `docs/early_time_e2_synthesis.md` (single referee verdict + decision tree + key evidence figure pointer)
        - `docs/early_time_e2_executive_summary.md` (E2 findings in 1-2 pages)
        - `docs/early_time_e2_drift_constrained_bound.md` (WS14 Pareto bound note)
        - `docs/early_time_e2_drift_bound_analytic.md` (analytic bound appendix)
        - `docs/early_time_e2_closure_to_physical_knobs.md` (WS15 effective physical-knob scale note)
        - `docs/sn_two_pass_sensitivity.md` (SN two-pass robustness diagnostic note)
        - `docs/paper_sanity_checklist.md` (release-discipline checklist)
        - `referee_pack_figures/closure_requirements.png` (WS13 closure-requirements figure, static copy)
        - `referee_pack_figures/e2_drift_constrained_bound.png` (WS14 drift-constrained bound figure)
        - `referee_pack_figures/e2_closure_to_physical_knobs.png` (WS15 closure->knobs figure)
        - `data/cmb/README.md` (compressed CMB prior provenance/contract notes)
        - `scripts/` (minimal offline verifiers/helpers)

        ## Excluded (by design)

        - `docs/popular/**` (TOE / popular / speculative notes are intentionally excluded)

        ## Submission bundle (nested)

        - `{submission_zip_name}`
        - SHA256 (submission bundle): `{submission_sha256}`
        """
    )

    # Add a compact "how to reproduce diagnostics" block. The intent is to keep
    # early-time and other roadmap tooling clearly separate from submission scope,
    # while still making it easy for reviewers to find/run it.
    text += "\n" + textwrap.dedent(
        """\
        ## Diagnostic modules (non-submission)

        This pack includes diagnostic notes under `docs/` (out of submission scope), including:

        - `docs/early_time_e2_synthesis.md` (single-page E2 referee verdict / decision tree)
        - `docs/early_time_e2_executive_summary.md` (short E2 findings summary)
        - `docs/early_time_e2_drift_constrained_bound.md` (WS14 Pareto-bound diagnostic note)
        - `docs/early_time_e2_drift_bound_analytic.md` (analytic sanity bound note)
        - `docs/early_time_e2_closure_to_physical_knobs.md` (WS15 closure->physical-knobs note)
        - `docs/early_time_e2_closure_requirements.md` (E2 closure requirements / no-go map)
        - `docs/sn_two_pass_sensitivity.md` (SN two-pass robustness diagnostic)
        - `docs/paper_sanity_checklist.md` (PDF narrative/scope discipline checklist)
        - `docs/diagnostics_index.md` (diagnostic modules index; tags/assets/SHA/reproduce)
        - `docs/early_time_drift_cmb_correlation.md` (E2.5 drift ↔ CMB closure correlation)
        - `docs/gw_standard_sirens.md` (E3 GW standard sirens)
        - `docs/early_time_e2_plan.md` (E2 roadmap/design notes)
        - `docs/redshift_drift_beyond_flrw.md` (redshift drift systematics note)

        Reproduce commands (run from the repo root; optional, diagnostic-only):

        ```bash
        bash v11.0.0/scripts/reproduce_v10_1_e2_drift_cmb_correlation.sh --sync-paper-assets
        bash v11.0.0/scripts/reproduce_v10_1_e2_closure_requirements.sh --sync-paper-assets
        bash v11.0.0/scripts/reproduce_v10_1_e2_drift_constrained_closure_bound.sh --sync-paper-assets
        bash v11.0.0/scripts/reproduce_v10_1_e2_drift_bound_analytic.sh --sync-paper-assets
        bash v11.0.0/scripts/reproduce_v10_1_e2_closure_to_physical_knobs.sh --sync-paper-assets
        bash v11.0.0/scripts/reproduce_v10_1_gw_standard_sirens_diagnostic.sh --sync-paper-assets
        ```

        Packaged diagnostic artifacts (separate pre-releases; not nested here):
        """
    )

    for a in diagnostic_assets or []:
        tag = a.get("tag") or "<unknown>"
        name = a.get("asset_name") or "<unknown>"
        sha = a.get("sha256") or "<not available locally>"
        text += f"- `{tag}`: `{name}` (SHA256: `{sha}`)\n"

    path.write_text(text, encoding="utf-8")


def _write_manifest(
    path: Path,
    *,
    late_time_tag: str,
    assets_zip_name: str | None,
    assets_sha256: str | None,
    submission_zip_name: str,
    submission_sha256: str,
    included_files: List[str],
) -> None:
    obj: Dict[str, object] = {
        "kind": "referee_pack",
        # Deterministic pack output: avoid embedding "build time" into manifest.
        # (Release notes can record human time separately.)
        "generated_utc": "1980-01-01T00:00:00Z",
        "late_time_tag": late_time_tag,
        "inputs": {
            "assets_zip_name": assets_zip_name,
            "assets_sha256": assets_sha256,
            "submission_zip_name": submission_zip_name,
            "submission_sha256": submission_sha256,
        },
        "included": {"files": included_files},
        "excludes": ["docs/popular/**", "__MACOSX/**", ".DS_Store", "._*"],
        "notes": [
            "Docs/tooling only; not part of the arXiv submission bundle itself.",
            "The nested submission bundle is intended to compile standalone (TeX + paper_assets).",
            "This pack intentionally excludes docs/popular (TOE/speculative notes).",
        ],
    }
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    script_dir = Path(__file__).resolve().parent

    ap = argparse.ArgumentParser(
        prog="make_referee_pack",
        description="Build a referee-pack zip (docs + tooling + nested submission bundle).",
    )
    ap.add_argument(
        "--assets-zip",
        type=Path,
        default=None,
        help="Optional: canonical paper-assets zip path (used only for provenance in README/manifest).",
    )
    ap.add_argument(
        "--submission-zip",
        type=Path,
        required=True,
        help="Path to a submission bundle zip (nested into paper/).",
    )
    ap.add_argument(
        "--out-zip",
        type=Path,
        default=None,
        help="Output zip path (default: ./referee_pack_<tag>.zip derived from assets/submission name).",
    )
    ap.add_argument(
        "--v101-dir",
        type=Path,
        default=None,
        help="Path to v11.0.0/ (default: inferred from script location; used for tests).",
    )
    args = ap.parse_args(argv)

    v101_dir = args.v101_dir.resolve() if args.v101_dir else script_dir.parent

    docs_dir = v101_dir / "docs"
    scripts_dir = v101_dir / "scripts"
    data_cmb_readme = v101_dir / "data" / "cmb" / "README.md"
    referee_fig_dir = v101_dir / "referee_pack_figures"

    required_docs = [
        "diagnostics_index.md",
        "early_time_e2_synthesis.md",
        "early_time_e2_executive_summary.md",
        "early_time_e2_drift_constrained_bound.md",
        "early_time_e2_drift_bound_analytic.md",
        "early_time_e2_closure_to_physical_knobs.md",
        "reviewer_faq.md",
        "risk_register.md",
        "precision_constraints_translator.md",
        "early_time_bridge.md",
        "early_time_e2_closure_requirements.md",
        "sn_two_pass_sensitivity.md",
        "paper_sanity_checklist.md",
        "early_time_drift_cmb_correlation.md",
        "gw_standard_sirens.md",
        "early_time_e2_plan.md",
        "redshift_drift_beyond_flrw.md",
        "reproducibility.md",
        "measurement_model.md",
    ]
    required_scripts = [
        "verify_release_bundle.py",
        "make_submission_bundle.py",
        "cmb_distance_budget_diagnostic.py",
        "verify_submission_bundle.py",
        "e2_drift_bound_analytic.py",
    ]
    required_referee_figures = [
        "closure_requirements.png",
        "e2_drift_constrained_bound.png",
        "e2_closure_to_physical_knobs.png",
    ]

    submission_zip = args.submission_zip.expanduser().resolve()
    if not submission_zip.is_file():
        print(f"ERROR: submission zip not found: {submission_zip}", file=sys.stderr)
        return 2

    assets_zip_name: str | None = None
    assets_sha: str | None = None
    late_time_tag = _derive_tag_from_name(submission_zip.name)
    if args.assets_zip is not None:
        assets_zip = args.assets_zip.expanduser().resolve()
        if not assets_zip.is_file():
            print(f"ERROR: assets zip not found: {assets_zip}", file=sys.stderr)
            return 2
        assets_zip_name = assets_zip.name
        assets_sha = _sha256_file(assets_zip)
        late_time_tag = _derive_tag_from_name(assets_zip.name)

    out_zip = args.out_zip.expanduser().resolve() if args.out_zip else (Path.cwd() / f"referee_pack_{late_time_tag}.zip").resolve()

    # Stage in a temp dir, then produce a deterministic zip.
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        stage = td_path / "referee_pack"
        (stage / "docs").mkdir(parents=True, exist_ok=True)
        (stage / "scripts").mkdir(parents=True, exist_ok=True)
        (stage / "data" / "cmb").mkdir(parents=True, exist_ok=True)
        (stage / "paper").mkdir(parents=True, exist_ok=True)
        (stage / "referee_pack_figures").mkdir(parents=True, exist_ok=True)

        # Docs.
        for name in required_docs:
            src = docs_dir / name
            if not src.is_file():
                print(f"ERROR: missing required doc: {src}", file=sys.stderr)
                return 2
            shutil.copyfile(src, stage / "docs" / name)

        # Data.
        if not data_cmb_readme.is_file():
            print(f"ERROR: missing required CMB README: {data_cmb_readme}", file=sys.stderr)
            return 2
        shutil.copyfile(data_cmb_readme, stage / "data" / "cmb" / "README.md")

        # Minimal helper scripts.
        for name in required_scripts:
            src = scripts_dir / name
            if not src.is_file():
                print(f"ERROR: missing required script: {src}", file=sys.stderr)
                return 2
            shutil.copyfile(src, stage / "scripts" / name)

        # Static figure snapshots for referee-facing docs.
        for name in required_referee_figures:
            src = referee_fig_dir / name
            if not src.is_file():
                print(f"ERROR: missing required referee figure: {src}", file=sys.stderr)
                return 2
            shutil.copyfile(src, stage / "referee_pack_figures" / name)

        # Nested submission bundle.
        submission_name = submission_zip.name
        submission_sha = _sha256_file(submission_zip)
        shutil.copyfile(submission_zip, stage / "paper" / submission_name)

        # README + manifest.
        readme = stage / "REFEREE_PACK_README.md"
        diagnostic_assets = []
        for tag, fname in [
            ("v10.1.1-bridge-e2-drift-cmb-correlation-r2", "paper_assets_cmb_e2_drift_cmb_correlation_r2.zip"),
            ("v10.1.1-bridge-e2-closure-requirements-diagnostic-r0", "paper_assets_cmb_e2_closure_requirements_r0.zip"),
            ("v10.1.1-bridge-e2-drift-constrained-closure-bound-r0", "paper_assets_cmb_e2_drift_constrained_closure_bound_r0.zip"),
            ("v10.1.1-bridge-e2-closure-to-physical-knobs-r0", "paper_assets_cmb_e2_closure_to_physical_knobs_r0.zip"),
            ("v10.1.1-sn-two-pass-sensitivity-diagnostic-r0", "paper_assets_sn_two_pass_sensitivity_diagnostic_r0.zip"),
            ("v10.1.1-gw-standard-sirens-diagnostic-r2", "paper_assets_gw_standard_sirens_diagnostic_r2.zip"),
        ]:
            p = (v101_dir / fname).resolve()
            diagnostic_assets.append(
                {
                    "tag": tag,
                    "asset_name": fname,
                    "sha256": _sha256_file(p) if p.is_file() else None,
                }
            )
        _write_readme(
            readme,
            late_time_tag=late_time_tag,
            assets_zip_name=assets_zip_name,
            assets_sha256=assets_sha,
            submission_zip_name=submission_name,
            submission_sha256=submission_sha,
            diagnostic_assets=diagnostic_assets,
        )

        included_files = [p.relative_to(stage).as_posix() for p in sorted(stage.rglob("*")) if p.is_file()]
        manifest = stage / "manifest.json"
        _write_manifest(
            manifest,
            late_time_tag=late_time_tag,
            assets_zip_name=assets_zip_name,
            assets_sha256=assets_sha,
            submission_zip_name=submission_name,
            submission_sha256=submission_sha,
            included_files=included_files,
        )

        _zip_dir(stage, out_zip)

    print("OK: referee pack built")
    print(f"  zip: {out_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
