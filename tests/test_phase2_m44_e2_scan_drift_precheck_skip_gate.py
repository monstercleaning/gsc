import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHI2_SENTINEL = 1.0e99


def _write_plan(path: Path) -> None:
    payload = {
        "plan_version": "phase2_e2_refine_plan_v1",
        "source": {"jsonl_sha256": "m44_synthetic_source"},
        "points": [
            {"point_id": "p_fail", "params": {"H0": 67.4, "Omega_m": 0.90}},
            {"point_id": "p_ok", "params": {"H0": 67.4, "Omega_m": 0.30}},
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


class TestPhase2M44E2ScanDriftPrecheckSkipGate(unittest.TestCase):
    def test_toy_drift_precheck_emits_ok_and_skipped(self) -> None:
        scan_script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(scan_script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            outdir = td_path / "scan_out"
            _write_plan(plan)

            cmd = [
                sys.executable,
                str(scan_script),
                "--model",
                "lcdm",
                "--toy",
                "--plan",
                str(plan),
                "--out-dir",
                str(outdir),
                "--drift-precheck",
                "z2_5_positive",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            jsonl = outdir / "e2_scan_points.jsonl"
            self.assertTrue(jsonl.is_file())
            rows = _load_jsonl(jsonl)
            self.assertEqual(len(rows), 2)
            by_id = {str(r.get("plan_point_id")): r for r in rows}
            self.assertEqual(set(by_id.keys()), {"p_fail", "p_ok"})

            fail = by_id["p_fail"]
            self.assertEqual(fail.get("status"), "skipped_drift")
            self.assertEqual(fail.get("drift_precheck_spec"), "z2_5_positive")
            self.assertIs(fail.get("drift_precheck_ok"), False)
            self.assertEqual(fail.get("skip_reason"), "drift_precheck_failed")
            self.assertAlmostEqual(float(fail.get("chi2_total")), CHI2_SENTINEL)
            self.assertIn("drift", fail)
            self.assertIsInstance(fail.get("drift"), dict)

            ok = by_id["p_ok"]
            self.assertEqual(ok.get("status"), "ok")
            self.assertEqual(ok.get("drift_precheck_spec"), "z2_5_positive")
            self.assertIs(ok.get("drift_precheck_ok"), True)
            self.assertNotEqual(float(ok.get("chi2_total")), CHI2_SENTINEL)

    def test_merge_prefers_ok_over_skipped_drift(self) -> None:
        merge_script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        self.assertTrue(merge_script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_a = td_path / "a.jsonl"
            shard_b = td_path / "b.jsonl"
            out = td_path / "merged.jsonl"

            shared_hash = "h_m44_same"
            shard_a.write_text(
                json.dumps(
                    {
                        "params_hash": shared_hash,
                        "status": "skipped_drift",
                        "chi2_total": CHI2_SENTINEL,
                        "model": "lcdm",
                        "plan_point_id": "p0",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            shard_b.write_text(
                json.dumps(
                    {
                        "params_hash": shared_hash,
                        "status": "ok",
                        "chi2_total": 1.2345,
                        "model": "lcdm",
                        "plan_point_id": "p0",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            cmd = [sys.executable, str(merge_script), str(shard_a), str(shard_b), "--out", str(out)]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            merged_rows = _load_jsonl(out)
            self.assertEqual(len(merged_rows), 1)
            self.assertEqual(merged_rows[0].get("status"), "ok")
            self.assertAlmostEqual(float(merged_rows[0].get("chi2_total")), 1.2345)

    def test_reports_ignore_skipped_by_default(self) -> None:
        scan_script = ROOT / "scripts" / "phase2_e2_scan.py"
        pareto_script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        diagnostics_script = ROOT / "scripts" / "phase2_e2_diagnostics_report.py"
        self.assertTrue(scan_script.is_file())
        self.assertTrue(pareto_script.is_file())
        self.assertTrue(diagnostics_script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            out_scan = td_path / "scan_out"
            _write_plan(plan)

            scan_cmd = [
                sys.executable,
                str(scan_script),
                "--model",
                "lcdm",
                "--toy",
                "--plan",
                str(plan),
                "--out-dir",
                str(out_scan),
                "--drift-precheck",
                "z2_5_positive",
            ]
            scan_proc = subprocess.run(scan_cmd, cwd=str(ROOT), text=True, capture_output=True)
            scan_output = (scan_proc.stdout or "") + (scan_proc.stderr or "")
            self.assertEqual(scan_proc.returncode, 0, msg=scan_output)
            jsonl = out_scan / "e2_scan_points.jsonl"

            out_pareto = td_path / "pareto_out"
            pareto_cmd = [
                sys.executable,
                str(pareto_script),
                "--jsonl",
                str(jsonl),
                "--outdir",
                str(out_pareto),
            ]
            pareto_proc = subprocess.run(pareto_cmd, cwd=str(ROOT), text=True, capture_output=True)
            pareto_output = (pareto_proc.stdout or "") + (pareto_proc.stderr or "")
            self.assertEqual(pareto_proc.returncode, 0, msg=pareto_output)
            summary_json = out_pareto / "pareto_summary.json"
            self.assertTrue(summary_json.is_file())
            summary = json.loads(summary_json.read_text(encoding="utf-8"))
            best_overall = summary.get("best_overall")
            self.assertIsInstance(best_overall, dict)
            self.assertLess(float(best_overall.get("chi2_cmb", CHI2_SENTINEL)), 1.0e90)

            out_diag = td_path / "diag_out"
            diag_cmd = [
                sys.executable,
                str(diagnostics_script),
                "--jsonl",
                str(jsonl),
                "--outdir",
                str(out_diag),
            ]
            diag_proc = subprocess.run(diag_cmd, cwd=str(ROOT), text=True, capture_output=True)
            diag_output = (diag_proc.stdout or "") + (diag_proc.stderr or "")
            self.assertEqual(diag_proc.returncode, 0, msg=diag_output)
            best_csv = out_diag / "e2_best_points.csv"
            self.assertTrue(best_csv.is_file())
            with best_csv.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            self.assertGreaterEqual(len(rows), 1)
            for row in rows:
                chi2_raw = row.get("chi2", "NA")
                if chi2_raw in {"", "NA"}:
                    continue
                self.assertLess(float(chi2_raw), 1.0e90)

    def test_plan_coverage_counts_skipped_drift_as_covered(self) -> None:
        scan_script = ROOT / "scripts" / "phase2_e2_scan.py"
        coverage_script = ROOT / "scripts" / "phase2_e2_plan_coverage.py"
        self.assertTrue(scan_script.is_file())
        self.assertTrue(coverage_script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            out_scan = td_path / "scan_out"
            _write_plan(plan)

            scan_cmd = [
                sys.executable,
                str(scan_script),
                "--model",
                "lcdm",
                "--toy",
                "--plan",
                str(plan),
                "--out-dir",
                str(out_scan),
                "--drift-precheck",
                "z2_5_positive",
            ]
            scan_proc = subprocess.run(scan_cmd, cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(scan_proc.returncode, 0, msg=(scan_proc.stdout or "") + (scan_proc.stderr or ""))
            jsonl = out_scan / "e2_scan_points.jsonl"

            cov_cmd = [
                sys.executable,
                str(coverage_script),
                "--plan",
                str(plan),
                "--jsonl",
                str(jsonl),
                "--strict",
            ]
            cov_proc = subprocess.run(cov_cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (cov_proc.stdout or "") + (cov_proc.stderr or "")
            self.assertEqual(cov_proc.returncode, 0, msg=output)
            payload = json.loads((cov_proc.stdout or "").strip())
            counts = payload.get("counts", {})
            self.assertEqual(int(counts.get("n_missing", -1)), 0)
            self.assertEqual(int(counts.get("n_failed", -1)), 0)


if __name__ == "__main__":
    unittest.main()
