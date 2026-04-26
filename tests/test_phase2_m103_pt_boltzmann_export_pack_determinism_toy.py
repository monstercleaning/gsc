import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_export_pack.py"


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase2M103PtBoltzmannExportPackDeterminismToy(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _write_lines(self, path: Path, lines: list[str]) -> None:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_deterministic_zip_and_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_a = td_path / "input_a.jsonl"
            input_b = td_path / "input_b.jsonl"

            rec_ok_worse = {
                "params_hash": "hash_ok_worse",
                "plan_point_id": "pp-worse",
                "status": "ok",
                "chi2_total": 5.2,
                "params": {"H0": 68.0, "omega_b": 0.049, "omega_m": 0.31},
            }
            rec_error = {
                "params_hash": "hash_error",
                "status": "error",
                "error": "synthetic_error",
                "chi2_total": 0.1,
            }
            rec_no_status = {
                "params_hash": "hash_unknown",
                "chi2_total": 0.2,
                "params": {"H0": 65.0},
            }
            rec_ok_best = {
                "params_hash": "hash_ok_best",
                "plan_point_id": "pp-best",
                "status": "ok",
                "chi2_total": 4.8,
                "chi2_joint_total": 5.4,
                "rsd_chi2_total": 0.6,
                "rsd_transfer_model": "eh98_nowiggle",
                "rsd_primordial_ns": 0.965,
                "rsd_primordial_k_pivot_mpc": 0.05,
                "params": {
                    "H0": 67.6,
                    "omega_b": 0.049,
                    "omega_m": 0.30,
                    "As": 2.1e-9,
                    "ns": 0.965,
                    "k_pivot_mpc": 0.05,
                },
            }

            self._write_lines(
                input_a,
                [
                    json.dumps(rec_ok_worse, sort_keys=True),
                    "{invalid_json_line",
                    json.dumps(rec_error, sort_keys=True),
                ],
            )
            self._write_lines(
                input_b,
                [
                    json.dumps(rec_no_status, sort_keys=True),
                    json.dumps(rec_ok_best, sort_keys=True),
                ],
            )

            created_utc = "2026-02-24T00:00:00Z"
            out1 = td_path / "out_1"
            out2 = td_path / "out_2"
            zip1 = td_path / "export_1.zip"
            zip2 = td_path / "export_2.zip"

            cmd_1 = [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(input_a),
                "--input",
                str(input_b),
                "--rank-by",
                "cmb",
                "--eligible-status",
                "ok_only",
                "--created-utc",
                created_utc,
                "--outdir",
                str(out1),
                "--zip-out",
                str(zip1),
                "--format",
                "json",
            ]
            run1 = self._run(cmd_1)
            self.assertEqual(run1.returncode, 0, msg=(run1.stdout or "") + (run1.stderr or ""))
            payload1 = json.loads(run1.stdout)

            cmd_2 = list(cmd_1)
            cmd_2[cmd_2.index(str(out1))] = str(out2)
            cmd_2[cmd_2.index(str(zip1))] = str(zip2)
            run2 = self._run(cmd_2)
            self.assertEqual(run2.returncode, 0, msg=(run2.stdout or "") + (run2.stderr or ""))
            payload2 = json.loads(run2.stdout)

            self.assertTrue(zip1.is_file())
            self.assertTrue(zip2.is_file())
            self.assertEqual(_sha256_path(zip1), _sha256_path(zip2))

            self.assertEqual(payload1.get("schema"), "phase2_pt_boltzmann_export_pack_v1")
            self.assertEqual(payload1.get("selection", {}).get("rank_by"), "cmb")
            self.assertEqual(payload1.get("inputs", {}).get("n_invalid_lines"), 1)
            self.assertEqual(payload1.get("best", {}).get("best_params_hash"), "hash_ok_best")
            self.assertEqual(payload2.get("best", {}).get("best_params_hash"), "hash_ok_best")

            summary_path = out1 / "EXPORT_SUMMARY.json"
            candidate_path = out1 / "CANDIDATE_RECORD.json"
            class_ini = out1 / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini"
            camb_ini = out1 / "BOLTZMANN_INPUT_TEMPLATE_CAMB.ini"
            readme = out1 / "README.md"
            for path in (summary_path, candidate_path, class_ini, camb_ini, readme):
                self.assertTrue(path.is_file(), msg=str(path))

            summary_json = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(list(summary_json.keys()), sorted(summary_json.keys()))
            self.assertEqual(summary_json.get("schema"), "phase2_pt_boltzmann_export_pack_v1")

            with zipfile.ZipFile(zip1, "r") as zf:
                names = sorted(zf.namelist())
                self.assertIn("boltzmann_export_pack/EXPORT_SUMMARY.json", names)
                self.assertIn("boltzmann_export_pack/CANDIDATE_RECORD.json", names)
                self.assertIn("boltzmann_export_pack/BOLTZMANN_INPUT_TEMPLATE_CLASS.ini", names)
                self.assertIn("boltzmann_export_pack/BOLTZMANN_INPUT_TEMPLATE_CAMB.ini", names)
                self.assertIn("boltzmann_export_pack/README.md", names)

                forbidden_fragments = (
                    "/.git/",
                    "/.venv/",
                    "/__macosx/",
                    "/site-packages/",
                    ".ds_store",
                    "/v11.0.0/archive/packs/",
                    "/v11.0.0/b/",
                    "submission_bundle",
                    "referee_pack",
                    "toe_bundle",
                    "publication_bundle",
                )
                for name in names:
                    lowered = "/" + name.lower().strip("/") + "/"
                    for fragment in forbidden_fragments:
                        self.assertNotIn(fragment, lowered, msg=name)

    def test_rank_by_rsd_missing_field_exits_2_with_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_jsonl = td_path / "input_missing_rsd.jsonl"
            rows = [
                {
                    "params_hash": "hash_ok",
                    "status": "ok",
                    "chi2_total": 3.1,
                },
                {
                    "params_hash": "hash_error",
                    "status": "error",
                    "chi2_total": 0.1,
                },
            ]
            with input_jsonl.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")

            outdir = td_path / "out_missing_rsd"
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(input_jsonl),
                "--rank-by",
                "rsd",
                "--eligible-status",
                "ok_only",
                "--created-utc",
                "2026-02-24T00:00:00Z",
                "--outdir",
                str(outdir),
            ]
            run = self._run(cmd)
            self.assertEqual(run.returncode, 2, msg=(run.stdout or "") + (run.stderr or ""))
            self.assertIn("MISSING_RSD_CHI2_FIELD_FOR_BOLTZMANN_EXPORT", run.stderr)


if __name__ == "__main__":
    unittest.main()
