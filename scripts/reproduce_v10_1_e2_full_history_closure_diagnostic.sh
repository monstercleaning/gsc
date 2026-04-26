#!/usr/bin/env bash
set -euo pipefail

# E2.7 full-history (no-stitch) closure diagnostic reproduction entrypoint (v11.0.0).
#
# Outputs are intentionally isolated from canonical late-time paper builds:
#   - results:      v11.0.0/results/diagnostic_cmb_full_history/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_full_history_closure_diagnostic/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_cmb_full_history"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_full_history_closure_diagnostic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_full_history_closure_diagnostic_r1.zip"

CMB_CSV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
CMB_COV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

# Fixed Planck-like early inputs.
H0="67.4"
OMEGA_M="0.315"
OMEGA_B_H2="0.02237"
OMEGA_C_H2="0.1200"
NEFF="3.046"
TCMB_K="2.7255"

# Grid defaults (coarse, deterministic).
BRIDGE_Z_REF="5"
P_GRID="0.55,0.6,0.65,0.7,0.75,0.8,0.9"
ZTRANS_GRID="0.8,1.2,1.5,1.8,2.2,3.0,4.0"
Z_RELAX_LIST="2,5,10,20,inf"
Z_BBN_CLAMP="1e7"

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
    --bridge-z-ref)
      BRIDGE_Z_REF="${2:-}"
      shift 2
      ;;
    --p-grid)
      P_GRID="${2:-}"
      shift 2
      ;;
    --ztrans-grid)
      ZTRANS_GRID="${2:-}"
      shift 2
      ;;
    --z-relax-list)
      Z_RELAX_LIST="${2:-}"
      shift 2
      ;;
    --z-bbn-clamp)
      Z_BBN_CLAMP="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--bridge-z-ref Z] [--p-grid CSV] [--ztrans-grid CSV] [--z-relax-list CSV] [--z-bbn-clamp Z]

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
  if [[ ! -x "${PY_V101}" || "${GSC_FORCE_BOOTSTRAP:-0}" == "1" ]]; then
    if [[ "${GSC_SKIP_BOOTSTRAP:-0}" != "1" ]]; then
      echo "[reproduce-e2-full-history] bootstrapping v11.0.0 venv..."
      if bash "${V101_DIR}/scripts/bootstrap_venv.sh"; then
        if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
          PY="${PY_V101}"
        fi
      fi
    fi
  fi
fi

if [[ -z "${PY}" ]]; then
  if [[ "${GSC_REQUIRE_V101_VENV:-0}" == "1" ]]; then
    echo "ERROR: GSC_REQUIRE_V101_VENV=1 but v11.0.0/.venv is missing or incomplete." >&2
    exit 1
  fi
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[reproduce-e2-full-history] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
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

echo "[reproduce-e2-full-history] python=${PY}"
echo "[reproduce-e2-full-history] results_dir=${RESULTS_DIR}"
echo "[reproduce-e2-full-history] grid: bridge_z_ref=${BRIDGE_Z_REF} p_grid=${P_GRID} ztrans_grid=${ZTRANS_GRID}"
echo "[reproduce-e2-full-history] z_relax_list=${Z_RELAX_LIST}  z_bbn_clamp=${Z_BBN_CLAMP}"
echo "[reproduce-e2-full-history] sync_paper_assets=${SYNC_PAPER_ASSETS}  zip_out=${ZIP_OUT}"

echo "[reproduce-e2-full-history] running scan..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_full_history_closure_scan.py" \
  --cmb "${CMB_CSV}" --cmb-cov "${CMB_COV}" \
  --outdir "${RESULTS_DIR}" \
  --bridge-z-ref "${BRIDGE_Z_REF}" \
  --p-grid "${P_GRID}" \
  --ztrans-grid "${ZTRANS_GRID}" \
  --z-relax-list "${Z_RELAX_LIST}" \
  --z-bbn-clamp "${Z_BBN_CLAMP}" \
  --H0 "${H0}" --Omega-m "${OMEGA_M}" \
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}" \
  --Neff "${NEFF}" --Tcmb-K "${TCMB_K}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-full-history] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"

  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  echo "[reproduce-e2-full-history] zipping: ${ZIP_OUT}"
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

echo "[reproduce-e2-full-history] done"
