import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_rg_pade_fit_report.py"


def _synthetic_flow_csv(g_ir: float, k_star: float, ks: list[float]) -> str:
    lines = ["# synthetic RG flow table", "k,g"]
    for k in ks:
        g = g_ir / (1.0 - (k / k_star) ** 2)
        lines.append(f"{k:.12g},{g:.12g}")
    return "\n".join(lines) + "\n"


class TestPhase2M93RGPadeFitReportSynthetic(unittest.TestCase):
    def test_synthetic_fit_recovers_parameters_and_emits_snippets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            csv_path = tmp / "flow.csv"
            csv_path.write_text(
                _synthetic_flow_csv(
                    g_ir=2.0,
                    k_star=3.0,
                    ks=[0.1, 0.3, 0.7, 1.1, 1.5, 2.0],
                ),
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(csv_path),
                "--format",
                "json",
            ]
            run = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            out = (run.stdout or "") + (run.stderr or "")
            self.assertEqual(run.returncode, 0, msg=out)

            payload = json.loads(run.stdout)
            self.assertEqual(payload.get("tool"), "phase2_rg_pade_fit_report_v1")
            self.assertEqual((payload.get("summary") or {}).get("n_fit_ok"), 1)

            file_fit = (payload.get("files") or [])[0]
            self.assertTrue(bool(file_fit.get("fit_ok")))

            g_ir_fit = float(file_fit.get("G_ir"))
            k_star_fit = float(file_fit.get("k_star"))
            self.assertLess(abs((g_ir_fit - 2.0) / 2.0), 1e-6)
            self.assertLess(abs((k_star_fit - 3.0) / 3.0), 1e-6)

            snip_dir = tmp / "snippets"
            run_snip = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(csv_path),
                    "--format",
                    "json",
                    "--emit-snippets",
                    str(snip_dir),
                ],
                text=True,
                capture_output=True,
                cwd=str(tmp),
            )
            snip_out = (run_snip.stdout or "") + (run_snip.stderr or "")
            self.assertEqual(run_snip.returncode, 0, msg=snip_out)

            tex_path = snip_dir / "phase2_rg_pade_fit.tex"
            md_path = snip_dir / "phase2_rg_pade_fit.md"
            self.assertTrue(tex_path.exists())
            self.assertTrue(md_path.exists())
            self.assertIn("phase2_rg_pade_fit_snippet_v1", tex_path.read_text(encoding="utf-8"))
            self.assertIn("phase2_rg_pade_fit_snippet_v1", md_path.read_text(encoding="utf-8"))

    def test_constant_g_is_fit_impossible_and_returns_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            csv_path = tmp / "flat.csv"
            csv_path.write_text("k,g\n0.1,1.0\n0.5,1.0\n1.0,1.0\n", encoding="utf-8")

            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(csv_path),
                    "--format",
                    "json",
                ],
                text=True,
                capture_output=True,
                cwd=str(tmp),
            )
            out = (run.stdout or "") + (run.stderr or "")
            self.assertEqual(run.returncode, 2, msg=out)

            payload = json.loads(run.stdout)
            summary = payload.get("summary") or {}
            self.assertEqual(summary.get("n_fit_ok"), 0)
            self.assertEqual(summary.get("n_fit_fail"), 1)
            file_fit = (payload.get("files") or [])[0]
            self.assertFalse(bool(file_fit.get("fit_ok")))
            self.assertEqual(file_fit.get("fit_reason"), "non_negative_slope")


if __name__ == "__main__":
    unittest.main()
