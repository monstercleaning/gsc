import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCAN_SCRIPT = ROOT / "scripts" / "phase2_e2_scan.py"
MERGE_SCRIPT = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
BUNDLE_SCRIPT = ROOT / "scripts" / "phase2_e2_bundle.py"
VERIFY_SCRIPT = ROOT / "scripts" / "phase2_e2_verify_bundle.py"
PAPER_ASSETS_SCRIPT = ROOT / "scripts" / "phase2_e2_make_paper_assets.py"


class TestPhase2M111GoldenToyPipelineBundleAndPaperAssets(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_golden_toy_pipeline_produces_lineage_and_consistency_reports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            scan_out = td_path / "scan_out"
            scan = self._run(
                [
                    sys.executable,
                    str(SCAN_SCRIPT),
                    "--model",
                    "lcdm",
                    "--toy",
                    "--grid",
                    "H0=67.4",
                    "--grid",
                    "Omega_m=0.315",
                    "--out-dir",
                    str(scan_out),
                ]
            )
            self.assertEqual(scan.returncode, 0, msg=(scan.stdout or "") + (scan.stderr or ""))
            scan_jsonl = scan_out / "e2_scan_points.jsonl"
            self.assertTrue(scan_jsonl.is_file(), msg=str(scan_jsonl))

            merged_jsonl = td_path / "merged.jsonl"
            merge = self._run(
                [
                    sys.executable,
                    str(MERGE_SCRIPT),
                    str(scan_jsonl),
                    str(scan_jsonl),
                    "--out",
                    str(merged_jsonl),
                    "--report-out",
                    str(td_path / "merge_report.json"),
                ]
            )
            self.assertEqual(merge.returncode, 0, msg=(merge.stdout or "") + (merge.stderr or ""))
            self.assertTrue(merged_jsonl.is_file(), msg=str(merged_jsonl))

            bundle_dir = td_path / "bundle"
            bundle = self._run(
                [
                    sys.executable,
                    str(BUNDLE_SCRIPT),
                    "--in",
                    str(merged_jsonl),
                    "--in",
                    str(merged_jsonl),
                    "--outdir",
                    str(bundle_dir),
                    "--steps",
                    "merge,manifest,meta",
                ]
            )
            self.assertEqual(bundle.returncode, 0, msg=(bundle.stdout or "") + (bundle.stderr or ""))
            self.assertTrue((bundle_dir / "manifest.json").is_file())
            self.assertTrue((bundle_dir / "LINEAGE.json").is_file())

            verify = self._run([sys.executable, str(VERIFY_SCRIPT), "--bundle", str(bundle_dir)])
            self.assertEqual(verify.returncode, 0, msg=(verify.stdout or "") + (verify.stderr or ""))

            paper_assets_out = td_path / "paper_assets_out"
            paper = self._run(
                [
                    sys.executable,
                    str(PAPER_ASSETS_SCRIPT),
                    "--jsonl",
                    str(merged_jsonl),
                    "--mode",
                    "all",
                    "--outdir",
                    str(paper_assets_out),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ]
            )
            self.assertEqual(paper.returncode, 0, msg=(paper.stdout or "") + (paper.stderr or ""))

            manifest_path = paper_assets_out / "paper_assets_manifest.json"
            consistency_json = (
                paper_assets_out
                / "paper_assets_cmb_e2_closure_to_physical_knobs"
                / "consistency"
                / "CONSISTENCY_REPORT.json"
            )
            consistency_md = (
                paper_assets_out
                / "paper_assets_cmb_e2_closure_to_physical_knobs"
                / "consistency"
                / "CONSISTENCY_REPORT.md"
            )
            self.assertTrue(manifest_path.is_file(), msg=str(manifest_path))
            self.assertTrue(consistency_json.is_file(), msg=str(consistency_json))
            self.assertTrue(consistency_md.is_file(), msg=str(consistency_md))

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = manifest.get("files") or []
            relpaths = {str(row.get("relpath", "")) for row in files if isinstance(row, dict)}
            self.assertIn(
                "paper_assets_cmb_e2_closure_to_physical_knobs/consistency/CONSISTENCY_REPORT.json",
                relpaths,
            )
            self.assertIn(
                "paper_assets_cmb_e2_closure_to_physical_knobs/consistency/CONSISTENCY_REPORT.md",
                relpaths,
            )


if __name__ == "__main__":
    unittest.main()
