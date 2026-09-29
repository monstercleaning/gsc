#!/usr/bin/env bash
# predictions_compute_all.sh — reproduce the whole register and score it.
#
# Registered pipeline outputs are frozen records. This orchestrator therefore
# never overwrites them: it recomputes every pipeline into a temporary file and
# checks that the result is byte-identical to the registered output. With
# --verify it also recomputes a second time to confirm determinism. It then
# reruns every scorer into a temporary folder, checks that each scorecard is
# reproduced and that no scorer crashed, and prints the scoreboard.
#
# Usage:
#   bash pipelines/predictions_compute_all.sh
#   bash pipelines/predictions_compute_all.sh --verify
#
# Exit: 0 = every pipeline and scorecard reproduces; 2 = mismatch or scorer crash.

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
echo "=== Scoring (scorecards are recomputed in a temporary folder and compared, never overwritten) ==="
for scorer in pipelines/predictions_score_P*.py; do
  pid="$(basename "${scorer}" .py | sed 's/predictions_score_//')"
  entry="$(ls -d predictions/P$(printf '%02d' "${pid#P}")_*/ | head -1)"
  if grep -q -- '"--register-dir"' "${scorer}"; then
    copy="${TMP}/register_${pid}"; mkdir -p "${copy}"; cp -R "${entry}." "${copy}/"
    set +e; out=$(python3 "${scorer}" --register-dir "${copy}" 2>&1); rc=$?; set -e
    card="${copy}/scorecard.md"
  else
    set +e; out=$(python3 "${scorer}" --output "${TMP}/${pid}_scorecard.md" 2>&1); rc=$?; set -e
    card="${TMP}/${pid}_scorecard.md"
  fi
  outcome="$(echo "${out}" | grep -o 'outcome: .*' | head -1 | sed 's/outcome: //' || true)"
  word="${outcome%% *}"
  # Scorers exit 1 on a FAIL verdict; any other non-zero exit, or no outcome line, is a crash, not a verdict.
  if [ -z "${word}" ] || [ "${rc}" -gt 1 ] || { [ "${rc}" = "1" ] && [ "${word}" != "FAIL" ]; }; then
    echo "  ${pid}: SCORER ERROR (exit ${rc})"; echo "${out}" | tail -3 | sed 's/^/      /'; status=2; continue
  fi
  if cmp -s "${card}" "${entry}scorecard.md"; then note="scorecard reproduces"; else note="SCORECARD DIFFERS"; status=2; fi
  echo "  ${pid}: ${outcome}; ${note}"
done

echo
echo "=== Scoreboard ==="
python3 "${SCRIPT_DIR}/predictions_scoreboard.py"
[ "${status}" = "0" ] && echo "=== All pipelines reproduce their registered outputs ===" || echo "=== MISMATCH: see above ==="
exit "${status}"
