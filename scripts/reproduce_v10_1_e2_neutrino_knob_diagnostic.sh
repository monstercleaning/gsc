#!/usr/bin/env bash
set -euo pipefail

# E2.6 neutrino-knob diagnostic reproduction entrypoint (v11.0.0).
#
# Outputs are intentionally isolated from canonical late-time paper builds:
#   - results:      v11.0.0/results/diagnostic_cmb_e2_neutrino_knob/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_neutrino_knob_diagnostic/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_cmb_e2_neutrino_knob"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_neutrino_knob_diagnostic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_neutrino_knob_diagnostic_r0.zip"

CMB_CSV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
CMB_COV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

# Fixed Planck-like inputs (diagnostic; not a fit).
H0="67.4"
OMEGA_M="0.315"
OMEGA_L="0.685"
GSC_P="0.6"
GSC_ZTRANS="1.8"

OMEGA_B_H2="0.02237"
OMEGA_C_H2="0.1200"
NEFF_BASE="3.046"
TCMB_K="2.7255"

# Scan knobs.
BRIDGE_ZS="5,10"
DELTA_NEFF_GRID="-1.0,-0.5,0.0,0.5,1.0"

# Fit grid (same defaults as E2.2).
RS_MIN="0.90"
RS_MAX="1.20"
RS_STEP="5e-4"

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
    --bridge-zs)
      BRIDGE_ZS="${2:-}"
      shift 2
      ;;
    --delta-neff-grid)
      DELTA_NEFF_GRID="${2:-}"
      shift 2
      ;;
    --rs-min)
      RS_MIN="${2:-}"
      shift 2
      ;;
    --rs-max)
      RS_MAX="${2:-}"
      shift 2
      ;;
    --rs-step)
      RS_STEP="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--bridge-zs CSV] [--delta-neff-grid CSV]
          [--rs-min X] [--rs-max X] [--rs-step X]

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
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[reproduce-e2-neutrino] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need numpy+matplotlib)." >&2
    exit 1
  fi
fi

if [[ ! -f "${CMB_CSV}" || ! -f "${CMB_COV}" ]]; then
  echo "Missing expected CHW2018 CMB priors files:" >&2
  echo "  ${CMB_CSV}" >&2
  echo "  ${CMB_COV}" >&2
  exit 1
fi

mkdir -p "${RESULTS_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[reproduce-e2-neutrino] python=${PY}"
echo "[reproduce-e2-neutrino] results_dir=${RESULTS_DIR}"
echo "[reproduce-e2-neutrino] bridge_zs=${BRIDGE_ZS}"
echo "[reproduce-e2-neutrino] delta_neff_grid=${DELTA_NEFF_GRID} (Neff_base=${NEFF_BASE})"
echo "[reproduce-e2-neutrino] sync_paper_assets=${SYNC_PAPER_ASSETS} zip_out=${ZIP_OUT}"

echo "[reproduce-e2-neutrino] running diagnostic script..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_neutrino_knob_diagnostic.py" \
  --model gsc_transition \
  --cmb "${CMB_CSV}" --cmb-cov "${CMB_COV}" \
  --outdir "${RESULTS_DIR}" \
  --bridge-zs "${BRIDGE_ZS}" \
  --delta-neff-grid="${DELTA_NEFF_GRID}" \
  --H0 "${H0}" --Omega-m "${OMEGA_M}" --Omega-L "${OMEGA_L}" \
  --gsc-p "${GSC_P}" --gsc-ztrans "${GSC_ZTRANS}" \
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}" \
  --Neff-base "${NEFF_BASE}" --Tcmb-K "${TCMB_K}" \
  --rs-min "${RS_MIN}" --rs-max "${RS_MAX}" --rs-step "${RS_STEP}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-neutrino] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"

  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  echo "[reproduce-e2-neutrino] zipping: ${ZIP_OUT}"
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
    rel = src.relative_to(pa.parent)  # include the folder name
    info = zipfile.ZipInfo(str(rel).replace(os.sep, "/"), date_time=epoch_dt)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zf.writestr(info, src.read_bytes())
print("WROTE", zip_out)
PY
  )
fi

echo "[reproduce-e2-neutrino] done"
