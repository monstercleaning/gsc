#!/usr/bin/env bash
set -euo pipefail

# WS13 / E2 closure requirements consolidation (diagnostic-only).
#
# Outputs:
#   - results:      v11.0.0/results/diagnostic_cmb_e2_closure_requirements/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_closure_requirements/  (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_cmb_e2_closure_requirements"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_closure_requirements"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_closure_requirements_r0.zip"

E24_SCAN_CSV_DEFAULT="${V101_DIR}/results/late_time_fit_cmb_e2_closure_diagnostic/scan/tables/cmb_e2_dm_rs_fit_scan.csv"

SYNC_PAPER_ASSETS="0"
ZIP_OUT="${ZIP_OUT_DEFAULT}"
E24_SCAN_CSV="${E24_SCAN_CSV_DEFAULT}"

QUANTILES="0.1,0.5,0.9"
DM_TARGETS="0.9290939714464278"
Z_BOOST_START_LIST="5,6,7,8,10,12,15,20"

H0="67.4"
OMEGA_M="0.315"
OMEGA_L="0.685"
GSC_P="0.6"
GSC_ZTRANS="1.8"
CMB_BRIDGE_Z="5"
OMEGA_B_H2="0.02237"
OMEGA_C_H2="0.1200"
NEFF="3.046"
TCMB_K="2.7255"

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
    --e24-scan-csv)
      E24_SCAN_CSV="${2:-}"
      shift 2
      ;;
    --quantiles)
      QUANTILES="${2:-}"
      shift 2
      ;;
    --dm-targets)
      DM_TARGETS="${2:-}"
      shift 2
      ;;
    --z-boost-start-list)
      Z_BOOST_START_LIST="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--e24-scan-csv PATH]
          [--quantiles CSV] [--dm-targets CSV] [--z-boost-start-list CSV]

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
elif [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
  echo "[reproduce-e2-closure-req] WARNING: falling back to Phase10 venv python."
  PY="${PY_PHASE10}"
else
  echo "ERROR: no usable python found (need numpy+matplotlib)." >&2
  exit 1
fi

if [[ ! -f "${E24_SCAN_CSV}" ]]; then
  echo "ERROR: missing E2.4 scan CSV: ${E24_SCAN_CSV}" >&2
  exit 1
fi

mkdir -p "${RESULTS_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[reproduce-e2-closure-req] python=${PY}"
echo "[reproduce-e2-closure-req] e24_scan_csv=${E24_SCAN_CSV}"
echo "[reproduce-e2-closure-req] quantiles=${QUANTILES} dm_targets=${DM_TARGETS} z_boost_start_list=${Z_BOOST_START_LIST}"
echo "[reproduce-e2-closure-req] outdir=${RESULTS_DIR}"

(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_closure_requirements_plot.py" \
  --e24-scan-csv "${E24_SCAN_CSV}" \
  --outdir "${RESULTS_DIR}" \
  --quantiles "${QUANTILES}" \
  --dm-targets "${DM_TARGETS}" \
  --z-boost-start-list "${Z_BOOST_START_LIST}" \
  --model gsc_transition \
  --cmb-bridge-z "${CMB_BRIDGE_Z}" \
  --H0 "${H0}" --Omega-m "${OMEGA_M}" --Omega-L "${OMEGA_L}" \
  --gsc-p "${GSC_P}" --gsc-ztrans "${GSC_ZTRANS}" \
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}" \
  --Neff "${NEFF}" --Tcmb-K "${TCMB_K}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-closure-req] syncing paper-assets view + zipping..."
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

echo "[reproduce-e2-closure-req] done"

