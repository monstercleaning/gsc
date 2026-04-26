#!/usr/bin/env bash
set -euo pipefail

# E2 analytic drift bound helper (diagnostic-only).
#
# Outputs:
#   - results:      v11.0.0/results/diagnostic_e2_drift_bound_analytic/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_drift_bound_analytic/  (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_e2_drift_bound_analytic"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_drift_bound_analytic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_drift_bound_analytic_r0.zip"

Z1="2.0"
Z2="5.0"
H0_MIN="60.0"
H0_MAX="75.0"
H0_STEP="2.5"
H0_VALUES=""
REFERENCE_H0="67.4"

SYNC_PAPER_ASSETS="0"
ZIP_OUT="${ZIP_OUT_DEFAULT}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sync-paper-assets)
      SYNC_PAPER_ASSETS="1"
      shift
      ;;
    --zip-out)
      ZIP_OUT="${2:-}"
      shift 2
      ;;
    --z1)
      Z1="${2:-}"
      shift 2
      ;;
    --z2)
      Z2="${2:-}"
      shift 2
      ;;
    --h0-min)
      H0_MIN="${2:-}"
      shift 2
      ;;
    --h0-max)
      H0_MAX="${2:-}"
      shift 2
      ;;
    --h0-step)
      H0_STEP="${2:-}"
      shift 2
      ;;
    --h0-values)
      H0_VALUES="${2:-}"
      shift 2
      ;;
    --reference-h0)
      REFERENCE_H0="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--z1 X] [--z2 X]
          [--h0-min X] [--h0-max X] [--h0-step X]
          [--h0-values CSV]
          [--reference-h0 X]
EOF
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

PY="${GSC_PYTHON:-}"
if [[ -z "${PY}" ]]; then
  if [[ -x "${V101_DIR}/.venv/bin/python" ]]; then
    PY="${V101_DIR}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
  else
    echo "ERROR: python3 not found and v11.0.0/.venv/bin/python missing." >&2
    exit 2
  fi
fi

mkdir -p "${RESULTS_DIR}"

cmd=(
  "${PY}" "${V101_DIR}/scripts/e2_drift_bound_analytic.py"
  --outdir "${RESULTS_DIR}"
  --z1 "${Z1}"
  --z2 "${Z2}"
  --h0-min "${H0_MIN}"
  --h0-max "${H0_MAX}"
  --h0-step "${H0_STEP}"
  --reference-h0 "${REFERENCE_H0}"
)
if [[ -n "${H0_VALUES}" ]]; then
  cmd+=( --h0-values "${H0_VALUES}" )
fi

(cd "${ROOT_DIR}" && "${cmd[@]}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  mkdir -p "${PAPER_ASSETS_DIR}/tables"
  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/tables/"*.txt "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  (cd "${ROOT_DIR}" && PAPER_ASSETS_DIR="${PAPER_ASSETS_DIR}" ZIP_OUT="${ZIP_OUT}" "${PY}" - <<'PY'
import os
import zipfile
from pathlib import Path

pa = Path(os.environ["PAPER_ASSETS_DIR"]).resolve()
zip_out = Path(os.environ["ZIP_OUT"]).resolve()

epoch_dt = (1980, 1, 1, 0, 0, 0)
with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
  for src in sorted(pa.rglob("*")):
    if not src.is_file():
      continue
    rel = src.relative_to(pa.parent).as_posix()
    info = zipfile.ZipInfo(rel, date_time=epoch_dt)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zf.writestr(info, src.read_bytes())
print("WROTE", zip_out)
PY
  )
fi

echo "[reproduce-e2-drift-bound-analytic] done"
