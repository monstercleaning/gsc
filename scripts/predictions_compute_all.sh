#!/usr/bin/env bash
# predictions_compute_all.sh — orchestrate all 8 prediction compute pipelines.
#
# Runs each of the predictions_compute_PN.py scripts in sequence, captures
# the SHA-256 of each pipeline output, and prints a summary table.
#
# Determinism check: pass --verify to run each pipeline twice and confirm
# identical hashes.
#
# Usage:
#   bash scripts/predictions_compute_all.sh
#   bash scripts/predictions_compute_all.sh --verify

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

VERIFY=0
if [ "${1:-}" = "--verify" ]; then
  VERIFY=1
fi

PREDICTIONS=(P1 P2 P3 P4 P5 P7 P8 P6 P9 P10)

echo "=== GSC predictions compute orchestrator ==="
echo "  repo: ${REPO_ROOT}"
echo "  verify mode: ${VERIFY}"
echo

declare -a PRIMARY_HASHES
declare -a VERIFY_HASHES

for pid in "${PREDICTIONS[@]}"; do
  script="scripts/predictions_compute_${pid}.py"
  if [ ! -f "${script}" ]; then
    echo "  ${pid}  MISSING (no ${script})"
    PRIMARY_HASHES+=("${pid}:MISSING")
    continue
  fi
  hash1=$(python3 "${script}" 2>&1 | grep "SHA-256:" | sed 's/.*SHA-256: //')
  PRIMARY_HASHES+=("${pid}:${hash1}")
  echo "  ${pid}  primary_hash=${hash1:0:16}..."
  if [ "${VERIFY}" = "1" ]; then
    hash2=$(python3 "${script}" 2>&1 | grep "SHA-256:" | sed 's/.*SHA-256: //')
    VERIFY_HASHES+=("${pid}:${hash2}")
    if [ "${hash1}" = "${hash2}" ]; then
      echo "        verify_hash=${hash2:0:16}... ✓ MATCH"
    else
      echo "        verify_hash=${hash2:0:16}... ✗ MISMATCH (DETERMINISM VIOLATION)"
      exit 2
    fi
  fi
done

echo
echo "=== Scoring (where observed_data.json is available) ==="
SCORERS=(P1 P3 P4 P5 P6 P7 P9)
for pid in "${SCORERS[@]}"; do
  scorer="scripts/predictions_score_${pid}.py"
  if [ -f "${scorer}" ]; then
    # Capture stdout regardless of exit code (PASS=0, FAIL=1, SUB-THRESHOLD=0).
    set +e
    out=$(python3 "${scorer}" 2>&1)
    set -e
    outcome=$(echo "${out}" | grep "outcome:" | sed 's/.*outcome: //')
    echo "  ${pid}: ${outcome}"
  fi
done

echo
echo "=== Summary ==="
python3 "${SCRIPT_DIR}/predictions_scoreboard.py"

if [ "${VERIFY}" = "1" ]; then
  echo
  echo "=== Determinism verification: all hashes matched across two runs ==="
fi
