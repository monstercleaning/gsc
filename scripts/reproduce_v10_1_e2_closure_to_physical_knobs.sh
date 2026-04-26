#!/usr/bin/env bash
set -euo pipefail

# E2.11 closure-requirements -> physical-knobs translation (diagnostic-only).
#
# Outputs:
#   - results:      v11.0.0/results/diagnostic_cmb_e2_closure_to_physical_knobs/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_closure_to_physical_knobs/  (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_cmb_e2_closure_to_physical_knobs"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_closure_to_physical_knobs"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_closure_to_physical_knobs_r0.zip"

WS13_TABLE_DEFAULT="${V101_DIR}/results/diagnostic_cmb_e2_closure_requirements/tables/A_required_vs_zstart.csv"

SYNC_PAPER_ASSETS="0"
ZIP_OUT="${ZIP_OUT_DEFAULT}"
WS13_TABLE="${WS13_TABLE_DEFAULT}"

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
    --ws13-table)
      WS13_TABLE="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH] [--ws13-table PATH]

Outputs:
  - ${RESULTS_DIR}/
  - (optional) ${PAPER_ASSETS_DIR}/ + zip: ${ZIP_OUT_DEFAULT}
EOF
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

python_has_deps() {
  local py="$1"
  local d="${RESULTS_DIR}/.mplconfig_check"
  mkdir -p "${d}" >/dev/null 2>&1 || true
  MPLBACKEND="Agg" MPLCONFIGDIR="${d}" "${py}" - <<'PY' >/dev/null 2>&1
import numpy  # noqa: F401
import matplotlib  # noqa: F401
PY
}

PY_V101="${V101_DIR}/.venv/bin/python"
PY_PHASE10="${V101_DIR}/B/GSC_v10_8_PUBLICATION_BUNDLE/.venv/bin/python"
PY=""

if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
  PY="${PY_V101}"
else
  if [[ "${GSC_SKIP_BOOTSTRAP:-0}" != "1" ]]; then
    echo "[reproduce-e2-knobs] bootstrap venv"
    if bash "${V101_DIR}/scripts/bootstrap_venv.sh"; then
      if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
        PY="${PY_V101}"
      fi
    fi
  fi
fi

if [[ -z "${PY}" ]]; then
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[reproduce-e2-knobs] WARNING: falling back to Phase10 venv python"
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need numpy+matplotlib)." >&2
    exit 1
  fi
fi

if [[ ! -f "${WS13_TABLE}" ]]; then
  echo "[reproduce-e2-knobs] WS13 table missing, generating it first..."
  (cd "${ROOT_DIR}" && bash "${V101_DIR}/scripts/reproduce_v10_1_e2_closure_requirements.sh")
fi

if [[ ! -f "${WS13_TABLE}" ]]; then
  echo "ERROR: WS13 table still missing after reproduce attempt: ${WS13_TABLE}" >&2
  exit 1
fi

mkdir -p "${RESULTS_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[reproduce-e2-knobs] python=${PY}"
echo "[reproduce-e2-knobs] ws13_table=${WS13_TABLE}"
echo "[reproduce-e2-knobs] outdir=${RESULTS_DIR}"

(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_closure_to_physical_knobs.py" \
  --ws13-table "${WS13_TABLE}" \
  --outdir "${RESULTS_DIR}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-knobs] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"
  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/tables/"*.txt "${PAPER_ASSETS_DIR}/tables/" 2>/dev/null || true
  cp -f "${RESULTS_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  (cd "${ROOT_DIR}" && PAPER_ASSETS_DIR="${PAPER_ASSETS_DIR}" ZIP_OUT="${ZIP_OUT}" "${PY}" - <<'PY'
import os
import zipfile
from pathlib import Path

pa = Path(os.environ["PAPER_ASSETS_DIR"]).resolve()
zip_out = Path(os.environ["ZIP_OUT"]).resolve()

def iter_files(base: Path):
  for p in sorted(base.rglob("*")):
    if p.is_file():
      yield p

epoch_dt = (1980, 1, 1, 0, 0, 0)
with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
  for src in iter_files(pa):
    rel = src.relative_to(pa.parent)
    info = zipfile.ZipInfo(str(rel).replace(os.sep, "/"), date_time=epoch_dt)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zf.writestr(info, src.read_bytes())
print("WROTE", zip_out)
PY
  )
fi

echo "[reproduce-e2-knobs] done"
