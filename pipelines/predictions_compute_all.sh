#!/usr/bin/env bash
# predictions_compute_all.sh — reproduce the whole register and score it.
#
# Registered pipeline outputs are frozen records. This orchestrator therefore
# never overwrites them: it recomputes every pipeline into a temporary file and
# checks that the result is byte-identical to the registered output. With
# --verify it also recomputes a second time to confirm determinism. It then
# runs every scorer (scorecards are deterministic) and prints the scoreboard.
#
# Usage:
#   bash pipelines/predictions_compute_all.sh
#   bash pipelines/predictions_compute_all.sh --verify
#
# Exit: 0 = every pipeline reproduces its registered output; 2 = mismatch.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"
VERIFY=0; [ "${1:-}" = "--verify" ] && VERIFY=1
TMP="$(mktemp -d)"; trap 'rm -rf "${TMP}"' EXIT

echo "=== Reproducing the register (frozen outputs are compared, never overwritten) ==="
status=0
for entry in predictions/P*/; do
  folder="$(basename "${entry}")"
  pid="P$(echo "${folder}" | sed -E 's/^P0*([0-9]+)_.*/\1/')"
  script="pipelines/predictions_compute_${pid}.py"
  [ -f "${script}" ] || { echo "  ${pid}: no pipeline"; status=2; continue; }
  python3 "${script}" --output "${TMP}/${pid}.json" >/dev/null
  if cmp -s "${TMP}/${pid}.json" "${entry}pipeline_output.json"; then
    line="  ${pid}: reproduces registered output"
  else
    line="  ${pid}: DIFFERS from registered output"; status=2
  fi
  if [ "${VERIFY}" = "1" ]; then
    python3 "${script}" --output "${TMP}/${pid}.2.json" >/dev/null
    if cmp -s "${TMP}/${pid}.json" "${TMP}/${pid}.2.json"; then line="${line}; deterministic"; else line="${line}; NOT DETERMINISTIC"; status=2; fi
  fi
  echo "${line}"
done

echo
echo "=== Scoring (entries with observed data) ==="
for scorer in pipelines/predictions_score_P*.py; do
  pid="$(basename "${scorer}" .py | sed 's/predictions_score_//')"
  set +e; out=$(python3 "${scorer}" 2>&1); set -e
  echo "  ${pid}: $(echo "${out}" | grep -o 'outcome: .*' | sed 's/outcome: //')"
done

echo
echo "=== Scoreboard ==="
python3 "${SCRIPT_DIR}/predictions_scoreboard.py"
[ "${status}" = "0" ] && echo "=== All pipelines reproduce their registered outputs ===" || echo "=== MISMATCH: see above ==="
exit "${status}"
