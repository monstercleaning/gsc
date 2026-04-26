#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

PY="${GSC_PYTHON:-}"
if [[ -z "${PY}" ]]; then
  if [[ -x "${SCRIPT_DIR}/../.venv/bin/python" ]]; then
    PY="${SCRIPT_DIR}/../.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
  else
    echo "ERROR: python3 not found and v11.0.0/.venv/bin/python missing." >&2
    exit 2
  fi
fi

exec "${PY}" "${SCRIPT_DIR}/verify_all_canonical_artifacts.py" "$@"
