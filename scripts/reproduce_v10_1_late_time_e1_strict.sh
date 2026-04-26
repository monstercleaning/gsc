#!/usr/bin/env bash
set -euo pipefail

# E1.1 strict reproduction entrypoint (Option 2, v11.0.0).
#
# This is intentionally separate from reproduce_v10_1_late_time.sh:
# - late-time paper build remains canonical and unchanged
# - E1.1 strict (CHW2018 vector+cov) outputs go to a separate results dir

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/late_time_fit_cmb_e11_strict"
FIG_DIR="${RESULTS_DIR}/figures"

PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e11_strict"

SN_DIR="${V101_DIR}/data/sn/pantheon_plus_shoes"
SN_DAT="${SN_DIR}/Pantheon+SH0ES.dat"
SN_COV="${SN_DIR}/Pantheon+SH0ES_STAT+SYS.cov"
SN_HFLOW_CSV="${SN_DIR}/pantheon_plus_shoes_hflow_mu.csv"

BAO_CSV="${V101_DIR}/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv"
DRIFT_DEFAULT="${V101_DIR}/data/drift/elt_andes_liske_conservative_20yr_asimov.csv"

CMB_CSV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
CMB_COV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

OMEGA_B_H2="0.02235976" # CHW2018 mean
OMEGA_C_H2="0.1200"     # Planck-like default
NEFF="3.046"
TCMB_K="2.7255"

DRIFT_CSV=""
DRIFT_ARGS=()
H0_GRID="67.4"
OMEGA_M_GRID="0.25:0.37:0.005"
SYNC_PAPER_ASSETS="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-drift)
      DRIFT_CSV="${DRIFT_DEFAULT}"
      shift
      ;;
    --sync-paper-assets)
      SYNC_PAPER_ASSETS="1"
      shift
      ;;
    --drift)
      DRIFT_CSV="${2:-}"
      if [[ -z "${DRIFT_CSV}" ]]; then
        echo "ERROR: --drift requires a path" >&2
        exit 2
      fi
      shift 2
      ;;
    --no-drift)
      DRIFT_CSV=""
      shift
      ;;
    --omega-b-h2)
      OMEGA_B_H2="${2:-}"
      shift 2
      ;;
    --omega-c-h2)
      OMEGA_C_H2="${2:-}"
      shift 2
      ;;
    --Neff)
      NEFF="${2:-}"
      shift 2
      ;;
    --Tcmb-K)
      TCMB_K="${2:-}"
      shift 2
      ;;
    --H0-grid)
      H0_GRID="${2:-}"
      shift 2
      ;;
    --Omega-m-grid)
      OMEGA_M_GRID="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--with-drift|--drift PATH|--no-drift] [--sync-paper-assets]
          [--omega-b-h2 X] [--omega-c-h2 X] [--Neff X] [--Tcmb-K X]
          [--H0-grid SPEC] [--Omega-m-grid SPEC]

Outputs:
  - ${RESULTS_DIR}/
  - (optional) ${PAPER_ASSETS_DIR}/
EOF
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "${DRIFT_CSV}" ]]; then
  if [[ ! -f "${DRIFT_CSV}" ]]; then
    echo "Missing expected drift CSV: ${DRIFT_CSV}" >&2
    exit 1
  fi
  # Profile H0 analytically from drift to avoid an expensive H0 grid scan.
  DRIFT_ARGS=(--drift "${DRIFT_CSV}" --profile-H0)
  # In profile mode, --H0-grid defines the admissible bounds for the analytic solution.
  H0_GRID="60:80:0.5"
fi

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

# Prefer a self-contained v11.0.0 virtualenv, but allow a fallback to the Phase10 venv
# when running inside restricted environments (e.g. no pip internet access).
PY_V101="${V101_DIR}/.venv/bin/python"
PY_PHASE10="${V101_DIR}/B/GSC_v10_8_PUBLICATION_BUNDLE/.venv/bin/python"

PY=""
if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
  PY="${PY_V101}"
