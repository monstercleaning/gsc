import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402


class TestManifestRepoRelativePaths(unittest.TestCase):
    def test_manifest_normalizes_repo_paths_and_records_rs_star_calibration(self):
        script = ROOT / "scripts/late_time_make_manifest.py"
        self.assertTrue(script.exists())

        bao = ROOT / "data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv"
        cmb = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        cmb_cov = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
        self.assertTrue(bao.exists())
        self.assertTrue(cmb.exists())
        self.assertTrue(cmb_cov.exists())

        with tempfile.TemporaryDirectory() as td:
            fit_dir = Path(td)
            fit_json = fit_dir / "lcdm_bestfit.json"
            out_manifest = fit_dir / "manifest.json"

            fit_json.write_text(
                json.dumps(
                    {
                        "model": "lcdm",
                        "datasets": {
                            "bao": str(bao.resolve()),
                            "cmb": str(cmb.resolve()),
                            "cmb_cov": str(cmb_cov.resolve()),
                        },
                        "cmb": {
                            "path": str(cmb.resolve()),
                            "cov_path": str(cmb_cov.resolve()),
                            "mode": "distance_priors",
                            "bridge_z": None,
                        },
                        "early_time": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            subprocess.check_call(
                [
                    sys.executable,
                    str(script),
                    "--fit-dir",
                    str(fit_dir),
                    "--out",
                    str(out_manifest),
                ]
            )

            obj = json.loads(out_manifest.read_text(encoding="utf-8"))

            # Python executable path should be repo-relative when possible.
            expected_py_rel = None
            py = Path(sys.executable).absolute()
            try:
                expected_py_rel = str(py.relative_to(REPO_ROOT))
            except Exception:
                expected_py_rel = None
            if expected_py_rel is None:
                prefix = Path(getattr(sys, "prefix", "")).absolute()
                for name in ("python", "python3", f"python{sys.version_info.major}", f"python{sys.version_info.major}.{sys.version_info.minor}"):
                    cand = prefix / "bin" / name
                    if not cand.exists():
                        continue
                    try:
                        expected_py_rel = str(cand.relative_to(REPO_ROOT))
                        break
                    except Exception:
                        continue

            if expected_py_rel is not None:
                self.assertEqual(obj["python"], expected_py_rel)
                self.assertFalse(Path(obj["python"]).is_absolute())

            # Repo-relative dataset paths (no absolute repo paths).
            ds = obj["datasets_by_model"]["lcdm"]
            self.assertEqual(ds["bao"], str(bao.relative_to(REPO_ROOT)))
            self.assertEqual(ds["cmb"], str(cmb.relative_to(REPO_ROOT)))
            self.assertEqual(ds["cmb_cov"], str(cmb_cov.relative_to(REPO_ROOT)))

            cmb_cfg = obj["cmb_by_model"]["lcdm"]
            self.assertEqual(cmb_cfg["path"], str(cmb.relative_to(REPO_ROOT)))
            self.assertEqual(cmb_cfg["cov_path"], str(cmb_cov.relative_to(REPO_ROOT)))

            # Calibration provenance is recorded for CHW2018 distance-priors.
            self.assertTrue(bool(cmb_cfg.get("rs_star_calibration_applied")))
            self.assertAlmostEqual(
                float(cmb_cfg.get("rs_star_calibration")),
                float(_RS_STAR_CALIB_CHW2018),
                places=14,
            )

            # Hash keys must be repo-relative (the manifest is meant to be portable).
            for k in obj["inputs_sha256"].keys():
                self.assertFalse(Path(k).is_absolute(), msg=f"unexpected absolute key: {k}")


if __name__ == "__main__":
    unittest.main()
