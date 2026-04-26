import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import sys


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import operator_one_button as op  # noqa: E402


def _sha256_bytes(payload: bytes) -> str:
    h = hashlib.sha256()
    h.update(payload)
    return h.hexdigest()


def _entries_for_files(base: Path) -> dict[str, dict[str, str]]:
    items = {
        "late_time": "paper_assets_v10.1.1-late-time-r4.zip",
        "submission": "submission_bundle_v10.1.1-late-time-r4.zip",
        "referee_pack": "referee_pack_v10.1.1-late-time-r4-r7.zip",
        "toe_bundle": "toe_bundle_v10.1.1-r2.zip",
    }
    out: dict[str, dict[str, str]] = {}
    for idx, (key, name) in enumerate(items.items(), start=1):
        payload = f"{key}-{idx}".encode("utf-8")
        (base / name).write_bytes(payload)
        out[key] = {
            "tag": f"v-{key}",
            "asset": name,
            "sha256": _sha256_bytes(payload),
            "release_url": f"https://github.com/org/repo/releases/tag/v-{key}",
        }
    return out


class TestOperatorOneButtonUploadPortal(unittest.TestCase):
    def test_prepare_upload_portal_structure_and_checksums(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            entries = _entries_for_files(td)
            upload_dir = td / "upload_portal"

            fake_v101 = td / "fake_v101"
            fake_v101.mkdir(parents=True, exist_ok=True)

            with mock.patch.object(op, "V101_DIR", fake_v101):
                info = op._prepare_upload_portal(
                    entries=entries,
                    artifacts_dir=td,
                    upload_dir=upload_dir,
                    mode="copy",
                )

            self.assertEqual(info["path"], str(upload_dir))
            self.assertTrue((upload_dir / "arxiv" / entries["submission"]["asset"]).is_file())
            self.assertTrue((upload_dir / "referee_pack" / entries["referee_pack"]["asset"]).is_file())
            self.assertTrue((upload_dir / "toe" / entries["toe_bundle"]["asset"]).is_file())
            self.assertTrue((upload_dir / "late_time" / entries["late_time"]["asset"]).is_file())
            self.assertFalse((upload_dir / "late_time" / "GSC_Framework_v10_1_FINAL.pdf").is_file())
            self.assertTrue((upload_dir / "checksums" / "SHA256SUMS.txt").is_file())
            self.assertTrue((upload_dir / "README_UPLOAD.md").is_file())
            expected_tree = sorted(
                [
                    f"arxiv/{entries['submission']['asset']}",
                    f"referee_pack/{entries['referee_pack']['asset']}",
                    f"toe/{entries['toe_bundle']['asset']}",
                    f"late_time/{entries['late_time']['asset']}",
                    "CHECKLIST_PUBLISH.md",
                    "checksums/SHA256SUMS.txt",
                    "README_UPLOAD.md",
                ]
            )
            got_tree = sorted(
                p.relative_to(upload_dir).as_posix()
                for p in upload_dir.rglob("*")
                if p.is_file()
            )
            for rel in expected_tree:
                self.assertIn(rel, got_tree)

            checksums = (upload_dir / "checksums" / "SHA256SUMS.txt").read_text(encoding="utf-8")
            checksum_lines = [ln for ln in checksums.strip().splitlines() if ln.strip()]
            checksum_map = {}
            for ln in checksum_lines:
                sha, rel = ln.split("  ", 1)
                checksum_map[rel] = sha
            self.assertEqual(checksum_lines, sorted(checksum_lines, key=lambda x: x.split("  ", 1)[1]))
            self.assertEqual(checksum_map[f"arxiv/{entries['submission']['asset']}"], entries["submission"]["sha256"])
            self.assertEqual(checksum_map[f"toe/{entries['toe_bundle']['asset']}"], entries["toe_bundle"]["sha256"])
            self.assertIn("README_UPLOAD.md", checksum_map)
            self.assertIn("CHECKLIST_PUBLISH.md", checksum_map)
            readme = (upload_dir / "README_UPLOAD.md").read_text(encoding="utf-8")
            self.assertIn("What to upload", readme)
            self.assertIn(f"`arxiv/{entries['submission']['asset']}`", readme)
            self.assertIn("| id | filename | expected_sha256 | canonical tag | release |", readme)
            self.assertIn("No staged PDF", readme)
            self.assertFalse(info["pdf_from_submission_bundle"])
            self.assertTrue(info["portal_warnings"])

    def test_prepare_upload_portal_fails_on_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            entries = _entries_for_files(td)
            entries["submission"]["sha256"] = "0" * 64
            upload_dir = td / "upload_portal"

            fake_v101 = td / "fake_v101"
            fake_v101.mkdir(parents=True, exist_ok=True)

            with mock.patch.object(op, "V101_DIR", fake_v101):
                with self.assertRaises(RuntimeError) as ctx:
                    op._prepare_upload_portal(
                        entries=entries,
                        artifacts_dir=td,
                        upload_dir=upload_dir,
                        mode="copy",
                    )

            self.assertIn("sha256 mismatch for submission", str(ctx.exception))
            self.assertFalse(upload_dir.exists())

    def test_operator_summary_file_contains_status_and_sha_lines(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            entries = _entries_for_files(td)
            upload_dir = td / "upload_portal"
            fake_v101 = td / "fake_v101"
            fake_v101.mkdir(parents=True, exist_ok=True)

            with mock.patch.object(op, "V101_DIR", fake_v101):
                info = op._prepare_upload_portal(
                    entries=entries,
                    artifacts_dir=td,
                    upload_dir=upload_dir,
                    mode="copy",
                )

            snapshot = op._snapshot_with_integrity(entries, td)
            steps = [
                op.StepResult(
                    name="alpha",
                    cmd=["alpha"],
                    exit_code=0,
                    status="PASS",
                    started_utc="2026-01-01T00:00:00+00:00",
                    finished_utc="2026-01-01T00:00:01+00:00",
                    duration_sec=1.0,
                )
            ]
            summary_path = op._write_operator_summary_file(
                upload_portal=info,
                result="PASS",
                steps=steps,
                snapshot=snapshot,
                warnings=["example warning"],
                rc_check={
                    "arxiv_preflight": {
                        "result": "WARN",
                        "warnings": ["zip size warning"],
                    }
                },
                reports_staged={
                    "operator_report": True,
                    "rc_check": True,
                    "arxiv_preflight": True,
                },
            )
            text = Path(summary_path).read_text(encoding="utf-8")
            self.assertIn("overall_status=PASS", text)
            self.assertIn("staged_artifacts:", text)
            self.assertIn("id=submission", text)
            self.assertIn("sha_match=True", text)
            self.assertIn("warnings:", text)
            self.assertIn("example warning", text)
            self.assertIn("arxiv_preflight=WARN (zip size warning)", text)
            self.assertIn("pdf_from_submission_bundle=no", text)
            self.assertIn("reports_staged:", text)
            self.assertIn("operator_report.json=yes", text)
            self.assertIn("rc_check.json=yes", text)
            self.assertIn("arxiv_preflight.json=yes", text)

    def test_prepare_upload_zip_writes_archive_and_sha(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            entries = _entries_for_files(td)
            upload_dir = td / "upload_portal"
            fake_v101 = td / "fake_v101"
            fake_v101.mkdir(parents=True, exist_ok=True)

            with mock.patch.object(op, "V101_DIR", fake_v101):
                info = op._prepare_upload_portal(
                    entries=entries,
                    artifacts_dir=td,
                    upload_dir=upload_dir,
                    mode="copy",
                )
                out_zip = td / "upload_portal.zip"
                zinfo = op._zip_upload_portal(upload_dir, out_zip)

            self.assertTrue(out_zip.is_file())
            self.assertTrue(Path(zinfo["sha256_file"]).is_file())
            self.assertEqual(zinfo["sha256"], op._sha256_file(out_zip))
            with zipfile.ZipFile(out_zip, "r") as zf:
                names = sorted(zf.namelist())
            self.assertIn("README_UPLOAD.md", names)
            self.assertIn("checksums/SHA256SUMS.txt", names)
            self.assertIn(f"arxiv/{entries['submission']['asset']}", names)
            info["portal_zip"] = zinfo
            summary_path = op._write_operator_summary_file(
                upload_portal=info,
                result="PASS",
                steps=[],
                snapshot=op._snapshot_with_integrity(entries, td),
                warnings=[],
            )
            text = Path(summary_path).read_text(encoding="utf-8")
            self.assertIn("upload_portal_zip:", text)
            self.assertIn("sha256=", text)

    def test_prepare_upload_portal_stages_compiled_pdf_and_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            entries = _entries_for_files(td)
            upload_dir = td / "upload_portal"
            compiled_pdf = td / "compiled_from_submission.pdf"
            compiled_pdf.write_bytes(b"%PDF-1.4\n%fake\n")
            compiled_sha = op._sha256_file(compiled_pdf)
            compile_pdf = {
                "produced": True,
                "path": str(compiled_pdf),
                "sha256": compiled_sha,
                "main_tex": "GSC_Framework_v10_1_FINAL.tex",
                "bib_mode": "bibtex",
            }
            fake_v101 = td / "fake_v101"
            fake_v101.mkdir(parents=True, exist_ok=True)

            with mock.patch.object(op, "V101_DIR", fake_v101):
                info = op._prepare_upload_portal(
                    entries=entries,
                    artifacts_dir=td,
                    upload_dir=upload_dir,
                    mode="copy",
                    compile_pdf=compile_pdf,
                )

            staged_pdf = upload_dir / "late_time" / "GSC_Framework_v10_1_FINAL.pdf"
            self.assertTrue(staged_pdf.is_file())
            self.assertEqual(op._sha256_file(staged_pdf), compiled_sha)
            prov = upload_dir / "late_time" / "PDF_PROVENANCE.txt"
            self.assertTrue(prov.is_file())
            prov_text = prov.read_text(encoding="utf-8")
            self.assertIn("source_submission_asset=submission_bundle_v10.1.1-late-time-r4.zip", prov_text)
            self.assertIn(f"compiled_pdf_sha256={compiled_sha}", prov_text)
            self.assertIn("Compiled from canonical submission bundle", prov_text)
            self.assertTrue(info["pdf_from_submission_bundle"])
            self.assertEqual(info["pdf_sha256"], compiled_sha)
            self.assertEqual(info["portal_warnings"], [])

    def test_prepare_upload_portal_records_warning_when_compile_pdf_missing(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            entries = _entries_for_files(td)
            upload_dir = td / "upload_portal"
            fake_v101 = td / "fake_v101"
            fake_v101.mkdir(parents=True, exist_ok=True)

            with mock.patch.object(op, "V101_DIR", fake_v101):
                info = op._prepare_upload_portal(
                    entries=entries,
                    artifacts_dir=td,
                    upload_dir=upload_dir,
                    mode="copy",
                    compile_pdf=None,
                )

            self.assertFalse(info["pdf_from_submission_bundle"])
            self.assertTrue(info["portal_warnings"])
            self.assertFalse((upload_dir / "late_time" / "GSC_Framework_v10_1_FINAL.pdf").is_file())

    def test_stage_portal_reports_and_checksums_include_reports(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            entries = _entries_for_files(td)
            upload_dir = td / "upload_portal"
            fake_v101 = td / "fake_v101"
            fake_v101.mkdir(parents=True, exist_ok=True)

            with mock.patch.object(op, "V101_DIR", fake_v101):
                info = op._prepare_upload_portal(
                    entries=entries,
                    artifacts_dir=td,
                    upload_dir=upload_dir,
                    mode="copy",
                )

            operator_payload = {"overall_status": "PASS", "result": "PASS", "steps": []}
            rc_payload = {
                "overall_status": "PASS",
                "result": "PASS",
                "arxiv_preflight": {"overall_status": "WARN", "result": "WARN"},
            }
            staged = op._stage_portal_reports(
                upload_portal=info,
                operator_payload=operator_payload,
                rc_payload=rc_payload,
            )
            self.assertTrue(staged["operator_report"])
            self.assertTrue((upload_dir / "reports" / "operator_report.json").is_file())
            self.assertTrue((upload_dir / "reports" / "rc_check.json").is_file())
            self.assertTrue((upload_dir / "reports" / "arxiv_preflight.json").is_file())
            self.assertTrue((upload_dir / "reports" / "README_REPORTS.md").is_file())

            op._rewrite_portal_checksums(upload_dir)
            checksums = (upload_dir / "checksums" / "SHA256SUMS.txt").read_text(encoding="utf-8")
            self.assertIn("reports/operator_report.json", checksums)
            self.assertIn("reports/rc_check.json", checksums)
            self.assertIn("reports/arxiv_preflight.json", checksums)
            self.assertIn("CHECKLIST_PUBLISH.md", checksums)


if __name__ == "__main__":
    unittest.main()