else
  # Only auto-bootstrap when the venv is missing (or when explicitly forced).
  if [[ ! -x "${PY_V101}" || "${GSC_FORCE_BOOTSTRAP:-0}" == "1" ]]; then
    if [[ "${GSC_SKIP_BOOTSTRAP:-0}" != "1" ]]; then
      echo "[reproduce-e1] bootstrapping v11.0.0 venv..."
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
    echo "Run: bash v11.0.0/scripts/bootstrap_venv.sh" >&2
    exit 1
  fi
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[reproduce-e1] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
    echo "[reproduce-e1] WARNING: for a self-contained setup, run: bash v11.0.0/scripts/bootstrap_venv.sh"
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need numpy+scipy+matplotlib)." >&2
    echo "Tried: ${PY_V101} and ${PY_PHASE10}" >&2
    exit 1
  fi
fi

mkdir -p "${RESULTS_DIR}" "${FIG_DIR}"

# Keep matplotlib caches local and reproducible.
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[reproduce-e1] python=${PY}"

if [[ ! -f "${CMB_CSV}" || ! -f "${CMB_COV}" ]]; then
  echo "Missing expected CHW2018 CMB priors files:" >&2
  echo "  ${CMB_CSV}" >&2
  echo "  ${CMB_COV}" >&2
  exit 1
fi

if [[ ! -f "${SN_DAT}" || ! -f "${SN_COV}" ]]; then
  echo "[reproduce-e1] fetching Pantheon+SH0ES raw files..."
  (cd "${ROOT_DIR}" && bash "${V101_DIR}/scripts/fetch_pantheon_plus_shoes.sh")
fi

echo "[reproduce-e1] converting Pantheon+SH0ES .dat -> CSVs..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/pantheon_plus_shoes_to_csv.py")

if [[ ! -f "${SN_HFLOW_CSV}" ]]; then
  echo "Missing expected CSV: ${SN_HFLOW_CSV}" >&2
  exit 1
fi

if [[ ! -f "${BAO_CSV}" ]]; then
  echo "Missing expected BAO CSV: ${BAO_CSV}" >&2
  exit 1
fi

echo "[reproduce-e1] fit: lcdm (E1.1 strict: CHW2018 vector+cov)"
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/late_time_fit_grid.py" \
  --model lcdm \
  --sn "${SN_HFLOW_CSV}" --sn-cov "${SN_COV}" \
  --bao "${BAO_CSV}" \
  ${DRIFT_ARGS[@]+"${DRIFT_ARGS[@]}"} \
  --H0-grid "${H0_GRID}" \
  --Omega-m-grid "${OMEGA_M_GRID}" \
  --rd-mode early --rd-method eisenstein_hu_1998 \
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}" --Neff "${NEFF}" --Tcmb-K "${TCMB_K}" \
  --cmb "${CMB_CSV}" --cmb-cov "${CMB_COV}" --cmb-mode distance_priors \
  --two-pass --two-pass-top 2000 --top-k 2000 \
  --out-dir "${RESULTS_DIR}")

echo "[reproduce-e1] figures + summary"
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/late_time_make_figures.py" \
  --fit-dir "${RESULTS_DIR}" \
  --models "lcdm")

echo "[reproduce-e1] confidence regions"
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/late_time_make_confidence.py" \
  --fit-dir "${RESULTS_DIR}" \
  --models "lcdm")

echo "[reproduce-e1] tables (LaTeX)"
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/late_time_make_tables.py" \
  --fit-dir "${RESULTS_DIR}")

echo "[reproduce-e1] manifest"
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/late_time_make_manifest.py" \
  --fit-dir "${RESULTS_DIR}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e1] sync paper assets"
  (cd "${ROOT_DIR}" && bash "${V101_DIR}/scripts/sync_paper_assets.sh" "${RESULTS_DIR}" "${PAPER_ASSETS_DIR}")
fi

echo "[reproduce-e1] done"
echo "results: ${RESULTS_DIR}"
echo "figures: ${FIG_DIR}"

