import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_repo_inventory.py"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_SPINE = (
    "v11.0.0/scripts/phase2_e2_scan.py",
    "v11.0.0/scripts/phase2_e2_merge_jsonl.py",
    "v11.0.0/scripts/phase2_e2_bundle.py",
    "v11.0.0/scripts/phase2_e2_verify_bundle.py",
    "v11.0.0/scripts/phase2_e2_jobgen.py",
    "v11.0.0/scripts/phase2_e2_make_reviewer_pack.py",
    "v11.0.0/scripts/phase2_pt_boltzmann_export_pack.py",
    "v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py",
)

REQUIRED_M116_EXPANSION = (
    "v11.0.0/gsc/cli.py",
    "v11.0.0/scripts/phase2_portable_content_lint.py",
    "v11.0.0/schemas/phase2_scan_row_v1.schema.json",
    "v11.0.0/schemas/phase2_candidate_record_v1.schema.json",
    "v11.0.0/schemas/phase2_bundle_manifest_v1.schema.json",
    "v11.0.0/schemas/phase2_reviewer_pack_plan_v1.schema.json",
    "v11.0.0/schemas/phase2_lineage_dag_v1.schema.json",
    "v11.0.0/schemas/phase2_consistency_report_v1.schema.json",
    "v11.0.0/schemas/phase2_pt_boltzmann_run_metadata_v1.schema.json",
    "v11.0.0/schemas/phase2_pt_boltzmann_results_pack_v1.schema.json",
    "v11.0.0/schemas/phase2_cmb_rs_zstar_reference_audit_v1.schema.json",
    "v11.0.0/schemas/gsc_repo_snapshot_manifest_v1.schema.json",
)

REQUIRED_M124_EXPANSION = (
    "v11.0.0/docs/phase3_sigma_tensor_model_v1.md",
    "v11.0.0/scripts/phase3_st_sigmatensor_background_report.py",
    "v11.0.0/scripts/phase3_st_sigmatensor_consistency_report.py",
    "v11.0.0/scripts/phase3_pt_sigmatensor_eft_export_pack.py",
    "v11.0.0/gsc/theory/sigmatensor_v1.py",
    "v11.0.0/gsc/pt/eft_alpha_v1.py",
    "v11.0.0/schemas/phase3_sigmatensor_theory_spec_v1.schema.json",
    "v11.0.0/schemas/phase3_sigmatensor_consistency_report_v1.schema.json",
    "v11.0.0/schemas/phase3_sigmatensor_eft_export_pack_v1.schema.json",
)

REQUIRED_M125_EXPANSION = (
    "v11.0.0/scripts/phase3_pt_sigmatensor_class_export_pack.py",
    "v11.0.0/schemas/phase3_sigmatensor_class_export_pack_v1.schema.json",
    "v11.0.0/schemas/phase3_sigmatensor_candidate_record_v1.schema.json",
)

REQUIRED_M126_EXPANSION = (
    "v11.0.0/scripts/phase3_pt_spectra_sanity_report.py",
    "v11.0.0/schemas/phase3_spectra_sanity_report_v1.schema.json",
)

REQUIRED_M127_EXPANSION = (
    "v11.0.0/scripts/phase3_sf_sigmatensor_fsigma8_report.py",
    "v11.0.0/schemas/phase3_sigmatensor_fsigma8_report_v1.schema.json",
)

REQUIRED_M128_EXPANSION = (
    "v11.0.0/scripts/phase3_joint_sigmatensor_lowz_report.py",
    "v11.0.0/schemas/phase3_sigmatensor_lowz_joint_report_v1.schema.json",
)

REQUIRED_M130_EXPANSION = (
    "v11.0.0/scripts/phase3_scan_sigmatensor_lowz_joint.py",
    "v11.0.0/schemas/phase3_sigmatensor_lowz_scan_plan_v1.schema.json",
    "v11.0.0/schemas/phase3_sigmatensor_lowz_scan_row_v1.schema.json",
    "v11.0.0/docs/phase3_scanning_lowz_joint.md",
)

REQUIRED_M131_EXPANSION = (
    "v11.0.0/scripts/phase3_analyze_sigmatensor_lowz_scan.py",
    "v11.0.0/schemas/phase3_sigmatensor_lowz_scan_analysis_v1.schema.json",
)

REQUIRED_M137_EXPANSION = (
    "v11.0.0/scripts/phase3_lowz_jobgen.py",
)

REQUIRED_M132_EXPANSION = (
    "v11.0.0/scripts/phase3_make_sigmatensor_candidate_dossier_pack.py",
    "v11.0.0/schemas/phase3_sigmatensor_candidate_dossier_manifest_v1.schema.json",
)

REQUIRED_M135_EXPANSION = (
    "v11.0.0/scripts/phase3_pt_sigmatensor_class_mapping_report.py",
    "v11.0.0/schemas/phase3_sigmatensor_class_mapping_report_v1.schema.json",
)

