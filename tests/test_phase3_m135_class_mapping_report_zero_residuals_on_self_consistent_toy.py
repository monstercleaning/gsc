import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_pt_sigmatensor_class_mapping_report.py"


def _w0wa_values(*, z: float, w0: float, wa: float, omega_m0: float, omega_r0: float) -> tuple[float, float, float]:
    zp1 = 1.0 + float(z)
    frac = float(z) / zp1
    w = float(w0 + wa * frac)
    omega_phi0 = 1.0 - float(omega_m0) - float(omega_r0)
    f_de = float((zp1 ** (3.0 * (1.0 + w0 + wa))) * math.exp(-3.0 * wa * frac))
    e2 = (
        float(omega_r0) * (zp1 ** 4.0)
        + float(omega_m0) * (zp1 ** 3.0)
        + omega_phi0 * f_de
    )
    e = math.sqrt(e2)
    omega_phi = (omega_phi0 * f_de) / e2
    return float(e), float(w), float(omega_phi)


def _make_self_consistent_export_pack(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    omega_m0 = 0.315
    omega_r0 = 9.0e-5
    w0 = -0.95
    wa = 0.2

    zs = [0.0, 0.5, 1.0, 2.0, 5.0]
    lines = ["z,H_over_H0,w_phi,Omega_phi,alpha_K,wa_fit_used"]
    for z in zs:
        e, w, om = _w0wa_values(z=z, w0=w0, wa=wa, omega_m0=omega_m0, omega_r0=omega_r0)
        lines.append(
            ",".join(
                [
                    f"{z:.16e}",
                    f"{e:.16e}",
                    f"{w:.16e}",
                    f"{om:.16e}",
                    f"{0.0:.16e}",
                    f"{wa:.16e}",
                ]
            )
        )
    (path / "SIGMATENSOR_DIAGNOSTIC_GRID.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (path / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini").write_text(
        "\n".join(
            [
                "# toy ini",
                f"w0_fld = {w0:.16e}",
                f"wa_fld = {wa:.16e}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "CANDIDATE_RECORD.json").write_text(
        json.dumps(
            {
                "schema": "phase3_sigmatensor_candidate_record_v1",
                "record": {
                    "Omega_m0": omega_m0,
                    "Omega_r0": omega_r0,
                },
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "EXPORT_SUMMARY.json").write_text(
        json.dumps(
            {
                "schema": "phase3_sigmatensor_class_export_pack_v1",
                "params": {"Omega_m0": omega_m0},
                "derived_today": {"Omega_r0": omega_r0},
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )


class TestPhase3M135ClassMappingReportZeroResidualsOnSelfConsistentToy(unittest.TestCase):
    def test_zero_residuals(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = td_path / "export_pack"
            outdir = td_path / "out"
            _make_self_consistent_export_pack(export_pack)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--export-pack",
                    str(export_pack),
                    "--outdir",
                    str(outdir),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            payload = json.loads((outdir / "CLASS_MAPPING_REPORT.json").read_text(encoding="utf-8"))
            self.assertLessEqual(float(payload["residuals"]["E"]["max_abs_rel"]), 1.0e-12)
            self.assertLessEqual(float(payload["residuals"]["w"]["rms_dw"]), 1.0e-12)
            self.assertLessEqual(float(payload["residuals"]["Omega_phi"]["max_abs"]), 1.0e-12)


if __name__ == "__main__":
    unittest.main()
