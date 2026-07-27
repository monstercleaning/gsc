"""Shared test helper: consciously-retired v11-era artifacts (v12.6).

Several tests in this suite guard editorial invariants of artifacts that the
v12 layout deliberately retired (the v10.1 monolithic paper, the outreach
pack, the paper-2 bundle). Those tests must not fail forever against targets
that are absent BY DESIGN — but they also must not go silently blind: if the
target is absent and the retirement is NOT declared, the calling test still
fails. The declarations live in `scripts/docs_claims_lint.RETIRED_V11_REL_FILES`
plus the retired trees below, so a test can only be skipped by an absence
that is simultaneously documented. See CHANGELOG (v12.6).

Usage in a test method:

    reason = retired_artifact_skip_reason(ROOT, "GSC_Framework_v10_1_FINAL.tex")
    if reason:
        self.skipTest(reason)
"""

from pathlib import Path
import sys

# Whole trees retired from the v12 layout (superseded by the five-paper
# strategy and the deposit-platform submission flow).
RETIRED_TREES = (
    "outreach/",
    "papers/paper2_measurement_model_epsilon/",
)


def _retired_rel_files(root: Path):
    scripts = str(root / "scripts")
    added = False
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
        added = True
    try:
        import docs_claims_lint  # noqa: E402
        return tuple(getattr(docs_claims_lint, "RETIRED_V11_REL_FILES", ()))
    finally:
        if added:
            sys.path.remove(scripts)


def retired_artifact_skip_reason(root: Path, rel: str):
    """Return a skip reason iff `rel` is absent AND declared retired.

    Present target  -> None (run the test for real).
    Absent+declared -> reason string (skip with documentation pointer).
    Absent+UNdeclared -> AssertionError (an undeclared disappearance is a
    failure, not a skip — the guard must not rot into a blind spot).
    """
    if (root / rel).exists():
        return None
    declared = rel in _retired_rel_files(root) or any(
        rel.startswith(tree) for tree in RETIRED_TREES
    )
    if not declared:
        raise AssertionError(
            f"{rel} is absent but not declared retired "
            "(scripts/docs_claims_lint.RETIRED_V11_REL_FILES / "
            "tests/_v12_layout.RETIRED_TREES) — an undeclared disappearance "
            "must fail, not skip."
        )
    return (
        f"target artifact '{rel}' was consciously retired from the v12 layout "
        "(declared in RETIRED_V11_REL_FILES/RETIRED_TREES; see CHANGELOG "
        "v12.6). The v11 tree still runs this guard against the real file."
    )
