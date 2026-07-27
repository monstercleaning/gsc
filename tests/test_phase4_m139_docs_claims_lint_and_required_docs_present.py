from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# v12.6 reconciliation: the original lists froze the v11 doc layout; the v12
# layout relocated those docs into archive/legacy_docs/ and this test kept
# asserting the old paths (part of the inherited doc-layout failure class
# recorded in AUDIT.md). The lists now name (a) the v12 package's own living
# entry-point docs and (b) the relocated legacy docs at their real locations.
REQUIRED_DOCS = (
    # living v12 entry points
    ROOT / "INDEX.md",
    ROOT / "QUICKSTART.md",
    ROOT / "CHANGELOG.md",
    ROOT / "GSC_Framework.md",
    ROOT / "docs" / "pre_registration.md",
    ROOT / "docs" / "claim_verification.md",
    # living reviewer-facing docs
    ROOT / "docs" / "VERIFICATION_MATRIX.md",
    ROOT / "docs" / "FRAMES_UNITS_INVARIANTS.md",
    ROOT / "docs" / "DATA_LICENSES_AND_SOURCES.md",
    ROOT / "docs" / "DATASET_ONBOARDING_POLICY.md",
    ROOT / "docs" / "AI_USAGE_AND_VALIDATION_POLICY.md",
    # relocated legacy docs (still shipped; see scripts/docs_claims_lint.py)
    ROOT / "archive" / "legacy_docs" / "REVIEW_START_HERE.md",
    ROOT / "archive" / "legacy_docs" / "DM_DECISION_MEMO.md",
    ROOT / "archive" / "legacy_docs" / "EPSILON_FRAMEWORK_READINESS.md",
    ROOT / "archive" / "legacy_docs" / "LEGACY_VERSIONED_ARTIFACTS.md",
    ROOT / "archive" / "legacy_docs" / "PRIOR_ART_AND_NOVELTY_MAP.md",
    ROOT / "archive" / "legacy_docs" / "GSC_Consolidated_Roadmap_v2.8.md",
    ROOT / "archive" / "legacy_docs" / "GSC_Consolidated_Roadmap_v2.8.1_patch.md",
)

REQUIRED_LINT_REL = (
    "docs/VERIFICATION_MATRIX.md",
    "docs/FRAMES_UNITS_INVARIANTS.md",
    "docs/DATA_LICENSES_AND_SOURCES.md",
    "docs/DATASET_ONBOARDING_POLICY.md",
    "docs/AI_USAGE_AND_VALIDATION_POLICY.md",
    "archive/legacy_docs/REVIEW_START_HERE.md",
    "archive/legacy_docs/DM_DECISION_MEMO.md",
    "archive/legacy_docs/EPSILON_FRAMEWORK_READINESS.md",
    "archive/legacy_docs/LEGACY_VERSIONED_ARTIFACTS.md",
    "archive/legacy_docs/PRIOR_ART_AND_NOVELTY_MAP.md",
    "archive/legacy_docs/GSC_Consolidated_Roadmap_v2.8.md",
    "archive/legacy_docs/GSC_Consolidated_Roadmap_v2.8.1_patch.md",
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
        # Lint THIS package. (The original test linted the sibling v11.0.0
        # tree via cwd=ROOT.parent — impossible in the public root layout and
        # in unzipped deposits, and redundant: the v11 tree runs its own copy
        # of this lint in its own suite.)
        script = SCRIPTS / "docs_claims_lint.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--repo-root", str(ROOT)],
            text=True,
            capture_output=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)


if __name__ == "__main__":
    unittest.main()
