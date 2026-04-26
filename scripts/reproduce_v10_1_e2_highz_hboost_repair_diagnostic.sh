#!/usr/bin/env bash
set -euo pipefail

# E2.10 high-z H-boost repair scan (full-history; drift-safe) reproduction entrypoint (v11.0.0).
#
# Diagnostic-only. Does not modify canonical late-time pipeline outputs.
#
# Outputs:
#   - results:      v11.0.0/results/diagnostic_cmb_highz_hboost_repair/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_highz_hboost_repair_diagnostic/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_cmb_highz_hboost_repair"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_highz_hboost_repair_diagnostic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_highz_hboost_repair_diagnostic_r0.zip"

CMB_CSV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
CMB_COV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

# Fixed Planck-like early inputs.
H0="67.4"
OMEGA_M="0.315"
OMEGA_B_H2="0.02237"
OMEGA_C_H2="0.1200"
NEFF="3.046"
TCMB_K="2.7255"

# Late-time checkpoint defaults.
GSC_P="0.6"
GSC_ZTRANS="1.8"

# Full-history base (guarded relax) defaults.
Z_RELAX_START="5.0"
RELAX_SCALE="0.5"
P_TARGET="1.5"
Z_BBN_CLAMP="1e7"

# Boost scan defaults.
Z_BOOST_START_LIST="5,6,7,8,10"
A_MIN="1.00"
A_MAX="2.00"
A_STEP="0.02"
TRANSITION_WIDTH="0.0"

# Numerics.
N_DM="8192"
N_RS="8192"

RS_STAR_CALIBRATION="" # default: script constant

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
    --gsc-p)
      GSC_P="${2:-}"
      shift 2
      ;;
    --gsc-ztrans)
      GSC_ZTRANS="${2:-}"
      shift 2
      ;;
    --z-relax-start)
      Z_RELAX_START="${2:-}"
      shift 2
      ;;
    --relax-scale)
      RELAX_SCALE="${2:-}"
      shift 2
      ;;
    --p-target)
      P_TARGET="${2:-}"
      shift 2
      ;;
    --z-bbn-clamp)
      Z_BBN_CLAMP="${2:-}"
      shift 2
      ;;
    --z-boost-start-list)
      Z_BOOST_START_LIST="${2:-}"
      shift 2
      ;;
    --A-min)
      A_MIN="${2:-}"
      shift 2
      ;;
    --A-max)
      A_MAX="${2:-}"
      shift 2
      ;;
    --A-step)
      A_STEP="${2:-}"
      shift 2
      ;;
    --transition-width)
      TRANSITION_WIDTH="${2:-}"
      shift 2
      ;;
    --n-dm)
      N_DM="${2:-}"
      shift 2
      ;;
    --n-rs)
      N_RS="${2:-}"
      shift 2
      ;;
    --rs-star-calibration)
      RS_STAR_CALIBRATION="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--gsc-p P] [--gsc-ztrans ZT]
          [--z-relax-start Z] [--relax-scale S] [--p-target P_TARGET]
          [--z-bbn-clamp Z]
          [--z-boost-start-list CSV] [--A-min X] [--A-max X] [--A-step DX]
          [--transition-width W]
          [--n-dm N] [--n-rs N]
          [--rs-star-calibration X]

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
      echo "[reproduce-e2-highz-hboost] bootstrapping v11.0.0 venv..."
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
    echo "[reproduce-e2-highz-hboost] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
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

echo "[reproduce-e2-highz-hboost] python=${PY}"
echo "[reproduce-e2-highz-hboost] results_dir=${RESULTS_DIR}"
echo "[reproduce-e2-highz-hboost] model: p=${GSC_P} z_transition=${GSC_ZTRANS}"
echo "[reproduce-e2-highz-hboost] full-history base: z_relax_start=${Z_RELAX_START} relax_scale=${RELAX_SCALE} p_target=${P_TARGET} z_bbn_clamp=${Z_BBN_CLAMP}"
echo "[reproduce-e2-highz-hboost] boost grid: z_boost_start_list=${Z_BOOST_START_LIST} A=[${A_MIN},${A_MAX}] step=${A_STEP} transition_width=${TRANSITION_WIDTH}"
echo "[reproduce-e2-highz-hboost] n_dm=${N_DM} n_rs=${N_RS}"
echo "[reproduce-e2-highz-hboost] sync_paper_assets=${SYNC_PAPER_ASSETS} zip_out=${ZIP_OUT}"

echo "[reproduce-e2-highz-hboost] running scan..."
cmd=( "${PY}" "${V101_DIR}/scripts/cmb_e2_highz_hboost_repair_scan.py"
  --cmb "${CMB_CSV}" --cmb-cov "${CMB_COV}"
  --outdir "${RESULTS_DIR}"
  --gsc-p "${GSC_P}" --gsc-ztrans "${GSC_ZTRANS}"
  --z-relax-start "${Z_RELAX_START}" --relax-scale "${RELAX_SCALE}" --p-target "${P_TARGET}"
  --z-bbn-clamp "${Z_BBN_CLAMP}"
  --z-boost-start-list "${Z_BOOST_START_LIST}"
  --A-min "${A_MIN}" --A-max "${A_MAX}" --A-step "${A_STEP}"
  --transition-width "${TRANSITION_WIDTH}"
  --n-dm "${N_DM}" --n-rs "${N_RS}"
  --H0 "${H0}" --Omega-m "${OMEGA_M}"
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}"
  --Neff "${NEFF}" --Tcmb-K "${TCMB_K}"
)
if [[ -n "${RS_STAR_CALIBRATION}" ]]; then
  cmd+=( --rs-star-calibration "${RS_STAR_CALIBRATION}" )
fi

(cd "${ROOT_DIR}" && "${cmd[@]}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-highz-hboost] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"

  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/tables/"*.txt "${PAPER_ASSETS_DIR}/tables/" 2>/dev/null || true
  cp -f "${RESULTS_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  echo "[reproduce-e2-highz-hboost] zipping: ${ZIP_OUT}"
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

echo "[reproduce-e2-highz-hboost] done"

