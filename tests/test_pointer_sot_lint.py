import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _write_catalog(path: Path) -> dict:
    obj = {
        "schema_version": 2,
        "artifacts": {
            "late_time": {
                "type": "late-time",
                "tier": "frozen",
                "tag": "v10.1.1-late-time-r4",
                "release_url": "https://example.com/late",
                "asset": "paper_assets_v10.1.1-late-time-r4.zip",
                "sha256": "a" * 64,
            },
            "submission": {
                "type": "submission",
                "tier": "frozen",
                "tag": "v10.1.1-submission-r2",
                "release_url": "https://example.com/sub",
                "asset": "submission_bundle_v10.1.1-late-time-r4.zip",
                "sha256": "b" * 64,
            },
            "referee_pack": {
                "type": "referee",
                "tier": "recommended",
                "tag": "v10.1.1-referee-pack-r7",
                "release_url": "https://example.com/ref",
                "asset": "referee_pack_v10.1.1-late-time-r4-r7.zip",
                "sha256": "c" * 64,
            },
            "toe_bundle": {
                "type": "toe",
                "tier": "recommended",
                "tag": "v10.1.1-toe-track-r1",
                "release_url": "https://example.com/toe",
                "asset": "toe_bundle_v10.1.1-r1.zip",
                "sha256": "d" * 64,
            },
        },
    }
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    return obj


class TestPointerSotLint(unittest.TestCase):
    def test_passes_for_consistent_tokens(self):
        import pointer_sot_lint as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "README.md").write_text("root pointer\n", encoding="utf-8")
            (repo / "GSC_ONBOARDING_NEXT_SESSION.md").write_text("onboard pointer\n", encoding="utf-8")
            (repo / "v11.0.0").mkdir(parents=True, exist_ok=True)
            (repo / "v11.0.0" / "README.md").write_text("v101 pointer\n", encoding="utf-8")
            (repo / "v11.0.0" / "docs").mkdir(parents=True, exist_ok=True)
            (repo / "v11.0.0" / "docs" / "status_canonical_artifacts.md").write_text(
                "\n".join(
                    [
                        "v10.1.1-late-time-r4",
                        "paper_assets_v10.1.1-late-time-r4.zip",
                        "a" * 64,
                        "v10.1.1-submission-r2",
                        "submission_bundle_v10.1.1-late-time-r4.zip",
                        "b" * 64,
                        "v10.1.1-referee-pack-r7",
                        "referee_pack_v10.1.1-late-time-r4-r7.zip",
                        "c" * 64,
                        "v10.1.1-toe-track-r1",
                        "toe_bundle_v10.1.1-r1.zip",
                        "d" * 64,
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            catalog = repo / "v11.0.0" / "canonical_artifacts.json"
            _write_catalog(catalog)

            issues = m.run_lint(repo, catalog)
            self.assertEqual(issues, [])

    def test_fails_on_stale_pointer_without_exception_context(self):
        import pointer_sot_lint as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "README.md").write_text("Tag: v10.1.1-referee-pack-r6\n", encoding="utf-8")
            (repo / "GSC_ONBOARDING_NEXT_SESSION.md").write_text("", encoding="utf-8")
            (repo / "v11.0.0").mkdir(parents=True, exist_ok=True)
            (repo / "v11.0.0" / "README.md").write_text("", encoding="utf-8")
            (repo / "v11.0.0" / "docs").mkdir(parents=True, exist_ok=True)
            (repo / "v11.0.0" / "docs" / "status_canonical_artifacts.md").write_text("", encoding="utf-8")
            catalog = repo / "v11.0.0" / "canonical_artifacts.json"
            _write_catalog(catalog)

            issues = m.run_lint(repo, catalog)
            self.assertTrue(issues)
            self.assertEqual(issues[0].file, repo / "README.md")
            self.assertEqual(issues[0].line, 1)
            self.assertEqual(issues[0].found, "v10.1.1-referee-pack-r6")
            self.assertEqual(issues[0].expected, "v10.1.1-referee-pack-r7")


if __name__ == "__main__":
    unittest.main()