REQUIRED_M136_EXPANSION = (
    "v11.0.0/scripts/phase3_dossier_quicklook_report.py",
    "v11.0.0/schemas/phase3_sigmatensor_candidate_dossier_quicklook_v1.schema.json",
)

REQUIRED_M139_EXPANSION = (
    "v11.0.0/docs/REVIEW_START_HERE.md",
    "v11.0.0/docs/VERIFICATION_MATRIX.md",
    "v11.0.0/docs/FRAMES_UNITS_INVARIANTS.md",
    "v11.0.0/docs/DATA_LICENSES_AND_SOURCES.md",
    "v11.0.0/docs/DATASET_ONBOARDING_POLICY.md",
    "v11.0.0/docs/DM_DECISION_MEMO.md",
    "v11.0.0/docs/GSC_Consolidated_Roadmap_v2.8.md",
    "v11.0.0/docs/GSC_Consolidated_Roadmap_v2.8.1_patch.md",
)

REQUIRED_M141_EXPANSION = (
    "v11.0.0/scripts/phase4_red_team_check.py",
    "v11.0.0/schemas/phase4_red_team_check_report_v1.schema.json",
    "v11.0.0/docs/PRIOR_ART_AND_NOVELTY_MAP.md",
)

REQUIRED_M142_EXPANSION = (
    "v11.0.0/scripts/phase4_cosmofalsify_demo.py",
    "v11.0.0/schemas/phase4_cosmofalsify_demo_report_v1.schema.json",
    "v11.0.0/docs/PRIOR_ART_MAP.md",
)

REQUIRED_M143_EXPANSION = (
    "v11.0.0/docs/AI_USAGE_AND_VALIDATION_POLICY.md",
)

REQUIRED_M145_EXPANSION = (
    "v11.0.0/scripts/phase4_sigmatensor_drift_sign_diagnostic.py",
    "v11.0.0/schemas/phase4_sigmatensor_drift_sign_diagnostic_report_v1.schema.json",
)

REQUIRED_M146_EXPANSION = (
    "v11.0.0/scripts/phase4_sigmatensor_optimal_control_gap_diagnostic.py",
    "v11.0.0/schemas/phase4_sigmatensor_optimal_control_gap_diagnostic_report_v1.schema.json",
)

REQUIRED_M147_EXPANSION = (
    "v11.0.0/scripts/phase4_epsilon_framework_readiness_audit.py",
    "v11.0.0/schemas/phase4_epsilon_framework_readiness_audit_report_v1.schema.json",
    "v11.0.0/docs/EPSILON_FRAMEWORK_READINESS.md",
)

REQUIRED_M148_EXPANSION = (
    "v11.0.0/scripts/phase4_epsilon_translator_mvp.py",
    "v11.0.0/gsc/epsilon/translator.py",
    "v11.0.0/schemas/phase4_epsilon_translator_report_v1.schema.json",
)

REQUIRED_M149_EXPANSION = (
    "v11.0.0/scripts/phase4_epsilon_sensitivity_matrix_toy.py",
    "v11.0.0/gsc/epsilon/sensitivity.py",
    "v11.0.0/schemas/phase4_epsilon_sensitivity_matrix_report_v1.schema.json",
)

REQUIRED_M150_EXPANSION = (
    "v11.0.0/scripts/phase4_pantheon_plus_epsilon_posterior.py",
    "v11.0.0/schemas/phase4_pantheon_plus_epsilon_posterior_report_v1.schema.json",
)

REQUIRED_M154_EXPANSION = (
    "v11.0.0/scripts/fetch_pantheon_plus_release.py",
    "v11.0.0/schemas/phase4_pantheon_plus_fetch_manifest_v1.schema.json",
)

REQUIRED_M155_EXPANSION = (
    "v11.0.0/tests/fixtures/phase4_m154/pantheon_toy_manifest.json",
    "v11.0.0/schemas/phase4_pantheon_plus_epsilon_posterior_report_v2.schema.json",
)

REQUIRED_M156_EXPANSION = (
    "v11.0.0/scripts/fetch_desi_bao_products.py",
    "v11.0.0/scripts/phase4_desi_bao_epsilon_or_rd_diagnostic.py",
    "v11.0.0/schemas/phase4_desi_bao_fetch_manifest_v1.schema.json",
    "v11.0.0/schemas/phase4_desi_bao_triangle1_report_v1.schema.json",
    "v11.0.0/data/bao/desi/README.md",
    "v11.0.0/data/bao/desi/desi_dr1_bao_baseline.csv",
)

REQUIRED_M152_EXPANSION = (
    "v11.0.0/docs/LEGACY_VERSIONED_ARTIFACTS.md",
)

