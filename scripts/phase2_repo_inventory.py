#!/usr/bin/env python3
"""Deterministic inventory for Phase-2 contract files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


SCHEMA = "phase2_repo_inventory_v1"

# Ordered canonical contract list for Phase-2 wiring.
_EXPECTED_FILES: List[Dict[str, Any]] = [
    # Phase-2 E2 spine (required)
    {"rel": "scripts/phase2_e2_scan.py", "required": True},
    {"rel": "scripts/phase2_e2_merge_jsonl.py", "required": True},
    {"rel": "scripts/phase2_e2_bundle.py", "required": True},
    {"rel": "scripts/phase2_e2_verify_bundle.py", "required": True},
    {"rel": "scripts/phase2_e2_jobgen.py", "required": True},
    {"rel": "scripts/phase2_e2_make_reviewer_pack.py", "required": True},
    {"rel": "scripts/phase2_pt_boltzmann_export_pack.py", "required": True},
    {"rel": "scripts/phase2_pt_boltzmann_run_harness.py", "required": True},
    {"rel": "scripts/phase2_pt_boltzmann_results_pack.py", "required": True},
    {"rel": "scripts/phase2_consistency_check.py", "required": True},
    {"rel": "scripts/preflight_share_check.py", "required": True},
    {"rel": "scripts/phase2_portable_content_lint.py", "required": True},
    {"rel": "scripts/make_repo_snapshot.py", "required": True},
    {"rel": "scripts/phase2_schema_validate.py", "required": True},
    {"rel": "scripts/phase2_lineage_dag.py", "required": True},
    {"rel": "scripts/gsc_cli.py", "required": True},
    {"rel": "gsc/cli.py", "required": True},
    {"rel": "scripts/docs_claim_ledger_lint.py", "required": True},
    {"rel": "schemas/phase2_scan_row_v1.schema.json", "required": True},
    {"rel": "schemas/phase2_candidate_record_v1.schema.json", "required": True},
    {"rel": "schemas/phase2_bundle_manifest_v1.schema.json", "required": True},
    {"rel": "schemas/phase2_reviewer_pack_plan_v1.schema.json", "required": True},
    {"rel": "schemas/phase2_lineage_dag_v1.schema.json", "required": True},
    {"rel": "schemas/phase2_consistency_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase2_pt_boltzmann_run_metadata_v1.schema.json", "required": True},
    {"rel": "schemas/phase2_pt_boltzmann_results_pack_v1.schema.json", "required": True},
    {"rel": "schemas/phase2_cmb_rs_zstar_reference_audit_v1.schema.json", "required": True},
    {"rel": "schemas/gsc_repo_snapshot_manifest_v1.schema.json", "required": True},
    # Phase-3 SigmaTensor spine (required)
    {"rel": "docs/phase3_sigma_tensor_model_v1.md", "required": True},
    {"rel": "scripts/phase3_st_sigmatensor_background_report.py", "required": True},
    {"rel": "scripts/phase3_st_sigmatensor_consistency_report.py", "required": True},
    {"rel": "scripts/phase3_pt_sigmatensor_eft_export_pack.py", "required": True},
    {"rel": "scripts/phase3_pt_sigmatensor_class_export_pack.py", "required": True},
    {"rel": "scripts/phase3_pt_sigmatensor_class_mapping_report.py", "required": True},
    {"rel": "scripts/phase3_sf_sigmatensor_fsigma8_report.py", "required": True},
    {"rel": "scripts/phase3_joint_sigmatensor_lowz_report.py", "required": True},
    {"rel": "scripts/phase3_scan_sigmatensor_lowz_joint.py", "required": True},
    {"rel": "scripts/phase3_lowz_jobgen.py", "required": True},
    {"rel": "scripts/phase3_analyze_sigmatensor_lowz_scan.py", "required": True},
    {"rel": "scripts/phase3_make_sigmatensor_candidate_dossier_pack.py", "required": True},
    {"rel": "scripts/phase3_dossier_quicklook_report.py", "required": True},
    {"rel": "scripts/phase3_pt_spectra_sanity_report.py", "required": True},
    {"rel": "scripts/phase4_red_team_check.py", "required": True},
    {"rel": "scripts/phase4_cosmofalsify_demo.py", "required": True},
    {"rel": "scripts/phase4_sigmatensor_drift_sign_diagnostic.py", "required": True},
    {"rel": "scripts/phase4_sigmatensor_optimal_control_gap_diagnostic.py", "required": True},
    {"rel": "scripts/phase4_epsilon_framework_readiness_audit.py", "required": True},
    {"rel": "scripts/phase4_epsilon_translator_mvp.py", "required": True},
    {"rel": "scripts/phase4_epsilon_sensitivity_matrix_toy.py", "required": True},
    {"rel": "scripts/phase4_pantheon_plus_epsilon_posterior.py", "required": True},
    {"rel": "scripts/phase4_m163_five_problems_report.py", "required": True},
    {"rel": "scripts/fetch_pantheon_plus_release.py", "required": True},
    {"rel": "scripts/fetch_desi_bao_products.py", "required": True},
    {"rel": "scripts/phase4_desi_bao_convert_gaussian_to_internal.py", "required": True},
    {"rel": "scripts/phase4_desi_bao_epsilon_or_rd_diagnostic.py", "required": True},
    {"rel": "scripts/phase4_triangle1_joint_sn_bao_epsilon_posterior.py", "required": True},
    {"rel": "scripts/phase4_triangle1_sn_bao_planck_thetastar.py", "required": True},
    {"rel": "scripts/phase4_make_paper2_artifacts.py", "required": True},
    {"rel": "scripts/phase4_build_paper2_assets.py", "required": True},
    {"rel": "bridges/phase4_qcd_gravity_bridge_v0.1/tools/make_qcd_gravity_bridge_artifacts.py", "required": True},
    {"rel": "bridges/phase4_qcd_gravity_bridge_v0.1/report/QCD_Gravity_Bridge_v0.1.md", "required": True},
    {"rel": "bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_numbers.json", "required": True},
    {"rel": "bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_kill_matrix.csv", "required": True},
    {"rel": "bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_scale_plot.png", "required": True},
    {"rel": "scripts/build_paper2.sh", "required": True},
    {"rel": "scripts/make_paper2_arxiv_bundle.py", "required": True},
    {"rel": "scripts/phase4_make_arxiv_bundle_paper2.py", "required": True},
    {"rel": "scripts/phase4_joss_preflight.py", "required": True},
    {"rel": "gsc/epsilon/translator.py", "required": True},
    {"rel": "gsc/epsilon/sensitivity.py", "required": True},
    {"rel": "gsc/theory/sigmatensor_v1.py", "required": True},
    {"rel": "gsc/pt/eft_alpha_v1.py", "required": True},
    {"rel": "schemas/phase3_sigmatensor_theory_spec_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_consistency_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_eft_export_pack_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_class_export_pack_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_candidate_record_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_fsigma8_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_lowz_joint_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_lowz_scan_plan_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_lowz_scan_row_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_lowz_scan_analysis_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_candidate_dossier_manifest_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_candidate_dossier_quicklook_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_spectra_sanity_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase3_sigmatensor_class_mapping_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_red_team_check_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_cosmofalsify_demo_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_sigmatensor_drift_sign_diagnostic_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_sigmatensor_optimal_control_gap_diagnostic_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_epsilon_framework_readiness_audit_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_epsilon_translator_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_epsilon_sensitivity_matrix_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_pantheon_plus_epsilon_posterior_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_m163_five_problems_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_pantheon_plus_epsilon_posterior_report_v2.schema.json", "required": True},
    {"rel": "schemas/phase4_pantheon_plus_fetch_manifest_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_desi_bao_fetch_manifest_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_desi_bao_triangle1_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_triangle1_joint_sn_bao_epsilon_posterior_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_triangle1_report_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_paper2_artifacts_manifest_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_paper2_assets_manifest_v1.schema.json", "required": True},
    {"rel": "schemas/phase4_joss_preflight_report_v1.schema.json", "required": True},
    {"rel": "data/bao/desi/README.md", "required": True},
    {"rel": "data/bao/desi/desi_dr1_bao_baseline.csv", "required": True},
    {"rel": "tests/fixtures/phase4_m154/pantheon_toy_manifest.json", "required": True},
    {"rel": "tests/fixtures/phase4_m157/desi_gaussian_mean_toy.txt", "required": True},
    {"rel": "tests/fixtures/phase4_m157/desi_gaussian_cov_toy.txt", "required": True},
    {"rel": "tests/test_phase4_m160_qcd_gravity_bridge_artifacts_deterministic.py", "required": True},
    {"rel": "tests/test_phase4_publish_branding_pack_present_and_nonempty.py", "required": True},
    {"rel": "tests/test_phase4_m163_five_problems_report_determinism_toy.py", "required": True},
    {"rel": "tests/test_phase4_m163_schema_validate_auto_toy.py", "required": True},
    # Structure / SF helpers (optional across branches)
    {"rel": "scripts/phase2_sf_structure_report.py", "required": False},
    {"rel": "scripts/phase2_sf_fsigma8_report.py", "required": False},
    # RG helpers (optional across branches)
    {"rel": "scripts/phase2_rg_flow_table_report.py", "required": False},
    {"rel": "scripts/phase2_rg_pade_fit_report.py", "required": False},
    # Canonical docs (required)
    {"rel": "docs/project_status_and_roadmap.md", "required": True},
    {"rel": "docs/GSC_Consolidated_Roadmap_v2.8.md", "required": True},
    {"rel": "docs/GSC_Consolidated_Roadmap_v2.8.1_patch.md", "required": True},
    {"rel": "docs/GSC_Consolidated_Roadmap_v2.5.md", "required": False},
    {"rel": "docs/REVIEW_START_HERE.md", "required": True},
    {"rel": "docs/VERIFICATION_MATRIX.md", "required": True},
    {"rel": "docs/FRAMES_UNITS_INVARIANTS.md", "required": True},
    {"rel": "docs/DATA_LICENSES_AND_SOURCES.md", "required": True},
    {"rel": "docs/DATASET_ONBOARDING_POLICY.md", "required": True},
    {"rel": "docs/AI_USAGE_AND_VALIDATION_POLICY.md", "required": True},
    {"rel": "docs/DM_DECISION_MEMO.md", "required": True},
    {"rel": "docs/EPSILON_FRAMEWORK_READINESS.md", "required": True},
    {"rel": "docs/LEGACY_VERSIONED_ARTIFACTS.md", "required": True},
    {"rel": "docs/PRIOR_ART_AND_NOVELTY_MAP.md", "required": True},
    {"rel": "docs/PRIOR_ART_MAP.md", "required": True},
    {"rel": "docs/PAPER2_SUBMISSION.md", "required": True},
    {"rel": "docs/PAPER2_SUBMISSION_GUIDE.md", "required": True},
    {"rel": "docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md", "required": True},
    {"rel": "docs/ARXIV_METADATA.md", "required": True},
    {"rel": "docs/ARXIV_UPLOAD_CHECKLIST.md", "required": True},
    {"rel": "docs/ARXIV_SUBMISSION_CHECKLIST.md", "required": True},
    {"rel": "docs/JOSS_AUTHORS.md", "required": True},
    {"rel": "docs/JOSS_SUBMISSION_GUIDE.md", "required": True},
    {"rel": "docs/JOSS_SUBMISSION.md", "required": True},
    {"rel": "docs/JOSS_SUBMISSION_CHECKLIST.md", "required": True},
    {"rel": "docs/AFFILIATION_AND_BRANDING.md", "required": True},
    {"rel": "docs/research_notes/PHASE4_M163_FIVE_PROBLEMS.md", "required": True},
    {"rel": "docs/early_time_e2_status.md", "required": True},
    {"rel": "docs/structure_formation_status.md", "required": True},
    {"rel": "docs/sigma_field_origin_status.md", "required": True},
    {"rel": "docs/perturbations_and_dm_scope.md", "required": True},
    {"rel": "docs/provenance_and_schemas.md", "required": True},
    {"rel": "docs/sharing_and_snapshots.md", "required": True},
    {"rel": "docs/claim_ledger.json", "required": True},
    {"rel": "docs/DATA_SOURCES.md", "required": True},
    {"rel": "docs/SBOM.md", "required": True},
    {"rel": "docs/phase3_scanning_lowz_joint.md", "required": True},
    {"rel": "papers/paper2_measurement_model_epsilon/main.tex", "required": True},
    {"rel": "papers/paper2_measurement_model_epsilon/paper2.tex", "required": True},
    {"rel": "papers/paper2_measurement_model_epsilon/refs.bib", "required": True},
    {"rel": "papers/paper2_measurement_model_epsilon/paper2.bib", "required": True},
    {"rel": "papers/paper2_measurement_model_epsilon/numbers.tex", "required": True},
    {"rel": "papers/paper2_measurement_model_epsilon/README.md", "required": True},
    {"rel": "outreach/labs_site_copy/labs_index.md", "required": True},
    {"rel": "outreach/labs_site_copy/labs_gsc.md", "required": True},
    {"rel": "outreach/labs_site_copy/labs_paper2.md", "required": True},
    {"rel": "outreach/labs_site_copy/labs_cosmofalsify.md", "required": True},
    {"rel": "outreach/labs_site_copy/labs_transparency.md", "required": True},
    {"rel": "outreach/labs_site_copy/labs_press_kit.md", "required": True},
    {"rel": "outreach/templates/email_researcher_feedback.md", "required": True},
    {"rel": "outreach/templates/email_oss_maintainer_feedback.md", "required": True},
    {"rel": "outreach/templates/email_journalist_pitch.md", "required": True},
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _repo_root_display(raw: str) -> str:
    text = str(raw).replace("\\", "/").rstrip("/")
    return text if text else "."


def _build_inventory(repo_root_dir: Path, repo_root_display: str) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    missing_required: List[str] = []

    for row in _EXPECTED_FILES:
        rel = str(row["rel"])
        required = bool(row["required"])
        abs_path = repo_root_dir / rel
        out_rel = f"{repo_root_display}/{rel}" if repo_root_display != "." else rel

        entry: Dict[str, Any] = {
            "path": out_rel,
            "required": required,
            "exists": abs_path.is_file(),
            "bytes": None,
            "sha256": None,
        }
        if entry["exists"]:
            entry["bytes"] = int(abs_path.stat().st_size)
            entry["sha256"] = _sha256_file(abs_path)
        elif required:
            missing_required.append(out_rel)
        entries.append(entry)

    return {
        "schema": SCHEMA,
        "repo_root": repo_root_display,
        "entries": entries,
        "counts": {
            "total": len(entries),
            "present": sum(1 for e in entries if bool(e.get("exists"))),
            "missing": sum(1 for e in entries if not bool(e.get("exists"))),
            "required_missing": len(missing_required),
        },
        "missing_required": missing_required,
    }


def _render_text(payload: Mapping[str, Any], *, require_present: bool) -> str:
    lines: List[str] = []
    lines.append(f"schema={payload.get('schema')}")
    lines.append(f"repo_root={payload.get('repo_root')}")
    counts = payload.get("counts", {}) if isinstance(payload.get("counts"), Mapping) else {}
    lines.append(
        "counts="
        f"total={counts.get('total')} present={counts.get('present')} "
        f"missing={counts.get('missing')} required_missing={counts.get('required_missing')}"
    )
    lines.append(f"require_present={bool(require_present)}")
    lines.append("entries:")

    for row in payload.get("entries", []):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "  - "
            f"path={row.get('path')} "
            f"required={bool(row.get('required'))} "
            f"exists={bool(row.get('exists'))} "
            f"bytes={row.get('bytes')} "
            f"sha256={row.get('sha256')}"
        )

    missing_required = payload.get("missing_required", [])
    if isinstance(missing_required, list) and missing_required:
        lines.append("missing_required:")
        for rel in missing_required:
            lines.append(f"  - {rel}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic Phase-2 contract-file inventory.")
    ap.add_argument("--repo-root", default="v11.0.0", help="Phase-2 root directory (default: v11.0.0)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--require-present", action="store_true", help="Exit with code 2 if required files are missing")
    ap.add_argument("--write", default=None, help="Optional path to write output deterministically")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root_display = _repo_root_display(str(args.repo_root))
    repo_root_dir = Path(str(args.repo_root)).expanduser().resolve()

    if not repo_root_dir.exists() or not repo_root_dir.is_dir():
        print(f"ERROR: --repo-root does not exist or is not a directory: {repo_root_dir}")
        return 1

    payload = _build_inventory(repo_root_dir, repo_root_display)

    if str(args.format) == "json":
        rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = _render_text(payload, require_present=bool(args.require_present))

    if args.write:
        out_path = Path(str(args.write)).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")

    print(rendered, end="")

    missing_required = payload.get("missing_required", [])
    if bool(args.require_present) and isinstance(missing_required, list) and missing_required:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
