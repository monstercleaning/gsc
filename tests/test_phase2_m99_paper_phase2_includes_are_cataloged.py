import json
import re
import subprocess
import sys
from pathlib import Path
import unittest

from tests._v12_layout import retired_artifact_skip_reason


ROOT = Path(__file__).resolve().parents[1]

# v12.6: the v10.1 monolithic paper was consciously retired from the v12
# layout; this guard skips iff the retirement is declared (an undeclared
# absence raises). The v11 tree runs the same guard against the real file.
_RETIRED_SKIP = retired_artifact_skip_reason(ROOT, "GSC_Framework_v10_1_FINAL.tex")
SCRIPT = ROOT / "scripts" / "phase2_e2_snippets_catalog.py"
TEX = ROOT / "GSC_Framework_v10_1_FINAL.tex"
MD = ROOT / "GSC_Framework_v10_1_FINAL.md"

SNIPPET_PATH_PATTERN = re.compile(r"snippets/(phase2_[a-z0-9_]+)\.(?:tex|md)")


@unittest.skipIf(bool(_RETIRED_SKIP), _RETIRED_SKIP or "")
class TestPhase2M99PaperPhase2IncludesAreCataloged(unittest.TestCase):
    def test_phase2_snippet_includes_are_cataloged(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(TEX.is_file())
        self.assertTrue(MD.is_file())

        paper_stems = set(SNIPPET_PATH_PATTERN.findall(TEX.read_text(encoding="utf-8")))
        paper_stems.update(SNIPPET_PATH_PATTERN.findall(MD.read_text(encoding="utf-8")))
        self.assertTrue(paper_stems, msg="no phase2 snippet includes found in paper files")

        run = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            cwd=str(ROOT.parent),
            capture_output=True,
            text=True,
        )
        out = (run.stdout or "") + (run.stderr or "")
        self.assertEqual(run.returncode, 0, msg=out)

        payload = json.loads(run.stdout)
        catalog_stems = set(payload.get("all_order") or [])
        all_stem = payload.get("all_stem")
        if isinstance(all_stem, str) and all_stem:
            catalog_stems.add(all_stem)

        missing = sorted(paper_stems.difference(catalog_stems))
        self.assertFalse(missing, msg=f"paper includes missing from snippets catalog: {missing}")


if __name__ == "__main__":
    unittest.main()