REQUIRED_M157_EXPANSION = (
    "v11.0.0/scripts/phase4_triangle1_joint_sn_bao_epsilon_posterior.py",
    "v11.0.0/schemas/phase4_triangle1_joint_sn_bao_epsilon_posterior_report_v1.schema.json",
    "v11.0.0/scripts/phase4_desi_bao_convert_gaussian_to_internal.py",
    "v11.0.0/scripts/phase4_triangle1_sn_bao_planck_thetastar.py",
    "v11.0.0/schemas/phase4_triangle1_report_v1.schema.json",
    "v11.0.0/tests/fixtures/phase4_m157/desi_gaussian_mean_toy.txt",
    "v11.0.0/tests/fixtures/phase4_m157/desi_gaussian_cov_toy.txt",
)

REQUIRED_M158_EXPANSION = (
    "v11.0.0/scripts/phase4_make_paper2_artifacts.py",
    "v11.0.0/scripts/phase4_build_paper2_assets.py",
    "v11.0.0/scripts/build_paper2.sh",
    "v11.0.0/scripts/make_paper2_arxiv_bundle.py",
    "v11.0.0/scripts/phase4_make_arxiv_bundle_paper2.py",
    "v11.0.0/scripts/phase4_joss_preflight.py",
    "v11.0.0/schemas/phase4_paper2_artifacts_manifest_v1.schema.json",
    "v11.0.0/schemas/phase4_paper2_assets_manifest_v1.schema.json",
    "v11.0.0/schemas/phase4_joss_preflight_report_v1.schema.json",
    "v11.0.0/docs/PAPER2_SUBMISSION.md",
    "v11.0.0/docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md",
    "v11.0.0/docs/ARXIV_SUBMISSION_CHECKLIST.md",
    "v11.0.0/docs/JOSS_SUBMISSION.md",
    "v11.0.0/docs/JOSS_SUBMISSION_CHECKLIST.md",
    "v11.0.0/papers/paper2_measurement_model_epsilon/main.tex",
    "v11.0.0/papers/paper2_measurement_model_epsilon/paper2.tex",
    "v11.0.0/papers/paper2_measurement_model_epsilon/refs.bib",
    "v11.0.0/papers/paper2_measurement_model_epsilon/paper2.bib",
    "v11.0.0/papers/paper2_measurement_model_epsilon/numbers.tex",
    "v11.0.0/papers/paper2_measurement_model_epsilon/README.md",
)

REQUIRED_M159_EXPANSION = (
    "v11.0.0/docs/PAPER2_SUBMISSION_GUIDE.md",
    "v11.0.0/docs/ARXIV_METADATA.md",
    "v11.0.0/docs/ARXIV_UPLOAD_CHECKLIST.md",
    "v11.0.0/docs/JOSS_AUTHORS.md",
    "v11.0.0/docs/JOSS_SUBMISSION_GUIDE.md",
)

REQUIRED_M160_EXPANSION = (
    "v11.0.0/bridges/phase4_qcd_gravity_bridge_v0.1/tools/make_qcd_gravity_bridge_artifacts.py",
    "v11.0.0/bridges/phase4_qcd_gravity_bridge_v0.1/report/QCD_Gravity_Bridge_v0.1.md",
    "v11.0.0/bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_numbers.json",
    "v11.0.0/bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_kill_matrix.csv",
    "v11.0.0/bridges/phase4_qcd_gravity_bridge_v0.1/golden/qcd_gravity_bridge_scale_plot.png",
    "v11.0.0/tests/test_phase4_m160_qcd_gravity_bridge_artifacts_deterministic.py",
)

REQUIRED_M161_EXPANSION = (
    "v11.0.0/docs/AFFILIATION_AND_BRANDING.md",
    "v11.0.0/outreach/labs_site_copy/labs_index.md",
    "v11.0.0/outreach/labs_site_copy/labs_gsc.md",
    "v11.0.0/outreach/labs_site_copy/labs_paper2.md",
    "v11.0.0/outreach/labs_site_copy/labs_cosmofalsify.md",
    "v11.0.0/outreach/labs_site_copy/labs_transparency.md",
    "v11.0.0/outreach/labs_site_copy/labs_press_kit.md",
    "v11.0.0/outreach/templates/email_researcher_feedback.md",
    "v11.0.0/outreach/templates/email_oss_maintainer_feedback.md",
    "v11.0.0/outreach/templates/email_journalist_pitch.md",
    "v11.0.0/tests/test_phase4_publish_branding_pack_present_and_nonempty.py",
)

REQUIRED_M163_EXPANSION = (
    "v11.0.0/scripts/phase4_m163_five_problems_report.py",
    "v11.0.0/schemas/phase4_m163_five_problems_report_v1.schema.json",
    "v11.0.0/tests/test_phase4_m163_five_problems_report_determinism_toy.py",
    "v11.0.0/tests/test_phase4_m163_schema_validate_auto_toy.py",
    "v11.0.0/docs/research_notes/PHASE4_M163_FIVE_PROBLEMS.md",
)


class TestPhase2M108RepoInventoryRequirePresent(unittest.TestCase):
    def test_require_present_passes_and_has_sha256(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                "v11.0.0",
                "--require-present",
                "--format",
                "json",
            ],
            cwd=str(ROOT.parent),
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
