#!/usr/bin/env bash
set -euo pipefail

# E2.5 drift ↔ CMB closure correlation reproduction entrypoint (Option 2, v11.0.0).
#
# Produces:
# - E2.4: dm/rs closure scan (strict CHW2018 distance priors; diagnostic-only)
# - E2.5: correlation between drift amplitudes (Delta v) and required closure knobs
#
# Outputs are intentionally isolated from the canonical late-time paper build:
#   - results:      v11.0.0/results/diagnostic_drift_cmb_correlation/
#   - paper assets: v11.0.0/paper_assets_drift_cmb_correlation/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/diagnostic_drift_cmb_correlation"
SCAN_DIR="${RESULTS_DIR}/e2_4_scan"
CORR_DIR="${RESULTS_DIR}/corr"

PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_drift_cmb_correlation"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_drift_cmb_correlation_r2.zip"

CMB_CSV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
CMB_COV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

# Fixed Planck-like early-time inputs (bridge diagnostics).
OMEGA_B_H2="0.02237"
OMEGA_C_H2="0.1200"
NEFF="3.046"
TCMB_K="2.7255"

# Fixed late-time parameters (diagnostic; not a fit).
H0="67.4"
OMEGA_M="0.315"
OMEGA_L="0.685"

# E2.4 scan defaults (coarse, deterministic).
BRIDGE_ZS="5,10"
P_GRID="0.55,0.6,0.65,0.7,0.75,0.8,0.9"
ZTRANS_GRID="0.8,1.2,1.5,1.8,2.2,3.0,4.0"

# Drift evaluation defaults (Delta v over YEARS).
YEARS="10"
ZS="2,3,4,5"
TOP_N="20"

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
    --p-grid)
      P_GRID="${2:-}"
      shift 2
      ;;
    --ztrans-grid)
      ZTRANS_GRID="${2:-}"
      shift 2
      ;;
    --years)
      YEARS="${2:-}"
      shift 2
      ;;
    --zs)
      ZS="${2:-}"
      shift 2
      ;;
    --top-n)
      TOP_N="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--bridge-zs CSV] [--p-grid CSV] [--ztrans-grid CSV]
          [--years YEARS] [--zs CSV] [--top-n N]

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
      echo "[reproduce-e2-drift-corr] bootstrapping v11.0.0 venv..."
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
    echo "[reproduce-e2-drift-corr] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
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

mkdir -p "${RESULTS_DIR}" "${SCAN_DIR}" "${CORR_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[reproduce-e2-drift-corr] python=${PY}"
echo "[reproduce-e2-drift-corr] results_dir=${RESULTS_DIR}"
echo "[reproduce-e2-drift-corr] scan: bridge_zs=${BRIDGE_ZS}  p_grid=${P_GRID}  ztrans_grid=${ZTRANS_GRID}"
echo "[reproduce-e2-drift-corr] drift eval: years=${YEARS}  zs=${ZS}"
echo "[reproduce-e2-drift-corr] sync_paper_assets=${SYNC_PAPER_ASSETS}  zip_out=${ZIP_OUT}"

echo "[reproduce-e2-drift-corr] running E2.4 closure scan (inputs for correlation)..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_dm_rs_fit_scan.py" \
  --cmb "${CMB_CSV}" --cmb-cov "${CMB_COV}" \
  --H0 "${H0}" --Omega-m "${OMEGA_M}" --Omega-L "${OMEGA_L}" \
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}" --Neff "${NEFF}" --Tcmb-K "${TCMB_K}" \
  --bridge-zs "${BRIDGE_ZS}" --p-grid "${P_GRID}" --ztrans-grid "${ZTRANS_GRID}" \
  --outdir "${SCAN_DIR}")

SCAN_CSV="${SCAN_DIR}/tables/cmb_e2_dm_rs_fit_scan.csv"
SCAN_MANIFEST="${SCAN_DIR}/manifest.json"

echo "[reproduce-e2-drift-corr] running E2.5 drift ↔ closure correlation..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_drift_cmb_correlation.py" \
  --scan-csv "${SCAN_CSV}" \
  --scan-manifest "${SCAN_MANIFEST}" \
  --years "${YEARS}" \
  --zs "${ZS}" \
  --top-n "${TOP_N}" \
  --outdir "${CORR_DIR}")

echo "[reproduce-e2-drift-corr] writing bundle manifest..."
(cd "${ROOT_DIR}" && RESULTS_DIR="${RESULTS_DIR}" "${PY}" - <<'PY'
import json
import os
from pathlib import Path

results_dir = Path(os.environ["RESULTS_DIR"])
scan = results_dir / "e2_4_scan" / "manifest.json"
corr = results_dir / "corr" / "manifest.json"
out = results_dir / "manifest.json"

obj = {
  "diagnostic_only": True,
  "kind": "cmb_e2_drift_cmb_correlation_bundle",
  "inputs": {
    "e2_4_scan_manifest": str(scan),
    "e2_5_corr_manifest": str(corr),
  },
  "e2_4_scan": json.loads(scan.read_text(encoding="utf-8")),
  "e2_5_corr": json.loads(corr.read_text(encoding="utf-8")),
}
out.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
print("WROTE", out)
PY
)

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-drift-corr] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"

  cp -f "${CORR_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${CORR_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"

  # Pack-level manifest for the zip (includes run provenance + grid spec).
  (cd "${ROOT_DIR}" && ROOT_DIR="${ROOT_DIR}" PAPER_ASSETS_DIR="${PAPER_ASSETS_DIR}" RESULTS_DIR="${RESULTS_DIR}" "${PY}" - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
pa = Path(os.environ["PAPER_ASSETS_DIR"])
results_dir = Path(os.environ["RESULTS_DIR"])

scan_manifest = results_dir / "e2_4_scan" / "manifest.json"
corr_manifest = results_dir / "corr" / "manifest.json"
out = pa / "manifest.json"

def rel(p: Path) -> str:
  try:
    return str(p.resolve().relative_to(root.resolve()))
  except Exception:
    return str(p.name)

scan = json.loads(scan_manifest.read_text(encoding="utf-8"))
corr = json.loads(corr_manifest.read_text(encoding="utf-8"))

tables = sorted([rel(p) for p in (pa / "tables").glob("*") if p.is_file()])
figs = sorted([rel(p) for p in (pa / "figures").glob("*") if p.is_file()])

obj = {
  "diagnostic_only": True,
  "kind": "paper_assets_cmb_e2_drift_cmb_correlation",
  "generated_utc": "1980-01-01T00:00:00Z",
  "git_commit": corr.get("git_commit") or scan.get("git_commit") or "<unknown>",
  "git_branch": corr.get("git_branch") or scan.get("git_branch") or "<unknown>",
  "inputs": {
    "e2_4_scan_manifest": rel(scan_manifest),
    "e2_5_corr_manifest": rel(corr_manifest),
  },
  "e2_4_scan": scan,
  "e2_5_corr": corr,
  "contents": {
    "tables": tables,
    "figures": figs,
  },
  "notes": [
    "Diagnostic-only paper-assets snapshot for the E2.5 drift ↔ CMB closure correlation.",
    "This must not be mixed into canonical late-time submission bundles.",
  ],
}
out.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
print("WROTE", out)
PY
  )

  echo "[reproduce-e2-drift-corr] zipping: ${ZIP_OUT}"
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

echo "[reproduce-e2-drift-corr] done"
