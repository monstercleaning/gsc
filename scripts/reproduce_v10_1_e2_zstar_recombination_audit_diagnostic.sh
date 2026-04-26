#!/usr/bin/env bash
set -euo pipefail

# E2.9 z* / r_s(z*) definition audit (Hu–Sugiyama vs Peebles-style recombination) reproduction entrypoint.
#
# Outputs are intentionally isolated from canonical late-time paper builds:
#   - results:      v11.0.0/results/diagnostic_zstar_recombination_audit/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_zstar_recombination_audit_diagnostic/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_zstar_recombination_audit"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_zstar_recombination_audit_diagnostic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_zstar_recombination_audit_diagnostic_r0.zip"

# Planck-like defaults.
H0="67.4"
OMEGA_M="0.315"
OMEGA_B_H2="0.02237"
OMEGA_C_H2="0.1200"
NEFF="3.046"
TCMB_K="2.7255"
YP="0.245"

# Numerics (diagnostic).
N_RS="8192"
Z_MAX="3000"
Z_MIN_ODE="200"
N_GRID="8192"
ODE_METHOD="fixed_rk4_u"

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
    --n-grid)
      N_GRID="${2:-}"
      shift 2
      ;;
    --ode-method)
      ODE_METHOD="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH] [--n-grid N] [--ode-method METHOD]

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
  if [[ ! -x "${PY_V101}" || "${GSC_FORCE_BOOTSTRAP:-0}" == "1" ]]; then
    if [[ "${GSC_SKIP_BOOTSTRAP:-0}" != "1" ]]; then
      echo "[reproduce-e2-zstar] bootstrapping v11.0.0 venv..."
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
    echo "[reproduce-e2-zstar] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
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

echo "[reproduce-e2-zstar] python=${PY}"
echo "[reproduce-e2-zstar] results_dir=${RESULTS_DIR}"
echo "[reproduce-e2-zstar] sync_paper_assets=${SYNC_PAPER_ASSETS}  zip_out=${ZIP_OUT}"

echo "[reproduce-e2-zstar] running audit..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_zstar_recombination_audit.py" \
  --outdir "${RESULTS_DIR}" \
  --H0 "${H0}" --Omega-m "${OMEGA_M}" \
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}" \
  --Neff "${NEFF}" --Tcmb-K "${TCMB_K}" --Yp "${YP}" \
  --n-rs "${N_RS}" --z-max "${Z_MAX}" --z-min-ode "${Z_MIN_ODE}" --n-grid "${N_GRID}" --ode-method "${ODE_METHOD}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-zstar] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"

  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/tables/"*.txt "${PAPER_ASSETS_DIR}/tables/" 2>/dev/null || true
  cp -f "${RESULTS_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  echo "[reproduce-e2-zstar] zipping: ${ZIP_OUT}"
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

echo "[reproduce-e2-zstar] done"
