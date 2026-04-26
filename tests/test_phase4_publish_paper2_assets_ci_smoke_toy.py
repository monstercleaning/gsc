import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_build_paper2_assets.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase4PublishPaper2AssetsCiSmokeToy(unittest.TestCase):
    def _run_once(self, workdir: Path, outdir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--preset",
                "ci_smoke",
                "--seed",
                "0",
                "--workdir",
                str(workdir),
                "--outdir",
                str(outdir),
                "--format",
                "json",
            ],
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )

    def test_ci_smoke_assets_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            w1 = base / "w1"
            w2 = base / "w2"
            o1 = base / "o1"
            o2 = base / "o2"

            p1 = self._run_once(w1, o1)
            p2 = self._run_once(w2, o2)
            self.assertEqual(p1.returncode, 0, msg=(p1.stdout or "") + (p1.stderr or ""))
            self.assertEqual(p2.returncode, 0, msg=(p2.stdout or "") + (p2.stderr or ""))

            m1 = o1 / "paper2_assets_manifest.json"
            m2 = o2 / "paper2_assets_manifest.json"
            n1 = o1 / "numbers.tex"
            n2 = o2 / "numbers.tex"
            self.assertTrue(m1.is_file())
            self.assertTrue(m2.is_file())
            self.assertTrue(n1.is_file())
            self.assertTrue(n2.is_file())
            self.assertEqual(m1.read_bytes(), m2.read_bytes())
            self.assertEqual(n1.read_bytes(), n2.read_bytes())

            figs1 = sorted((o1 / "figures").glob("*.png"))
            figs2 = sorted((o2 / "figures").glob("*.png"))
            self.assertEqual([p.name for p in figs1], [p.name for p in figs2])
            self.assertGreaterEqual(len(figs1), 2)
            for a, b in zip(figs1, figs2):
                self.assertEqual(_sha256_file(a), _sha256_file(b), msg=f"figure mismatch: {a.name}")

            text = m1.read_text(encoding="utf-8") + n1.read_text(encoding="utf-8")
            for tok in ABS_TOKENS:
                self.assertNotIn(tok, text)


if __name__ == "__main__":
    unittest.main()
