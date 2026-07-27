"""Phase-4 M152 — legacy v10* filenames must stay bounded to a conscious allowlist.

Repo-hygiene guard: any path with a "v10"-containing component must be on the
allowlist below, so legacy-versioned material can only enter the tree as a
deliberate decision.

v12.6 rewrite (kept byte-identical in v11.0.0/tests/ and v12.0.0/tests/):

* The original computed ROOT as ``parents[2]`` — correct only in the nested
  working-repo layout; in the public root-layout repo (or an unzipped
  deposit) that escapes ABOVE the repository and scans unrelated files.
  The scan root is now detected: nearest ancestor holding ``.git``, else the
  package root (marker: ``GSC_Framework.md``), else the historic fallback.
* Allowlist entries are package-relative: a leading version-directory
  component (``v11.0.0/``, ``v12.0.0/``, ...) is stripped before matching, so
  one list serves every layout and every package generation.
* The v12 package's legitimate v10-era carriers were added (its
  ``scripts/reproduce_v10_1_*`` reproduction scripts were already covered by
  the shared prefix; ``archive/v10*`` banner stubs are new): through v12.5
  they made this guard fail on every push — red since the v12 layout landed,
  unnoticed because a legacy suite's red X had become background noise.
"""

from pathlib import Path
import re
import subprocess
import unittest


def _detect_scan_root() -> Path:
    here = Path(__file__).resolve()
    package_root = None
    for cand in here.parents:
        if (cand / "GSC_Framework.md").is_file() and package_root is None:
            package_root = cand
        if (cand / ".git").exists():
            return cand
    if package_root is not None:
        return package_root
    return here.parents[2]


ROOT = _detect_scan_root()

_VERSION_DIR = re.compile(r"^v\d+\.\d+\.\d+/")

# Package-relative allowed prefixes (leading version dir already stripped).
ALLOWED_PREFIXES = (
    "GSC_v10_1_release/",
    "GSC_v10_1_simulations/",
    "scripts/reproduce_v10_1_",
    "GSC_Framework_v10",              # root wrappers + v11's _v10_1_FINAL.{md,tex}
    "archive/legacy/",
    "archive/v10",                    # v12 banner-stub pointers (v12.6)
    "B/GSC_Phase10_MochiClass_Integration_v10_8.pdf",
)

# Never scan VCS/venv/build-artifact directories (graphify-out is a local
# knowledge-graph build dir that may mirror arbitrary filenames).
SKIP_PARTS = {".git", "__pycache__", ".venv", "graphify-out", "node_modules"}


def _contains_v10_component(rel_posix: str) -> bool:
    parts = rel_posix.lower().split("/")
    return any("v10" in part for part in parts)


def _iter_rel_files(root: Path):
    """Files under the guard's jurisdiction, as posix paths relative to root.

    In a git repository this is exactly the tracked set (what a CI checkout
    contains) — untracked local material such as an operator's scratch
    directories is not the repo's to police. Outside git (unzipped deposit),
    every file present is deposit content: fall back to a filesystem walk.
    """
    if (root / ".git").exists():
        try:
            out = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z"],
                capture_output=True, check=True,
            ).stdout
            return sorted(p.decode("utf-8") for p in out.split(b"\0") if p)
        except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
            pass
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )


class TestPhase4M152LegacyVersionedFilenamesBounded(unittest.TestCase):
    def test_v10_paths_are_bounded_to_allowlist(self) -> None:
        offenders = []
        for rel in _iter_rel_files(ROOT):
            if any(part in SKIP_PARTS for part in rel.split("/")):
                continue
            if not _contains_v10_component(rel):
                continue
            normalized = _VERSION_DIR.sub("", rel)
            if not any(normalized.startswith(prefix) for prefix in ALLOWED_PREFIXES):
                offenders.append(rel)
        self.assertEqual([], offenders, msg="unexpected v10* paths:\n" + "\n".join(offenders))

    def test_root_legacy_wrappers_have_historical_do_not_submit_banner(self) -> None:
        wrappers = sorted(ROOT.glob("GSC_Framework_v10*.md"))
        for wrapper in wrappers:
            with wrapper.open("r", encoding="utf-8") as fh:
                first_30 = "".join([next(fh, "") for _ in range(30)]).lower()
            self.assertIn("historical", first_30, msg=f"missing HISTORICAL banner in {wrapper}")
            self.assertIn(
                "do not submit",
                first_30,
                msg=f"missing DO NOT SUBMIT banner in {wrapper}",
            )


if __name__ == "__main__":
    unittest.main()
