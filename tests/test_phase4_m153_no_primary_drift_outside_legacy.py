from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]

SCOPED_FILES = (
    ROOT / "README.md",
    ROOT / "GSC_ONBOARDING_NEXT_SESSION.md",
    ROOT / "v11.0.0" / "docs" / "REVIEW_START_HERE.md",
    ROOT / "v11.0.0" / "docs" / "VERIFICATION_MATRIX.md",
    ROOT / "v11.0.0" / "docs" / "project_status_and_roadmap.md",
    ROOT / "v11.0.0" / "scripts" / "paper_readiness_lint.py",
)

LEGACY_ALLOWLIST_PREFIXES = (
    ROOT / "v11.0.0" / "docs" / "GSC_Consolidated_Roadmap_v2.8.md",
    ROOT / "v11.0.0" / "GSC_v10_1_release",
    ROOT / "v11.0.0" / "GSC_v10_1_simulations",
)

_DRIFT_PRIMARY_PHRASES = (
    "primary falsifier",
    "primary discriminator",
    "key discriminant",
    "primary checkpoint",
)

_ALLOWED_CONTEXT = (
    "historical",
    "supporting",
    "deprecated",
    "superseded",
    "not the primary",
    "not primary",
)


class TestPhase4M153NoPrimaryDriftOutsideLegacy(unittest.TestCase):
    def test_scoped_files_do_not_frame_drift_as_primary(self) -> None:
        findings: list[str] = []
        for path in SCOPED_FILES:
            self.assertTrue(path.is_file(), msg=f"missing scoped file: {path}")
            if any(str(path).startswith(str(prefix)) for prefix in LEGACY_ALLOWLIST_PREFIXES):
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                line_lower = line.lower()
                if "golden test" in line_lower:
                    findings.append(f"{path}:{lineno}: forbidden token 'golden test'")
                    continue
                if "drift" not in line_lower:
                    continue
                if any(phrase in line_lower for phrase in _DRIFT_PRIMARY_PHRASES):
                    if not any(token in line_lower for token in _ALLOWED_CONTEXT):
                        findings.append(
                            f"{path}:{lineno}: drift framed as primary without historical/supporting context"
                        )

        self.assertEqual(
            findings,
            [],
            msg="\n".join(findings),
        )


if __name__ == "__main__":
    unittest.main()
