import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_audit_zip_bloat.py"


def _build_zip(path: Path) -> None:
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(".git/objects/pack/pack-abc.pack", b"a" * (1024 * 1024))
        zf.writestr("v11.0.0/.venv/lib/python3.12/site-packages/foo.bin", b"b" * 2048)
        zf.writestr("v11.0.0/data/sn/pantheon_plus_shoes/mock.cov", b"c" * 3072)
        zf.writestr("__MACOSX/._junk", b"d" * 128)
        zf.writestr("README.md", "ok\n")


class TestPhase2M77AuditZipBloat(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )

    def test_json_flags_and_policy_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            zip_path = Path(td) / "toy.zip"
            _build_zip(zip_path)

            args = ["--zip", str(zip_path), "--format", "json", "--top", "5"]
            p1 = self._run(args)
            p2 = self._run(args)

            self.assertEqual(p1.returncode, 0, msg=(p1.stdout or "") + (p1.stderr or ""))
            self.assertEqual(p2.returncode, 0, msg=(p2.stdout or "") + (p2.stderr or ""))
            self.assertEqual(p1.stdout, p2.stdout)

            payload = json.loads(p1.stdout)
            self.assertEqual(payload.get("schema"), "phase2_e2_zip_bloat_report_v1")
            flags = payload.get("flags") or {}
            self.assertTrue(flags.get("has_git"))
            self.assertTrue(flags.get("has_venv"))
            self.assertTrue(flags.get("has_cov_npz"))
            self.assertTrue(flags.get("has_macos_junk"))
            self.assertTrue(flags.get("has_any_bloat"))

            p_git = self._run(["--zip", str(zip_path), "--fail-on", "has_git"])
            self.assertEqual(p_git.returncode, 2, msg=(p_git.stdout or "") + (p_git.stderr or ""))

            p_venv = self._run(["--zip", str(zip_path), "--fail-on", "has_venv"])
            self.assertEqual(p_venv.returncode, 2, msg=(p_venv.stdout or "") + (p_venv.stderr or ""))


if __name__ == "__main__":
    unittest.main()
