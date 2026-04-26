#!/usr/bin/env bash
set -euo pipefail

# Redshift-drift forecast (systematic floor) diagnostic reproduction entrypoint (v11.0.0).
#
# Outputs are isolated from canonical late-time paper builds:
#   - results:      v11.0.0/results/diagnostic_drift_forecast/
#   - paper assets: v11.0.0/paper_assets_drift_forecast_diagnostic/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_drift_forecast"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_drift_forecast_diagnostic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_drift_forecast_diagnostic_r0.zip"

SYNC_PAPER_ASSETS="0"
ZIP_OUT="${ZIP_OUT_DEFAULT}"

YEARS="1:40:1"
Z_TARGETS="2.0,2.5,3.0,3.5,4.5"
SIGMA_STAT="1.0"
SIGMA_SYS_LIST="0.5,1.0,2.0"

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
    --years)
      YEARS="${2:-}"
      shift 2
      ;;
    --z-targets)
      Z_TARGETS="${2:-}"
      shift 2
      ;;
    --sigma-stat)
      SIGMA_STAT="${2:-}"
      shift 2
      ;;
    --sigma-sys-list)
      SIGMA_SYS_LIST="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--years SPEC] [--z-targets SPEC]
          [--sigma-stat CM_S] [--sigma-sys-list CSV]

Defaults:
  --years '${YEARS}'
  --z-targets '${Z_TARGETS}'
  --sigma-stat '${SIGMA_STAT}'
  --sigma-sys-list '${SIGMA_SYS_LIST}'

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
    echo "[drift-forecast] bootstrap venv"
    if bash "${V101_DIR}/scripts/bootstrap_venv.sh"; then
      if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
        PY="${PY_V101}"
      fi
    fi
  fi
fi

if [[ -z "${PY}" ]]; then
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[drift-forecast] WARNING: falling back to Phase10 venv python"
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need matplotlib)." >&2
    exit 1
  fi
fi

mkdir -p "${RESULTS_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[drift-forecast] python=${PY}"
echo "[drift-forecast] outdir=${RESULTS_DIR}"
echo "[drift-forecast] years=${YEARS}  z_targets=${Z_TARGETS}"
echo "[drift-forecast] sigma_stat=${SIGMA_STAT}  sigma_sys_list=${SIGMA_SYS_LIST}"
echo "[drift-forecast] sync_paper_assets=${SYNC_PAPER_ASSETS}  zip_out=${ZIP_OUT}"

ARGS=()
IFS=',' read -r -a SYS_ARR <<< "${SIGMA_SYS_LIST}"
for s in "${SYS_ARR[@]}"; do
  s_trim="$(echo "${s}" | xargs)"
  if [[ -n "${s_trim}" ]]; then
    ARGS+=(--sigma-sys-cm-s "${s_trim}")
  fi
done

(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/drift_forecast_fisher.py" \
  --outdir "${RESULTS_DIR}" \
  --years "${YEARS}" --z-targets "${Z_TARGETS}" \
  --sigma-stat-cm-s "${SIGMA_STAT}" \
  "${ARGS[@]}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[drift-forecast] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"
  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  if compgen -G "${RESULTS_DIR}/figures/*.png" >/dev/null; then
    cp -f "${RESULTS_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  fi
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  echo "[drift-forecast] zipping: ${ZIP_OUT}"
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

echo "[drift-forecast] done"

