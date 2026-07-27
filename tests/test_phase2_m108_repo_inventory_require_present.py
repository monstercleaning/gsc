import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
# v12.6: this copy previously audited the sibling v11.0.0 tree (impossible in
# the public root layout); it now audits its own package. Required paths are
# package-relative, follow the archive/legacy_docs/ relocations, and the
# retired paper2/outreach entries were removed (see CHANGELOG v12.6).
SCRIPT = ROOT / "scripts" / "phase2_repo_inventory.py"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_SPINE = (
    "scripts/phase2_e2_scan.py",
    "scripts/phase2_e2_merge_jsonl.py",
    "scripts/phase2_e2_bundle.py",
    "scripts/phase2_e2_verify_bundle.py",
    "scripts/phase2_e2_jobgen.py",
    "scripts/phase2_e2_make_reviewer_pack.py",
    "scripts/phase2_pt_boltzmann_export_pack.py",
    "scripts/phase2_pt_boltzmann_results_pack.py",
)

REQUIRED_M116_EXPANSION = (
    "gsc/cli.py",
    "scripts/phase2_portable_content_lint.py",
    "schemas/phase2_scan_row_v1.schema.json",
    "schemas/phase2_candidate_record_v1.schema.json",
    "schemas/phase2_bundle_manifest_v1.schema.json",
    "schemas/phase2_reviewer_pack_plan_v1.schema.json",
    "schemas/phase2_lineage_dag_v1.schema.json",
    "schemas/phase2_consistency_report_v1.schema.json",
    "schemas/phase2_pt_boltzmann_run_metadata_v1.schema.json",
    "schemas/phase2_pt_boltzmann_results_pack_v1.schema.json",
    "schemas/phase2_cmb_rs_zstar_reference_audit_v1.schema.json",
    "schemas/gsc_repo_snapshot_manifest_v1.schema.json",
)

REQUIRED_M124_EXPANSION = (
    "archive/legacy_docs/phase_specific_status/phase3_sigma_tensor_model_v1.md",
    "scripts/phase3_st_sigmatensor_background_report.py",
    "scripts/phase3_st_sigmatensor_consistency_report.py",
    "scripts/phase3_pt_sigmatensor_eft_export_pack.py",
    "gsc/theory/sigmatensor_v1.py",
    "gsc/pt/eft_alpha_v1.py",
    "schemas/phase3_sigmatensor_theory_spec_v1.schema.json",
    "schemas/phase3_sigmatensor_consistency_report_v1.schema.json",
    "schemas/phase3_sigmatensor_eft_export_pack_v1.schema.json",
)

REQUIRED_M125_EXPANSION = (
    "scripts/phase3_pt_sigmatensor_class_export_pack.py",
    "schemas/phase3_sigmatensor_class_export_pack_v1.schema.json",
    "schemas/phase3_sigmatensor_candidate_record_v1.schema.json",
)

REQUIRED_M126_EXPANSION = (
    "scripts/phase3_pt_spectra_sanity_report.py",
    "schemas/phase3_spectra_sanity_report_v1.schema.json",
)

REQUIRED_M127_EXPANSION = (
    "scripts/phase3_sf_sigmatensor_fsigma8_report.py",
    "schemas/phase3_sigmatensor_fsigma8_report_v1.schema.json",
)

REQUIRED_M128_EXPANSION = (
    "scripts/phase3_joint_sigmatensor_lowz_report.py",
    "schemas/phase3_sigmatensor_lowz_joint_report_v1.schema.json",
)

REQUIRED_M130_EXPANSION = (
    "scripts/phase3_scan_sigmatensor_lowz_joint.py",
    "schemas/phase3_sigmatensor_lowz_scan_plan_v1.schema.json",
    "schemas/phase3_sigmatensor_lowz_scan_row_v1.schema.json",
    "archive/legacy_docs/phase_specific_status/phase3_scanning_lowz_joint.md",
)

REQUIRED_M131_EXPANSION = (
    "scripts/phase3_analyze_sigmatensor_lowz_scan.py",
    "schemas/phase3_sigmatensor_lowz_scan_analysis_v1.schema.json",
)

REQUIRED_M137_EXPANSION = (
    "scripts/phase3_lowz_jobgen.py",
)

REQUIRED_M132_EXPANSION = (
    "scripts/phase3_make_sigmatensor_candidate_dossier_pack.py",
    "schemas/phase3_sigmatensor_candidate_dossier_manifest_v1.schema.json",
)

REQUIRED_M135_EXPANSION = (
    "scripts/phase3_pt_sigmatensor_class_mapping_report.py",
    "schemas/phase3_sigmatensor_class_mapping_report_v1.schema.json",
)

REQUIRED_M136_EXPANSION = (
    "scripts/phase3_dossier_quicklook_report.py",
    "schemas/phase3_sigmatensor_candidate_dossier_quicklook_v1.schema.json",
)

