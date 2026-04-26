import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
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


def _build_toy_review_repo(tmp: Path) -> Path:
    repo = tmp / "toy_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "ci@example.com")
    _git(repo, "config", "user.name", "CI")

    _write(repo / "README.md", "toy review repo\n")
    _write(repo / "v11.0.0/canonical_artifacts.json", '{"schema":"toy"}\n')
    _write(
        repo / "v11.0.0/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv",
        "z,mu\n0.1,1.0\n",
    )
    _write(
        repo / "v11.0.0/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv",
        "name,value\ntoy,1.0\n",
    )
    _write(
        repo / "v11.0.0/data/structure/fsigma8_gold2017_plus_zhao2018.csv",
        "z,fsigma8\n0.1,0.4\n",
    )
    _write(repo / "v11.0.0/gsc/__init__.py", "__all__ = []\n")
    _write(repo / "v11.0.0/results/out.txt", "derived\n")
    _write(repo / "v11.0.0/paper_assets/run/table.txt", "derived\n")
    _write(repo / "v11.0.0/artifacts/state.txt", "derived\n")
    _write(repo / "v11.0.0/archive/old.txt", "legacy\n")
    _write(repo / "v11.0.0/B/legacy.txt", "legacy\n")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed", "-q")
    return repo


class TestPhase2M116MakeRepoSnapshotReviewWithDataProfile(unittest.TestCase):
    def _run(self, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            cwd=str(cwd),
            text=True,
            capture_output=True,
        )

    def test_profile_includes_required_data_and_excludes_derived_paths(self) -> None:
        proc = self._run(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--profile",
                "review_with_data",
                "--dry-run",
                "--format",
                "json",
            ],
            cwd=ROOT,
        )
        msg = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=msg)

        payload = json.loads(proc.stdout)
        self.assertEqual(payload.get("profile"), "review_with_data")
        paths = {
            str(row.get("path"))
            for row in payload.get("files", [])
            if isinstance(row, dict) and row.get("path")
        }
        required_paths = {
            "v11.0.0/canonical_artifacts.json",
            "v11.0.0/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv",
            "v11.0.0/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv",
            "v11.0.0/data/structure/fsigma8_gold2017_plus_zhao2018.csv",
        }
        for rel in required_paths:
            self.assertIn(rel, paths, msg=f"missing required review-with-data path: {rel}")

        excluded_prefixes = (
            "v11.0.0/results/",
            "v11.0.0/paper_assets",
            "v11.0.0/artifacts/",
            "v11.0.0/archive/",
            "v11.0.0/B/",
        )
        for rel in paths:
            for prefix in excluded_prefixes:
                self.assertFalse(rel.startswith(prefix), msg=rel)

    def test_zip_determinism_and_manifest_portability(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _build_toy_review_repo(tmp)
            out_a = tmp / "review_a.zip"
            out_b = tmp / "review_b.zip"

            p1 = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--ref",
                    "HEAD",
                    "--profile",
                    "review_with_data",
                    "--zip-out",
                    str(out_a),
                ],
                cwd=ROOT,
            )
            self.assertEqual(p1.returncode, 0, msg=(p1.stdout or "") + (p1.stderr or ""))
            p2 = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--ref",
                    "HEAD",
                    "--profile",
                    "review_with_data",
                    "--zip-out",
                    str(out_b),
                ],
                cwd=ROOT,
            )
            self.assertEqual(p2.returncode, 0, msg=(p2.stdout or "") + (p2.stderr or ""))

            self.assertEqual(_sha256_path(out_a), _sha256_path(out_b))

            with zipfile.ZipFile(out_a, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("GSC/v11.0.0/canonical_artifacts.json", names)
                self.assertIn(
                    "GSC/v11.0.0/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv",
                    names,
                )
                self.assertIn("GSC/v11.0.0/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv", names)
                self.assertIn("GSC/v11.0.0/data/structure/fsigma8_gold2017_plus_zhao2018.csv", names)
                self.assertNotIn("GSC/v11.0.0/results/out.txt", names)
                self.assertNotIn("GSC/v11.0.0/paper_assets/run/table.txt", names)
                self.assertNotIn("GSC/v11.0.0/artifacts/state.txt", names)
                self.assertNotIn("GSC/v11.0.0/archive/old.txt", names)
                self.assertNotIn("GSC/v11.0.0/B/legacy.txt", names)

                manifest_text = zf.read("GSC/repo_snapshot_manifest.json").decode("utf-8")
                payload = json.loads(manifest_text)
                self.assertEqual(payload.get("repo_root"), ".")
                self.assertNotIn("repo_root_abs", payload)
                self.assertNotIn(str(repo.resolve()), manifest_text)
                for forbidden in ("/Users/", "/home/", "/var/folders/", "C:\\Users\\"):
                    self.assertNotIn(forbidden, manifest_text)

            out_abs = tmp / "review_abs.zip"
            p_abs = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--ref",
                    "HEAD",
                    "--profile",
                    "review_with_data",
                    "--include-absolute-paths",
                    "--zip-out",
                    str(out_abs),
                ],
                cwd=ROOT,
            )
            self.assertEqual(p_abs.returncode, 0, msg=(p_abs.stdout or "") + (p_abs.stderr or ""))
            with zipfile.ZipFile(out_abs, "r") as zf:
                payload = json.loads(zf.read("GSC/repo_snapshot_manifest.json").decode("utf-8"))
                self.assertEqual(payload.get("repo_root"), ".")
                repo_root_abs = str(payload.get("repo_root_abs"))
                self.assertTrue(repo_root_abs)
                self.assertTrue(Path(repo_root_abs).is_absolute())


if __name__ == "__main__":
    unittest.main()
