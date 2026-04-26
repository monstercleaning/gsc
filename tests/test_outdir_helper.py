import os
import unittest
from pathlib import Path
from unittest.mock import patch
import sys


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _outdir import resolve_outdir, resolve_path_under_outdir  # noqa: E402


class TestOutdirHelper(unittest.TestCase):
    def test_default_outdir_is_versioned_artifacts_release(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GSC_OUTDIR", None)
            out = resolve_outdir(None, v101_dir=ROOT)
        self.assertEqual(out, (ROOT / "artifacts" / "release").resolve())

    def test_env_outdir_used_when_cli_missing(self):
        with patch.dict(os.environ, {"GSC_OUTDIR": "tmp/gsc_out"}, clear=False):
            out = resolve_outdir(None, v101_dir=ROOT)
        self.assertEqual(out, (REPO_ROOT / "tmp" / "gsc_out").resolve())

    def test_cli_outdir_takes_precedence_over_env(self):
        with patch.dict(os.environ, {"GSC_OUTDIR": "tmp/from_env"}, clear=False):
            out = resolve_outdir(Path("tmp/from_cli"), v101_dir=ROOT)
        self.assertEqual(out, (REPO_ROOT / "tmp" / "from_cli").resolve())

    def test_resolve_path_under_outdir_relative_and_absolute(self):
        out_root = (ROOT / "artifacts" / "release").resolve()
        rel = resolve_path_under_outdir(Path("reports/operator.json"), out_root=out_root)
        self.assertEqual(rel, (out_root / "reports" / "operator.json").resolve())

        abs_path = (ROOT / "README.md").resolve()
        abs_resolved = resolve_path_under_outdir(abs_path, out_root=out_root)
        self.assertEqual(abs_resolved, abs_path)

        self.assertIsNone(resolve_path_under_outdir(None, out_root=out_root))


if __name__ == "__main__":
    unittest.main()
