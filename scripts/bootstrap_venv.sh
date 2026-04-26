#!/usr/bin/env bash
set -euo pipefail

V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${V101_DIR}/.venv"
PY="${PYTHON:-python3}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "[bootstrap] creating venv: ${VENV_DIR}"
  "${PY}" -m venv "${VENV_DIR}"
fi

echo "[bootstrap] upgrading pip"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip

echo "[bootstrap] installing requirements"
"${VENV_DIR}/bin/python" -m pip install -r "${V101_DIR}/requirements.txt"

echo "[bootstrap] done"
