import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make_repo_snapshot.py"


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_toy_repo(tmp: Path) -> Path:
    repo = tmp / "toy_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "ci@example.com")
    _git(repo, "config", "user.name", "CI")

    _write(repo / "README.md", "toy repo\n")
    _write(repo / ".gitignore", ".venv/\n__MACOSX/\n.claude/\nv11.0.0/results/\n")
    _write(repo / "v11.0.0/gsc/foo.py", "print('ok')\n")
    _write(repo / "v11.0.0/docs/x.md", "doc\n")
    _write(repo / "v11.0.0/B/legacy.txt", "legacy\n")
    _write(repo / "v11.0.0/archive/old.txt", "old\n")

    _git(repo, "add", "README.md", ".gitignore", "v11.0.0/gsc/foo.py", "v11.0.0/docs/x.md", "v11.0.0/B/legacy.txt", "v11.0.0/archive/old.txt")
    _git(repo, "commit", "-m", "initial", "-q")

    _write(repo / ".venv/lib/big.bin", "not tracked\n")
    _write(repo / "__MACOSX/._junk", "junk\n")
    _write(repo / ".claude/config.json", "{}\n")
    _write(repo / "v11.0.0/results/out.txt", "artifact\n")
    return repo


class TestPhase2M74MakeRepoSnapshot(unittest.TestCase):
    def _run(self, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT)] + args
        return subprocess.run(cmd, text=True, capture_output=True, cwd=str(cwd))

    def test_full_and_lean_profiles_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _build_toy_repo(tmp)

            full_zip = tmp / "full.zip"
            full = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--ref",
                    "HEAD",
                    "--profile",
                    "full",
                    "--out",
                    str(full_zip),
                    "--format",
                    "json",
                ],
                cwd=ROOT,
            )
            msg_full = (full.stdout or "") + (full.stderr or "")
            self.assertEqual(full.returncode, 0, msg=msg_full)
            self.assertTrue(full_zip.is_file())

            with zipfile.ZipFile(full_zip, "r") as zf:
                names = sorted(zf.namelist())
                self.assertIn("GSC/README.md", names)
                self.assertIn("GSC/v11.0.0/B/legacy.txt", names)
                self.assertIn("GSC/v11.0.0/archive/old.txt", names)
                self.assertIn("GSC/repo_snapshot_manifest.json", names)
                self.assertNotIn("GSC/.venv/lib/big.bin", names)
                self.assertNotIn("GSC/__MACOSX/._junk", names)
                self.assertNotIn("GSC/.claude/config.json", names)
                self.assertNotIn("GSC/v11.0.0/results/out.txt", names)

                manifest = json.loads(zf.read("GSC/repo_snapshot_manifest.json").decode("utf-8"))
                self.assertEqual(manifest.get("schema"), "gsc_repo_snapshot_manifest_v1")
                git_meta = manifest.get("git") or {}
                self.assertEqual(git_meta.get("sha"), _git(repo, "rev-parse", "HEAD"))

                by_path = {str(row.get("path")): row for row in manifest.get("files", [])}
                self.assertIn("README.md", by_path)
                readme_sha = hashlib.sha256(zf.read("GSC/README.md")).hexdigest()
                self.assertEqual(by_path["README.md"].get("sha256"), readme_sha)

            lean_zip = tmp / "lean.zip"
            lean = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--ref",
                    "HEAD",
                    "--profile",
                    "lean",
                    "--out",
                    str(lean_zip),
                    "--format",
                    "json",
                ],
                cwd=ROOT,
            )
            msg_lean = (lean.stdout or "") + (lean.stderr or "")
            self.assertEqual(lean.returncode, 0, msg=msg_lean)
            self.assertTrue(lean_zip.is_file())

            with zipfile.ZipFile(lean_zip, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("GSC/README.md", names)
                self.assertIn("GSC/v11.0.0/gsc/foo.py", names)
                self.assertIn("GSC/v11.0.0/docs/x.md", names)
                self.assertNotIn("GSC/v11.0.0/B/legacy.txt", names)
                self.assertNotIn("GSC/v11.0.0/archive/old.txt", names)

    def test_deterministic_zip_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _build_toy_repo(tmp)

            out1 = tmp / "snap1.zip"
            out2 = tmp / "snap2.zip"

            p1 = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--profile",
                    "lean",
                    "--ref",
                    "HEAD",
                    "--out",
                    str(out1),
                ],
                cwd=ROOT,
            )
            self.assertEqual(p1.returncode, 0, msg=(p1.stdout or "") + (p1.stderr or ""))

            p2 = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--profile",
                    "lean",
                    "--ref",
                    "HEAD",
                    "--out",
                    str(out2),
                ],
                cwd=ROOT,
            )
            self.assertEqual(p2.returncode, 0, msg=(p2.stdout or "") + (p2.stderr or ""))

            self.assertEqual(_sha256_path(out1), _sha256_path(out2))

    def test_slim_dry_run_manifest_and_determinism_on_repo(self) -> None:
        repo_root = ROOT.parent
        args = [
            "--repo-root",
            str(repo_root),
            "--profile",
            "slim",
            "--dry-run",
            "--format",
            "json",
        ]
        p1 = self._run(args, cwd=ROOT)
        p2 = self._run(args, cwd=ROOT)

        out1 = (p1.stdout or "") + (p1.stderr or "")
        out2 = (p2.stdout or "") + (p2.stderr or "")
        self.assertEqual(p1.returncode, 0, msg=out1)
        self.assertEqual(p2.returncode, 0, msg=out2)

        self.assertEqual(p1.stdout, p2.stdout)
        payload = json.loads(p1.stdout)
        self.assertEqual(payload.get("schema"), "gsc_repo_snapshot_manifest_v1")

        paths = [str(row.get("path")) for row in payload.get("files", []) if isinstance(row, dict)]
        self.assertTrue(paths)
        self.assertIn("README.md", paths)
        self.assertIn("v11.0.0/scripts/phase2_e2_scan.py", paths)
        self.assertIn("v11.0.0/gsc/__init__.py", paths)

        forbidden_prefixes = (".git/", "v11.0.0/B/", "v11.0.0/archive/")
        for path in paths:
            for prefix in forbidden_prefixes:
                self.assertFalse(path.startswith(prefix), msg=path)
        self.assertNotIn("GSC_v8.2_COMPLETE.zip", paths)
        self.assertNotIn("GSC_v10_sims.zip", paths)
        self.assertNotIn("v11.0.0/GSC_v10_1_release.zip", paths)
        self.assertNotIn("v11.0.0/GSC_v10_1_simulations.zip", paths)

    def test_zip_out_alias_works_and_rejects_non_zip_formats(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _build_toy_repo(tmp)
            zip_out = tmp / "alias.zip"

            ok_proc = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--profile",
                    "lean",
                    "--ref",
                    "HEAD",
                    "--zip-out",
                    str(zip_out),
                ],
                cwd=ROOT,
            )
            self.assertEqual(ok_proc.returncode, 0, msg=(ok_proc.stdout or "") + (ok_proc.stderr or ""))
            self.assertTrue(zip_out.is_file())

            bad_proc = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--profile",
                    "lean",
                    "--ref",
                    "HEAD",
                    "--snapshot-format",
                    "dir",
                    "--zip-out",
                    str(tmp / "bad.zip"),
                ],
                cwd=ROOT,
            )
            self.assertEqual(bad_proc.returncode, 2, msg=(bad_proc.stdout or "") + (bad_proc.stderr or ""))
            self.assertIn("--zip-out requires zip snapshot format", (bad_proc.stderr or "") + (bad_proc.stdout or ""))


if __name__ == "__main__":
    unittest.main()
