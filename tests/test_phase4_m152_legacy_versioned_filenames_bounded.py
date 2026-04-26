from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]

ALLOWED_PREFIXES = (
    "GSC/v11.0.0/GSC_v10_1_release/",
    "GSC/v11.0.0/GSC_v10_1_simulations/",
    "GSC/v11.0.0/scripts/reproduce_v10_1_",
    "GSC/v11.0.0/GSC_Framework_v10_1_FINAL.",
    "GSC/GSC_Framework_v10",
    "GSC/v11.0.0/archive/legacy/",
    "GSC/v11.0.0/B/GSC_Phase10_MochiClass_Integration_v10_8.pdf",
)

SKIP_PARTS = {".git", "__pycache__", ".venv"}


def _contains_v10_component(rel_posix: str) -> bool:
    parts = rel_posix.lower().split("/")
    return any("v10" in part for part in parts)


class TestPhase4M152LegacyVersionedFilenamesBounded(unittest.TestCase):
    def test_v10_paths_are_bounded_to_allowlist(self) -> None:
        offenders = []
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if any(part in SKIP_PARTS for part in rel.split("/")):
                continue
            if not _contains_v10_component(rel):
                continue
            scoped = f"GSC/{rel}"
            if not any(scoped.startswith(prefix) for prefix in ALLOWED_PREFIXES):
                offenders.append(scoped)
        self.assertEqual([], offenders, msg="unexpected v10* paths:\n" + "\n".join(offenders))

    def test_root_legacy_wrappers_have_historical_do_not_submit_banner(self) -> None:
        wrappers = sorted(ROOT.glob("GSC_Framework_v10*.md"))
        for wrapper in wrappers:
            with wrapper.open("r", encoding="utf-8") as fh:
                first_30 = "".join([next(fh, "") for _ in range(30)]).lower()
            self.assertIn("historical", first_30, msg=f"missing HISTORICAL banner in {wrapper}")
            self.assertIn(
                "do not submit",
                first_30,
                msg=f"missing DO NOT SUBMIT banner in {wrapper}",
            )


if __name__ == "__main__":
    unittest.main()
