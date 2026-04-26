#!/usr/bin/env bash
set -euo pipefail

# E2.10 drift-constrained closure Pareto bound (diagnostic-only).
#
# Outputs:
#   - results:      v11.0.0/results/diagnostic_cmb_drift_constrained_bound/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_drift_constrained_closure_bound/  (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_cmb_drift_constrained_bound"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_drift_constrained_closure_bound"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_drift_constrained_closure_bound_r0.zip"

CMB_CSV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
CMB_COV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

# Canonical diagnostic checkpoint defaults.
H0="67.4"
OMEGA_M="0.315"
OMEGA_B_H2="0.02237"
OMEGA_C_H2="0.1200"
NEFF="3.046"
TCMB_K="2.7255"
GSC_P="0.6"
GSC_ZTRANS="1.8"

Z_WINDOW_MIN="2.0"
Z_WINDOW_MAX="5.0"
Z_HANDOFF="5.0"
EPSILON_CAP="1e-6"
S_GRID=""

N_DM="8192"
N_RS="8192"
RS_STAR_CALIBRATION=""

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
    --s-grid)
      S_GRID="${2:-}"
      shift 2
      ;;
    --epsilon-cap)
      EPSILON_CAP="${2:-}"
      shift 2
      ;;
    --z-handoff)
      Z_HANDOFF="${2:-}"
      shift 2
      ;;
    --z-window-min)
      Z_WINDOW_MIN="${2:-}"
      shift 2
      ;;
    --z-window-max)
      Z_WINDOW_MAX="${2:-}"
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
          [--s-grid CSV] [--epsilon-cap X]
          [--z-window-min X] [--z-window-max X] [--z-handoff X]
          [--gsc-p P] [--gsc-ztrans ZT]
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
  if [[ "${GSC_SKIP_BOOTSTRAP:-0}" != "1" ]]; then
    echo "[reproduce-e2-drift-bound] bootstrap venv"
    if bash "${V101_DIR}/scripts/bootstrap_venv.sh"; then
      if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
        PY="${PY_V101}"
      fi
    fi
  fi
fi

if [[ -z "${PY}" ]]; then
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[reproduce-e2-drift-bound] WARNING: falling back to Phase10 venv python"
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need numpy+matplotlib)." >&2
    exit 1
  fi
fi

if [[ ! -f "${CMB_CSV}" || ! -f "${CMB_COV}" ]]; then
  echo "ERROR: missing CHW2018 files:" >&2
  echo "  ${CMB_CSV}" >&2
  echo "  ${CMB_COV}" >&2
  exit 1
fi

mkdir -p "${RESULTS_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[reproduce-e2-drift-bound] python=${PY}"
echo "[reproduce-e2-drift-bound] outdir=${RESULTS_DIR}"
echo "[reproduce-e2-drift-bound] model: p=${GSC_P} z_transition=${GSC_ZTRANS}"
echo "[reproduce-e2-drift-bound] window: [${Z_WINDOW_MIN},${Z_WINDOW_MAX}] handoff=${Z_HANDOFF} epsilon_cap=${EPSILON_CAP}"
if [[ -n "${S_GRID}" ]]; then
  echo "[reproduce-e2-drift-bound] s_grid=${S_GRID}"
fi

cmd=( "${PY}" "${V101_DIR}/scripts/cmb_e2_drift_constrained_closure_bound.py"
  --cmb "${CMB_CSV}" --cmb-cov "${CMB_COV}"
  --outdir "${RESULTS_DIR}"
  --gsc-p "${GSC_P}" --gsc-ztrans "${GSC_ZTRANS}"
  --H0 "${H0}" --Omega-m "${OMEGA_M}"
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}"
  --Neff "${NEFF}" --Tcmb-K "${TCMB_K}"
  --z-window-min "${Z_WINDOW_MIN}" --z-window-max "${Z_WINDOW_MAX}" --z-handoff "${Z_HANDOFF}"
  --epsilon-cap "${EPSILON_CAP}"
  --n-dm "${N_DM}" --n-rs "${N_RS}"
)
if [[ -n "${S_GRID}" ]]; then
  cmd+=( --s-grid "${S_GRID}" )
fi
if [[ -n "${RS_STAR_CALIBRATION}" ]]; then
  cmd+=( --rs-star-calibration "${RS_STAR_CALIBRATION}" )
fi

(cd "${ROOT_DIR}" && "${cmd[@]}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-drift-bound] syncing paper-assets view + zipping..."
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

echo "[reproduce-e2-drift-bound] done"
