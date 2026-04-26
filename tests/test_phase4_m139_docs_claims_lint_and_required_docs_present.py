from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

REQUIRED_DOCS = (
    ROOT / "docs" / "REVIEW_START_HERE.md",
    ROOT / "docs" / "VERIFICATION_MATRIX.md",
    ROOT / "docs" / "FRAMES_UNITS_INVARIANTS.md",
    ROOT / "docs" / "DATA_LICENSES_AND_SOURCES.md",
    ROOT / "docs" / "DATASET_ONBOARDING_POLICY.md",
    ROOT / "docs" / "AI_USAGE_AND_VALIDATION_POLICY.md",
    ROOT / "docs" / "DM_DECISION_MEMO.md",
    ROOT / "docs" / "EPSILON_FRAMEWORK_READINESS.md",
    ROOT / "docs" / "LEGACY_VERSIONED_ARTIFACTS.md",
    ROOT / "docs" / "PRIOR_ART_AND_NOVELTY_MAP.md",
    ROOT / "docs" / "GSC_Consolidated_Roadmap_v2.8.md",
    ROOT / "docs" / "GSC_Consolidated_Roadmap_v2.8.1_patch.md",
)

REQUIRED_LINT_REL = (
    "docs/REVIEW_START_HERE.md",
    "docs/VERIFICATION_MATRIX.md",
    "docs/FRAMES_UNITS_INVARIANTS.md",
    "docs/DATA_LICENSES_AND_SOURCES.md",
    "docs/DATASET_ONBOARDING_POLICY.md",
    "docs/AI_USAGE_AND_VALIDATION_POLICY.md",
    "docs/DM_DECISION_MEMO.md",
    "docs/EPSILON_FRAMEWORK_READINESS.md",
    "docs/LEGACY_VERSIONED_ARTIFACTS.md",
    "docs/PRIOR_ART_AND_NOVELTY_MAP.md",
    "docs/GSC_Consolidated_Roadmap_v2.8.md",
    "docs/GSC_Consolidated_Roadmap_v2.8.1_patch.md",
)


class TestPhase4M139DocsClaimsLintAndRequiredDocsPresent(unittest.TestCase):
    def test_required_docs_exist(self) -> None:
        for path in REQUIRED_DOCS:
            self.assertTrue(path.is_file(), msg=f"missing required doc: {path}")

    def test_docs_claims_lint_covers_new_docs(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import docs_claims_lint as lint  # noqa: E402
        finally:
            sys.path.pop(0)
        listed = set(lint.DEFAULT_REL_FILES)
        for rel in REQUIRED_LINT_REL:
            self.assertIn(rel, listed, msg=f"{rel} missing from DEFAULT_REL_FILES")

    def test_docs_claims_lint_passes(self) -> None:
        script = SCRIPTS / "docs_claims_lint.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--repo-root", "v11.0.0"],
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)


if __name__ == "__main__":
    unittest.main()
