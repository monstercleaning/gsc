import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _sha256_bytes(payload: bytes) -> str:
    h = hashlib.sha256()
    h.update(payload)
    return h.hexdigest()


def _write_catalog(path: Path, *, asset_name: str, sha: str) -> None:
    obj = {
        "schema_version": 2,
        "artifacts": {
            "late_time": {
                "type": "late-time",
                "tier": "frozen",
                "tag": "vL",
                "release_url": "https://github.com/org/repo/releases/tag/vL",
                "asset": asset_name,
                "sha256": sha,
            },
            "submission": {
                "type": "submission",
                "tier": "frozen",
                "tag": "vS",
                "release_url": "https://github.com/org/repo/releases/tag/vS",
                "asset": asset_name,
                "sha256": sha,
            },
            "referee_pack": {
                "type": "referee",
                "tier": "recommended",
                "tag": "vR",
                "release_url": "https://github.com/org/repo/releases/tag/vR",
                "asset": asset_name,
                "sha256": sha,
            },
            "toe_bundle": {
                "type": "toe",
                "tier": "recommended",
                "tag": "vT",
                "release_url": "https://github.com/org/repo/releases/tag/vT",
                "asset": asset_name,
                "sha256": sha,
            },
        },
    }
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


class TestFetchCanonicalArtifacts(unittest.TestCase):
    def test_construct_download_url(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        got = m.construct_download_url(
            "https://github.com/morfikus/GSC/releases/tag/v10.1.1-submission-r2",
            "v10.1.1-submission-r2",
            "submission_bundle_v10.1.1-late-time-r4.zip",
        )
        self.assertEqual(
            got,
            "https://github.com/morfikus/GSC/releases/download/v10.1.1-submission-r2/"
            "submission_bundle_v10.1.1-late-time-r4.zip",
        )

    def test_dry_run_fetch_missing_does_not_call_network(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            catalog = td / "catalog.json"
            _write_catalog(catalog, asset_name="missing.zip", sha=("a" * 64))

            with mock.patch.object(m.urllib.request, "urlopen", side_effect=AssertionError("network called")):
                rc = m.main(
                    [
                        "--catalog",
                        str(catalog),
                        "--artifacts-dir",
                        str(td),
                        "--fetch-missing",
                        "--dry-run",
                    ]
                )
            self.assertEqual(rc, 0)

    def test_missing_without_fetch_prints_hint_and_fails(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            catalog = td / "catalog.json"
            _write_catalog(catalog, asset_name="missing.zip", sha=("b" * 64))

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = m.main(["--catalog", str(catalog), "--artifacts-dir", str(td)])
            text = out.getvalue()
            self.assertEqual(rc, 2)
            self.assertIn("Missing canonical artifacts", text)
            self.assertIn("fetch_canonical_artifacts.sh", text)
            self.assertIn("download_url:", text)

    def test_existing_file_sha_mismatch_fails(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "asset.zip"
            asset.write_bytes(b"wrong")
            catalog = td / "catalog.json"
            _write_catalog(catalog, asset_name=asset.name, sha=_sha256_bytes(b"expected"))

            rc = m.main(["--catalog", str(catalog), "--artifacts-dir", str(td)])
            self.assertEqual(rc, 2)

    def test_resolve_auth_token_prefers_env(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "abc123"}, clear=False):
            self.assertEqual(m._resolve_auth_token(), "abc123")

    def test_download_to_temp_sets_auth_header(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        payload = b"hello"

        class DummyResponse:
            def __init__(self):
                self._used = False

            def read(self, _n: int):
                if self._used:
                    return b""
                self._used = True
                return payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        captured = {"auth": None, "ua": None}

        def fake_urlopen(req, timeout=0):
            captured["auth"] = req.headers.get("Authorization")
            captured["ua"] = req.headers.get("User-agent")
            return DummyResponse()

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            with mock.patch.object(m.urllib.request, "urlopen", side_effect=fake_urlopen):
                temp_path = m._download_to_temp(
                    "https://example.invalid/asset.zip",
                    td,
                    10.0,
                    auth_token="tok123",
                )
            self.assertTrue(temp_path.is_file())
            self.assertEqual(temp_path.read_bytes(), payload)
            self.assertEqual(captured["auth"], "Bearer tok123")
            self.assertIsNotNone(captured["ua"])

    def test_download_via_gh_release_success(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            resolved = td / "asset.zip"
            rec = {
                "tag": "vX",
                "asset": "asset.zip",
                "sha256": "0" * 64,
                "release_url": "https://github.com/org/repo/releases/tag/vX",
            }

            def fake_run(_cmd, capture_output=True, text=True):
                resolved.write_bytes(b"x")
                return subprocess.CompletedProcess(_cmd, 0, stdout="", stderr="")

            with mock.patch.object(m.subprocess, "run", side_effect=fake_run):
                ok, reason = m._download_via_gh_release(key="late_time", rec=rec, resolved=resolved)
            self.assertTrue(ok)
            self.assertEqual(reason, "")
            self.assertTrue(resolved.is_file())

    def test_download_via_gh_release_reports_auth_failure(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            resolved = td / "asset.zip"
            rec = {
                "tag": "vX",
                "asset": "asset.zip",
                "sha256": "0" * 64,
                "release_url": "https://github.com/org/repo/releases/tag/vX",
            }

            def fake_run(_cmd, capture_output=True, text=True):
                return subprocess.CompletedProcess(
                    _cmd,
                    1,
                    stdout="",
                    stderr="To get started with GitHub CLI, please run: gh auth login",
                )

            with mock.patch.object(m.subprocess, "run", side_effect=fake_run):
                ok, reason = m._download_via_gh_release(key="late_time", rec=rec, resolved=resolved)
            self.assertFalse(ok)
            self.assertIn("gh auth login", reason)

    def test_manual_download_help_prints_curl_and_verify_commands(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        rec = {
            "tag": "vX",
            "asset": "asset.zip",
            "sha256": "1" * 64,
            "release_url": "https://github.com/org/repo/releases/tag/vX",
        }
        resolved = Path("/tmp/asset.zip")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            m._print_manual_download_help(
                key="late_time",
                rec=rec,
                resolved=resolved,
                url="https://github.com/org/repo/releases/download/vX/asset.zip",
            )
        text = out.getvalue()
        self.assertIn("curl_download_cmd:", text)
        self.assertIn("verify_cmd:", text)

    def test_direct_download_retries_then_succeeds(self):
        import fetch_canonical_artifacts as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            temp = td / "tmp.bin"
            calls = {"n": 0}

            def fake_download(url, artifacts_dir, timeout_sec, auth_token=None):  # noqa: ARG001
                calls["n"] += 1
                if calls["n"] == 1:
                    raise m.urllib.error.HTTPError(url, 503, "unavailable", hdrs=None, fp=None)
                temp.write_bytes(b"ok")
                return temp

            with mock.patch.object(m, "_download_to_temp", side_effect=fake_download):
                with mock.patch.object(m.time, "sleep", return_value=None):
                    out = m._download_direct_with_retries(
                        key="late_time",
                        url="https://example.invalid/a.zip",
                        artifacts_dir=td,
                        timeout_sec=5.0,
                        retries=2,
                        retry_backoff_sec=0.01,
                        auth_token=None,
                    )
            self.assertEqual(out, temp)
            self.assertEqual(calls["n"], 2)


if __name__ == "__main__":
    unittest.main()
