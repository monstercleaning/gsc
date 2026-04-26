#!/usr/bin/env bash
set -euo pipefail

# SN two-pass sensitivity diagnostic reproduction entrypoint (v11.0.0).
#
# Outputs are isolated from canonical late-time paper builds:
#   - results:      v11.0.0/results/diagnostic_sn_two_pass_sensitivity/
#   - paper assets: v11.0.0/paper_assets_sn_two_pass_sensitivity_diagnostic/ (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_sn_two_pass_sensitivity"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_sn_two_pass_sensitivity_diagnostic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_sn_two_pass_sensitivity_diagnostic_r0.zip"

SYNC_PAPER_ASSETS="0"
ZIP_OUT="${ZIP_OUT_DEFAULT}"

MODELS="lcdm,gsc_transition"
TWO_PASS_TOP="60,200,500"
OMEGA_M_GRID="0.27,0.295,0.315,0.335,0.36"
P_GRID="0.55,0.6,0.65,0.7,0.8"
ZTRANS_GRID="1.0,1.5,1.8,2.5,3.5"
H0_GRID="60:80:2"
N_GRID="4000"

SN_CSV="${V101_DIR}/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv"
SN_COV="${V101_DIR}/data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov"
BAO_CSV="${V101_DIR}/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv"
DRIFT_CSV="${V101_DIR}/data/drift/elt_andes_liske_conservative_20yr_asimov.csv"

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
    --models)
      MODELS="${2:-}"
      shift 2
      ;;
    --two-pass-top)
      TWO_PASS_TOP="${2:-}"
      shift 2
      ;;
    --Omega-m-grid)
      OMEGA_M_GRID="${2:-}"
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
    --H0-grid)
      H0_GRID="${2:-}"
      shift 2
      ;;
    --n-grid)
      N_GRID="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF2
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--models CSV] [--two-pass-top CSV]
          [--Omega-m-grid SPEC] [--p-grid SPEC] [--ztrans-grid SPEC]
          [--H0-grid SPEC] [--n-grid N]

Outputs:
  - ${RESULTS_DIR}/
  - (optional) ${PAPER_ASSETS_DIR}/ + zip: ${ZIP_OUT_DEFAULT}
EOF2
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
import scipy  # noqa: F401
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
    echo "[sn-two-pass] bootstrap venv"
    if bash "${V101_DIR}/scripts/bootstrap_venv.sh"; then
      if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
        PY="${PY_V101}"
      fi
    fi
  fi
fi

if [[ -z "${PY}" ]]; then
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[sn-two-pass] WARNING: falling back to Phase10 venv python"
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need numpy+scipy+matplotlib)." >&2
    exit 1
  fi
fi

mkdir -p "${RESULTS_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[sn-two-pass] python=${PY}"
echo "[sn-two-pass] outdir=${RESULTS_DIR}"
echo "[sn-two-pass] models=${MODELS} two_pass_top=${TWO_PASS_TOP}"

(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/sn_two_pass_sensitivity_diagnostic.py" \
  --outdir "${RESULTS_DIR}" \
  --models "${MODELS}" \
  --two-pass-top "${TWO_PASS_TOP}" \
  --sn "${SN_CSV}" --sn-cov "${SN_COV}" --bao "${BAO_CSV}" --drift "${DRIFT_CSV}" \
  --profile-H0 \
  --H0-grid "${H0_GRID}" \
  --Omega-m-grid "${OMEGA_M_GRID}" \
  --p-grid "${P_GRID}" \
  --ztrans-grid "${ZTRANS_GRID}" \
  --n-grid "${N_GRID}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[sn-two-pass] syncing paper-assets view + zipping..."
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

echo "[sn-two-pass] done"
