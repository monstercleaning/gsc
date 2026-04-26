#!/usr/bin/env bash
set -euo pipefail

# Distance-duality diagnostic reproduction entrypoint (v11.0.0).
#
# Outputs are isolated from canonical late-time paper builds:
#   - results:      v11.0.0/results/diagnostic_distance_duality/
#   - paper assets: v11.0.0/paper_assets_distance_duality_diagnostic/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_distance_duality"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_distance_duality_diagnostic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_distance_duality_diagnostic_r0.zip"

SN_CSV="${V101_DIR}/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv"
SN_COV="${V101_DIR}/data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov"
BAO_CSV="${V101_DIR}/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv"

MODEL="gsc_transition"
H0="67.4"
OMEGA_M="0.315"
GSC_P="0.6"
GSC_ZTRANS="1.8"

EPS_MIN="-0.20"
EPS_MAX="0.20"
EPS_STEP="0.002"

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
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    --eps-min)
      EPS_MIN="${2:-}"
      shift 2
      ;;
    --eps-max)
      EPS_MAX="${2:-}"
      shift 2
      ;;
    --eps-step)
      EPS_STEP="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH] [--model {lcdm,gsc_transition,gsc_powerlaw}]
          [--eps-min X] [--eps-max X] [--eps-step X]

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
    echo "[distance-duality] bootstrap venv"
    if bash "${V101_DIR}/scripts/bootstrap_venv.sh"; then
      if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
        PY="${PY_V101}"
      fi
    fi
  fi
fi

if [[ -z "${PY}" ]]; then
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[distance-duality] WARNING: falling back to Phase10 venv python"
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need numpy+matplotlib)." >&2
    exit 1
  fi
fi

mkdir -p "${RESULTS_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[distance-duality] python=${PY}"
echo "[distance-duality] outdir=${RESULTS_DIR}"
echo "[distance-duality] model=${MODEL}  eps=[${EPS_MIN},${EPS_MAX}] step=${EPS_STEP}"
echo "[distance-duality] sync_paper_assets=${SYNC_PAPER_ASSETS}  zip_out=${ZIP_OUT}"

(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/distance_duality_diagnostic.py" \
  --outdir "${RESULTS_DIR}" \
  --sn "${SN_CSV}" --sn-cov "${SN_COV}" \
  --bao "${BAO_CSV}" \
  --model "${MODEL}" \
  --H0 "${H0}" --Omega-m "${OMEGA_M}" --gsc-p "${GSC_P}" --gsc-ztrans "${GSC_ZTRANS}" \
  --eps-min "${EPS_MIN}" --eps-max "${EPS_MAX}" --eps-step "${EPS_STEP}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[distance-duality] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"
  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  echo "[distance-duality] zipping: ${ZIP_OUT}"
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

echo "[distance-duality] done"

