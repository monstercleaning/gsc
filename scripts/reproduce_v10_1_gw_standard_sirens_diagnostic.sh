#!/usr/bin/env bash
set -euo pipefail

# GW standard-sirens diagnostic reproduction entrypoint (v11.0.0).
#
# Outputs are intentionally isolated from canonical late-time paper builds:
#   - results:      v11.0.0/results/diagnostic_gw_standard_sirens/
#   - paper assets: v11.0.0/paper_assets_gw_standard_sirens/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_gw_standard_sirens"
PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_gw_standard_sirens"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_gw_standard_sirens_diagnostic_r2.zip"

MODE="xi0_n"
XI0="0.9"
XI_N="2.0"
DELTA0="0.1"
ALPHAM0="0.0"
Z_MAX="5.0"
DZ="0.05"
N_INT="10000"

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
    --delta0)
      DELTA0="${2:-}"
      shift 2
      ;;
    --alphaM0)
      ALPHAM0="${2:-}"
      shift 2
      ;;
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --xi0)
      XI0="${2:-}"
      shift 2
      ;;
    --xi-n)
      XI_N="${2:-}"
      shift 2
      ;;
    --z-max)
      Z_MAX="${2:-}"
      shift 2
      ;;
    --dz)
      DZ="${2:-}"
      shift 2
      ;;
    --n-int)
      N_INT="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--mode xi0_n|friction] [--xi0 X0] [--xi-n N] [--delta0 D0] [--alphaM0 A0]
          [--z-max Z] [--dz DZ] [--n-int N]

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
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[reproduce-gw-sirens] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
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

echo "[reproduce-gw-sirens] python=${PY}"
echo "[reproduce-gw-sirens] results_dir=${RESULTS_DIR}"
echo "[reproduce-gw-sirens] mode=${MODE} xi0=${XI0} xi_n=${XI_N} delta0=${DELTA0} alphaM0=${ALPHAM0}"
echo "[reproduce-gw-sirens] z_max=${Z_MAX} dz=${DZ} n_int=${N_INT}"
echo "[reproduce-gw-sirens] sync_paper_assets=${SYNC_PAPER_ASSETS} zip_out=${ZIP_OUT}"

echo "[reproduce-gw-sirens] running diagnostic script..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/gw_standard_sirens_diagnostic.py" \
  --outdir "${RESULTS_DIR}" \
  --mode "${MODE}" \
  --xi0 "${XI0}" \
  --xi-n "${XI_N}" \
  --delta0 "${DELTA0}" \
  --alphaM0 "${ALPHAM0}" \
  --z-max "${Z_MAX}" \
  --dz "${DZ}" \
  --n-int "${N_INT}")

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-gw-sirens] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"

  cp -f "${RESULTS_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${RESULTS_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"

  echo "[reproduce-gw-sirens] zipping: ${ZIP_OUT}"
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

echo "[reproduce-gw-sirens] done"