REQUIRED_M139_EXPANSION = (
    "archive/legacy_docs/REVIEW_START_HERE.md",
    "docs/VERIFICATION_MATRIX.md",
    "docs/FRAMES_UNITS_INVARIANTS.md",
    "docs/DATA_LICENSES_AND_SOURCES.md",
    "docs/DATASET_ONBOARDING_POLICY.md",
    "archive/legacy_docs/DM_DECISION_MEMO.md",
    "archive/legacy_docs/GSC_Consolidated_Roadmap_v2.8.md",
    "archive/legacy_docs/GSC_Consolidated_Roadmap_v2.8.1_patch.md",
)

REQUIRED_M141_EXPANSION = (
    "scripts/phase4_red_team_check.py",
    "schemas/phase4_red_team_check_report_v1.schema.json",
    "archive/legacy_docs/PRIOR_ART_AND_NOVELTY_MAP.md",
)

REQUIRED_M142_EXPANSION = (
    "scripts/phase4_cosmofalsify_demo.py",
    "schemas/phase4_cosmofalsify_demo_report_v1.schema.json",
    "archive/legacy_docs/PRIOR_ART_MAP.md",
)

REQUIRED_M143_EXPANSION = (
    "docs/AI_USAGE_AND_VALIDATION_POLICY.md",
)

REQUIRED_M145_EXPANSION = (
    "scripts/phase4_sigmatensor_drift_sign_diagnostic.py",
    "schemas/phase4_sigmatensor_drift_sign_diagnostic_report_v1.schema.json",
)

REQUIRED_M146_EXPANSION = (
    "scripts/phase4_sigmatensor_optimal_control_gap_diagnostic.py",
    "schemas/phase4_sigmatensor_optimal_control_gap_diagnostic_report_v1.schema.json",
)

REQUIRED_M147_EXPANSION = (
    "scripts/phase4_epsilon_framework_readiness_audit.py",
    "schemas/phase4_epsilon_framework_readiness_audit_report_v1.schema.json",
    "archive/legacy_docs/EPSILON_FRAMEWORK_READINESS.md",
)

REQUIRED_M148_EXPANSION = (
    "scripts/phase4_epsilon_translator_mvp.py",
    "gsc/epsilon/translator.py",
    "schemas/phase4_epsilon_translator_report_v1.schema.json",
)

REQUIRED_M149_EXPANSION = (
    "scripts/phase4_epsilon_sensitivity_matrix_toy.py",
    "gsc/epsilon/sensitivity.py",
    "schemas/phase4_epsilon_sensitivity_matrix_report_v1.schema.json",
)

REQUIRED_M150_EXPANSION = (
    "scripts/phase4_pantheon_plus_epsilon_posterior.py",
    "schemas/phase4_pantheon_plus_epsilon_posterior_report_v1.schema.json",
)

REQUIRED_M154_EXPANSION = (
    "scripts/fetch_pantheon_plus_release.py",
    "schemas/phase4_pantheon_plus_fetch_manifest_v1.schema.json",
)

REQUIRED_M155_EXPANSION = (
    "tests/fixtures/phase4_m154/pantheon_toy_manifest.json",
    "schemas/phase4_pantheon_plus_epsilon_posterior_report_v2.schema.json",
)

REQUIRED_M156_EXPANSION = (
    "scripts/fetch_desi_bao_products.py",
    "scripts/phase4_desi_bao_epsilon_or_rd_diagnostic.py",
    "schemas/phase4_desi_bao_fetch_manifest_v1.schema.json",
    "schemas/phase4_desi_bao_triangle1_report_v1.schema.json",
    "data/bao/desi/README.md",
    "data/bao/desi/desi_dr1_bao_baseline.csv",
)

REQUIRED_M152_EXPANSION = (
    "archive/legacy_docs/LEGACY_VERSIONED_ARTIFACTS.md",
)

REQUIRED_M157_EXPANSION = (
    "scripts/phase4_triangle1_joint_sn_bao_epsilon_posterior.py",
    "schemas/phase4_triangle1_joint_sn_bao_epsilon_posterior_report_v1.schema.json",
    "scripts/phase4_desi_bao_convert_gaussian_to_internal.py",
    "scripts/phase4_triangle1_sn_bao_planck_thetastar.py",
    "schemas/phase4_triangle1_report_v1.schema.json",
    "tests/fixtures/phase4_m157/desi_gaussian_mean_toy.txt",
    "tests/fixtures/phase4_m157/desi_gaussian_cov_toy.txt",
)

