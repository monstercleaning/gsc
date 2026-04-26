import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402


class TestPhase2M17E2ScanQuasiRandomSamplers(unittest.TestCase):
    def _write_priors(self, path: Path) -> None:
        pred = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        lines = ["name,value,sigma"]
        lines.append(f"100theta_star,{100.0 * float(pred['theta_star']):.16g},1e-3")
        lines.append(f"R,{float(pred['R']):.16g},1e-3")
        lines.append(f"lA,{float(pred['lA']):.16g},1e-2")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _run_scan(self, *, sampler: str, priors_csv: Path, out_dir: Path) -> subprocess.CompletedProcess[str]:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--sampler",
            sampler,
            "--n-samples",
            "4",
            "--seed",
            "123",
            "--grid",
            "H0=67.0:67.8",
            "--grid",
            "Omega_m=0.30:0.33",
            "--cmb",
            str(priors_csv),
            "--omega-b-h2",
            "0.02237",
            "--omega-c-h2",
            "0.1200",
            "--Neff",
            "3.046",
            "--Tcmb-K",
            "2.7255",
            "--out-dir",
            str(out_dir),
        ]
        if sampler == "halton":
            cmd.extend(["--halton-skip", "2", "--halton-scramble"])
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_halton_and_lhs_smoke_emit_sampler_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            priors_csv = td_path / "cmb.csv"
            self._write_priors(priors_csv)

            for sampler in ("halton", "lhs"):
                out_dir = td_path / f"out_{sampler}"
                proc = self._run_scan(sampler=sampler, priors_csv=priors_csv, out_dir=out_dir)
                output = (proc.stdout or "") + (proc.stderr or "")
                self.assertEqual(proc.returncode, 0, msg=f"{sampler}: {output}")

                jsonl_path = out_dir / "e2_scan_points.jsonl"
                self.assertTrue(jsonl_path.is_file())
                lines = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertEqual(len(lines), 4)

                for idx, row in enumerate(lines):
                    sampler_meta = row.get("sampler") or {}
                    self.assertEqual(sampler_meta.get("kind"), sampler)
                    self.assertEqual(int(sampler_meta.get("seed", -1)), 123)
                    self.assertEqual(int(sampler_meta.get("index", -1)), idx)
                    self.assertGreaterEqual(int(sampler_meta.get("dim", 0)), 2)


if __name__ == "__main__":
    unittest.main()
