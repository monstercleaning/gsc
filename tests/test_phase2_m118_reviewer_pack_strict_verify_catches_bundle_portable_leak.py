import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PACK_SCRIPT = ROOT / "scripts" / "phase2_e2_make_reviewer_pack.py"
LINEAGE_SCRIPT = ROOT / "scripts" / "phase2_lineage_dag.py"


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


class TestPhase2M118ReviewerPackStrictVerifyCatchesBundlePortableLeak(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _make_bundle_zip_with_payload(self, td_path: Path, payload: dict[str, object]) -> Path:
        bundle_dir = td_path / "bundle_dir"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_zip = td_path / "bundle.zip"
        payload_bytes = (json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        payload_path = bundle_dir / "payload.json"
        payload_path.write_bytes(payload_bytes)
        manifest = {
            "schema": "phase2_e2_manifest_v1",
            "artifacts": [
                {
                    "path": "payload.json",
                    "sha256": _sha256_bytes(payload_bytes),
                    "bytes": len(payload_bytes),
                }
            ],
            "inputs": [],
        }
        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        lineage = self._run(
            [
                sys.executable,
                str(LINEAGE_SCRIPT),
                "--bundle-dir",
                str(bundle_dir),
                "--out",
                str(bundle_dir / "LINEAGE.json"),
                "--format",
                "json",
            ]
        )
        self.assertEqual(lineage.returncode, 0, msg=(lineage.stdout or "") + (lineage.stderr or ""))

        with zipfile.ZipFile(bundle_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(bundle_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(bundle_dir).as_posix()
                zf.write(path, arcname=str(PurePosixPath("bundle") / rel))
        return bundle_zip

    def test_strict_verify_fails_on_absolute_path_leak_inside_bundle_zip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_zip = self._make_bundle_zip_with_payload(
                td_path,
                {"source_path": "/Users/demo/secret"},
            )
            outdir = td_path / "reviewer_pack_strict"
            summary_json = td_path / "summary_strict.json"
            proc = self._run(
                [
                    sys.executable,
                    str(REVIEWER_PACK_SCRIPT),
                    "--bundle",
                    str(bundle_zip),
                    "--outdir",
                    str(outdir),
                    "--include-repo-snapshot",
                    "0",
                    "--include-paper-assets",
                    "0",
                    "--include-verify",
                    "1",
                    "--format",
                    "json",
                    "--json-out",
                    str(summary_json),
                ]
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("PORTABLE_CONTENT_LINT_FAILED", output)

    def test_verify_strict_0_allows_legacy_compatibility_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_zip = self._make_bundle_zip_with_payload(
                td_path,
                {"source_path": "/var/folders/demo/leak"},
            )
            outdir = td_path / "reviewer_pack_compat"
            zip_out = td_path / "reviewer_pack_compat.zip"
            summary_json = td_path / "summary_compat.json"
            proc = self._run(
                [
                    sys.executable,
                    str(REVIEWER_PACK_SCRIPT),
                    "--bundle",
                    str(bundle_zip),
                    "--outdir",
                    str(outdir),
                    "--zip-out",
                    str(zip_out),
                    "--include-repo-snapshot",
                    "0",
                    "--include-paper-assets",
                    "0",
                    "--include-verify",
                    "1",
                    "--verify-strict",
                    "0",
                    "--format",
                    "json",
                    "--json-out",
                    str(summary_json),
                ]
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue(zip_out.is_file())
            summary = json.loads(summary_json.read_text(encoding="utf-8"))
            subtools = summary.get("subtools")
            self.assertIsInstance(subtools, list)
            verify_rows = [row for row in subtools if isinstance(row, dict) and row.get("name") == "phase2_e2_verify_bundle"]
            self.assertEqual(len(verify_rows), 1)
            verify_cmd = [str(x) for x in verify_rows[0].get("command", [])]
            self.assertNotIn("--validate-schemas", verify_cmd)
            self.assertNotIn("--lint-portable-content", verify_cmd)


if __name__ == "__main__":
    unittest.main()