REQUIRED_M158_EXPANSION = (
    "scripts/phase4_make_paper2_artifacts.py",
    "scripts/phase4_build_paper2_assets.py",
    "scripts/build_paper2.sh",
    "scripts/make_paper2_arxiv_bundle.py",
    "scripts/phase4_make_arxiv_bundle_paper2.py",
    "scripts/phase4_joss_preflight.py",
    "schemas/phase4_paper2_artifacts_manifest_v1.schema.json",
    "schemas/phase4_paper2_assets_manifest_v1.schema.json",
    "schemas/phase4_joss_preflight_report_v1.schema.json",
    "archive/legacy_docs/PAPER2_SUBMISSION.md",
    "archive/legacy_docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md",
    "archive/legacy_docs/ARXIV_SUBMISSION_CHECKLIST.md",
    "archive/legacy_docs/JOSS_SUBMISSION.md",
    "archive/legacy_docs/JOSS_SUBMISSION_CHECKLIST.md",
)

REQUIRED_M159_EXPANSION = (
    "archive/legacy_docs/PAPER2_SUBMISSION_GUIDE.md",
    "archive/legacy_docs/ARXIV_METADATA.md",
    "archive/legacy_docs/ARXIV_UPLOAD_CHECKLIST.md",
    "archive/legacy_docs/JOSS_AUTHORS.md",
    "archive/legacy_docs/JOSS_SUBMISSION_GUIDE.md",
)

REQUIRED_M160_EXPANSION = (
    "bridges/phase4_qcd_gravity_bridge_v0.1/tools/make_qcd_gravity_bridge_artifacts.py",
    "bridges/phase4_qcd_gravity_bridge_v0.1/report/QCD_Gravity_Bridge_v0.1.md",
    "bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_numbers.json",
    "bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_kill_matrix.csv",
    "bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_scale_plot.png",
    "tests/test_phase4_m160_qcd_gravity_bridge_artifacts_deterministic.py",
)

REQUIRED_M161_EXPANSION = (
    "archive/legacy_docs/AFFILIATION_AND_BRANDING.md",
    "tests/test_phase4_publish_branding_pack_present_and_nonempty.py",
)

REQUIRED_M163_EXPANSION = (
    "scripts/phase4_m163_five_problems_report.py",
    "schemas/phase4_m163_five_problems_report_v1.schema.json",
    "tests/test_phase4_m163_five_problems_report_determinism_toy.py",
    "tests/test_phase4_m163_schema_validate_auto_toy.py",
    "docs/research_notes/PHASE4_M163_FIVE_PROBLEMS.md",
)


class TestPhase2M108RepoInventoryRequirePresent(unittest.TestCase):
    def test_require_present_passes_and_has_sha256(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(ROOT),
                "--require-present",
                "--format",
                "json",
            ],
            text=True,
            capture_output=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)

        payload = json.loads(proc.stdout)
        entries = payload.get("entries", [])
        self.assertIsInstance(entries, list)
        by_path = {
            str(row.get("path")): row
            for row in entries
            if isinstance(row, dict) and "path" in row
        }

        for rel in (
            *REQUIRED_SPINE,
            *REQUIRED_M116_EXPANSION,
            *REQUIRED_M124_EXPANSION,
            *REQUIRED_M125_EXPANSION,
            *REQUIRED_M126_EXPANSION,
            *REQUIRED_M127_EXPANSION,
            *REQUIRED_M128_EXPANSION,
            *REQUIRED_M130_EXPANSION,
            *REQUIRED_M131_EXPANSION,
            *REQUIRED_M137_EXPANSION,
            *REQUIRED_M132_EXPANSION,
            *REQUIRED_M135_EXPANSION,
            *REQUIRED_M136_EXPANSION,
            *REQUIRED_M139_EXPANSION,
            *REQUIRED_M141_EXPANSION,
            *REQUIRED_M142_EXPANSION,
            *REQUIRED_M143_EXPANSION,
            *REQUIRED_M145_EXPANSION,
            *REQUIRED_M146_EXPANSION,
            *REQUIRED_M147_EXPANSION,
            *REQUIRED_M148_EXPANSION,
            *REQUIRED_M149_EXPANSION,
            *REQUIRED_M150_EXPANSION,
            *REQUIRED_M154_EXPANSION,
            *REQUIRED_M155_EXPANSION,
            *REQUIRED_M156_EXPANSION,
            *REQUIRED_M157_EXPANSION,
            *REQUIRED_M152_EXPANSION,
            *REQUIRED_M158_EXPANSION,
            *REQUIRED_M159_EXPANSION,
            *REQUIRED_M160_EXPANSION,
            *REQUIRED_M161_EXPANSION,
            *REQUIRED_M163_EXPANSION,
        ):
            self.assertIn(rel, by_path, msg=f"missing inventory row for {rel}")
            row = by_path[rel]
            self.assertTrue(bool(row.get("exists")), msg=f"expected exists=true for {rel}")
            sha = str(row.get("sha256"))
            self.assertRegex(sha, HEX64_RE, msg=f"bad sha256 for {rel}: {sha}")


if __name__ == "__main__":
    unittest.main()
