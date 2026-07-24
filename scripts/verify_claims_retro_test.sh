#!/usr/bin/env bash
# verify_claims_retro_test.sh — regression guard on the claim DETECTOR's sensitivity.
#
# This test inverts the usual polarity: it requires a FAILURE to succeed.
#
# It runs the current verify_claims.py + CLAIMS.json against the historical
# pre-honesty-pass tree (v12.2, commit RETRO_COMMIT), where the register was
# described as "cryptographically signed" while all ten entries were unsigned
# scaffolds. The tool MUST still report `register-gpg-signed` as UNBACKED there.
#
# Why this exists: the obvious way to defeat a claim verifier is to over-hedge
# its detector — add one more `unless` pattern until the inconvenient finding
# goes quiet. This test makes that attack break CI. Any edit that blinds the
# instrument to a known historical false claim fails here.
#
# Usage:
#   bash scripts/verify_claims_retro_test.sh
#
# Exit codes: 0 = detector still fires (good); 1 = detector went blind (bad);
#             0 with SKIP notice = history unavailable (shallow clone).

set -uo pipefail

RETRO_COMMIT="a42d294"          # v12.2, 2026-04-27, pre-honesty-pass
RETRO_SUBDIR="v12.0.0"
MUST_FAIL_CLAIM="register-gpg-signed"
# Sensitivity floor. Historically 18 assertion sites existed in the v12.2 tree.
# A binary "does the claim still fire?" check is NOT sufficient: a negative-control
# experiment (adding the over-broad hedge `signed`) silenced 17 of 18 sites while
# still technically firing on the 18th. Enforcing a floor blocks mass-blinding
# while leaving room for legitimate, narrow hedge additions.
MIN_SITES=10

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PKG_ROOT}/.." && pwd)"

echo "=== claim-detector retro-test ==="
echo "  historical commit: ${RETRO_COMMIT} (${RETRO_SUBDIR})"
echo "  claim that must still be caught: ${MUST_FAIL_CLAIM}"

if ! git -C "${REPO_ROOT}" cat-file -e "${RETRO_COMMIT}^{commit}" 2>/dev/null; then
  echo "  SKIP: commit ${RETRO_COMMIT} not present (shallow clone?)."
  echo "  To enable this guard in CI use: actions/checkout with fetch-depth: 0"
  exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

if ! git -C "${REPO_ROOT}" archive "${RETRO_COMMIT}:${RETRO_SUBDIR}" | tar -x -C "${WORK}"; then
  echo "  SKIP: could not extract ${RETRO_COMMIT}:${RETRO_SUBDIR}"
  exit 0
fi

OUT="${WORK}/result.json"
python3 "${PKG_ROOT}/scripts/verify_claims.py" \
  --root "${WORK}" \
  --claims "${PKG_ROOT}/CLAIMS.json" \
  --format json > "${OUT}" 2>/dev/null
echo "  tool exit on historical tree: $? (1 expected — findings present)"

python3 - "$OUT" "$MUST_FAIL_CLAIM" "$MIN_SITES" <<'PY'
import json
import sys

path, must_fail, min_sites = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(path, encoding="utf-8") as fh:
    doc = json.load(fh)

unbacked = doc.get("unbacked", [])
by_id = {r["id"]: r for r in doc.get("results", [])}

print("  unbacked on historical tree: %s" % (", ".join(unbacked) or "(none)"))

target = by_id.get(must_fail)
if target is None:
    print("  RESULT: FAIL — claim %r is no longer in the manifest at all." % must_fail)
    print("          The historical false claim can no longer be detected.")
    raise SystemExit(1)

if must_fail not in unbacked:
    print("  RESULT: FAIL — detector went blind.")
    print("          %r evaluated to %s on a tree where it is known false." % (must_fail, target["verdict"]))
    print("          fact: %s" % target["detail"])
    print("          Most likely cause: an `unless` hedge or pattern edit that over-generalized.")
    raise SystemExit(1)

n_sites = len(target.get("sites", []))
if n_sites < min_sites:
    print("  RESULT: FAIL — detector sensitivity collapsed.")
    print("          %r still fires, but on only %d site(s) (floor: %d, historically 18)."
          % (must_fail, n_sites, min_sites))
    print("          A hedge or pattern edit has silenced most assertion sites.")
    print("          Firing on one line is not detection; it is luck.")
    raise SystemExit(1)

print("  RESULT: PASS — detector still fires on the known historical false claim")
print("          (%d assertion site(s), floor %d; fact: %s)"
      % (n_sites, min_sites, target["detail"]))
PY
STATUS=$?

echo "=== retro-test $([ ${STATUS} -eq 0 ] && echo PASSED || echo FAILED) ==="
exit ${STATUS}
