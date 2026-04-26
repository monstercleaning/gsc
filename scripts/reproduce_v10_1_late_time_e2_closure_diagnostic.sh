#!/usr/bin/env bash
set -euo pipefail

# E2 closure diagnostic reproduction entrypoint (Option 2, v11.0.0).
#
# Produces:
# - E2.3: effective mapping dm_star_calibration -> constant H(z) boost above z_boost_start
# - E2.4: coarse scan of (dm_fit, rs_fit) required to reconcile strict CHW2018 priors
#
# Outputs are intentionally isolated from the canonical late-time paper build:
#   - results:      v11.0.0/results/late_time_fit_cmb_e2_closure_diagnostic/
#   - paper assets: v11.0.0/paper_assets_cmb_e2_closure_diagnostic/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/late_time_fit_cmb_e2_closure_diagnostic"
HBOOST_DIR="${RESULTS_DIR}/hboost"
SCAN_DIR="${RESULTS_DIR}/scan"

PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e2_closure_diagnostic"
ZIP_OUT_DEFAULT="${V101_DIR}/paper_assets_cmb_e2_closure_diagnostic_r1.zip"

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
GSC_P="0.6"
GSC_ZTRANS="1.8"

# E2.2 diagnostic snapshot dm-fit used for the E2.3 mapping (out-of-scope closure knob).
DM_STAR_CALIB="0.9290939714464278"

# E2.4 scan defaults.
BRIDGE_ZS="5,10"
P_GRID="0.55,0.6,0.65,0.7,0.75,0.8,0.9"
ZTRANS_GRID="0.8,1.2,1.5,1.8,2.2,3.0,4.0"

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
    --dm-star-calib)
      DM_STAR_CALIB="${2:-}"
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
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--sync-paper-assets] [--zip-out PATH]
          [--dm-star-calib DM] [--bridge-zs CSV] [--p-grid CSV] [--ztrans-grid CSV]

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
      echo "[reproduce-e2-closure] bootstrapping v11.0.0 venv..."
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
    echo "[reproduce-e2-closure] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
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

mkdir -p "${RESULTS_DIR}" "${HBOOST_DIR}" "${SCAN_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[reproduce-e2-closure] python=${PY}"
echo "[reproduce-e2-closure] knobs:"
echo "  results_dir=${RESULTS_DIR}"
echo "  sync_paper_assets=${SYNC_PAPER_ASSETS}  paper_assets_dir=${PAPER_ASSETS_DIR}"
echo "  zip_out=${ZIP_OUT}"
echo "  model=gsc_transition  gsc_p=${GSC_P}  gsc_ztrans=${GSC_ZTRANS}  bridge_z_used=5"
echo "  dm_star_calib(E2.2 snapshot)=${DM_STAR_CALIB}"
echo "  scan: bridge_zs=${BRIDGE_ZS}  p_grid=${P_GRID}  ztrans_grid=${ZTRANS_GRID}"

echo "[reproduce-e2-closure] running E2.3 hboost mapping..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_distance_closure_to_hboost.py" \
  --model gsc_transition \
  --H0 "${H0}" --Omega-m "${OMEGA_M}" --Omega-L "${OMEGA_L}" \
  --gsc-p "${GSC_P}" --gsc-ztrans "${GSC_ZTRANS}" \
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}" --Neff "${NEFF}" --Tcmb-K "${TCMB_K}" \
  --cmb-bridge-z 5 \
  --dm-star-calib "${DM_STAR_CALIB}" \
  --outdir "${HBOOST_DIR}")

echo "[reproduce-e2-closure] running E2.4 dm/rs closure scan..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/cmb_e2_dm_rs_fit_scan.py" \
  --cmb "${CMB_CSV}" --cmb-cov "${CMB_COV}" \
  --H0 "${H0}" --Omega-m "${OMEGA_M}" --Omega-L "${OMEGA_L}" \
  --omega-b-h2 "${OMEGA_B_H2}" --omega-c-h2 "${OMEGA_C_H2}" --Neff "${NEFF}" --Tcmb-K "${TCMB_K}" \
  --bridge-zs "${BRIDGE_ZS}" --p-grid "${P_GRID}" --ztrans-grid "${ZTRANS_GRID}" \
  --outdir "${SCAN_DIR}")

echo "[reproduce-e2-closure] writing combined manifest..."
(cd "${ROOT_DIR}" && RESULTS_DIR="${RESULTS_DIR}" "${PY}" - <<'PY'
import json
import os
from pathlib import Path

results_dir = Path(os.environ["RESULTS_DIR"])
hboost = results_dir / "hboost" / "manifest.json"
scan = results_dir / "scan" / "manifest.json"
out = results_dir / "manifest.json"

obj = {
  "diagnostic_only": True,
  "kind": "cmb_e2_closure_diagnostic_bundle",
  "inputs": {
    "hboost_manifest": str(hboost),
    "scan_manifest": str(scan),
  },
  "hboost": json.loads(hboost.read_text(encoding="utf-8")),
  "scan": json.loads(scan.read_text(encoding="utf-8")),
}
out.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("WROTE", out)
PY
)

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e2-closure] syncing paper-assets view + zipping..."
  mkdir -p "${PAPER_ASSETS_DIR}/tables" "${PAPER_ASSETS_DIR}/figures"

  # Copy key outputs (paper-assets view is just a convenience snapshot for sharing).
  cp -f "${HBOOST_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${SCAN_DIR}/tables/"*.csv "${PAPER_ASSETS_DIR}/tables/"
  cp -f "${HBOOST_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"
  cp -f "${SCAN_DIR}/figures/"*.png "${PAPER_ASSETS_DIR}/figures/"

  # Write a pack-level manifest for the zip (includes run provenance + grid spec).
  (cd "${ROOT_DIR}" && ROOT_DIR="${ROOT_DIR}" PAPER_ASSETS_DIR="${PAPER_ASSETS_DIR}" HBOOST_DIR="${HBOOST_DIR}" SCAN_DIR="${SCAN_DIR}" "${PY}" - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
pa = Path(os.environ["PAPER_ASSETS_DIR"])
hboost_manifest = Path(os.environ["HBOOST_DIR"]) / "manifest.json"
scan_manifest = Path(os.environ["SCAN_DIR"]) / "manifest.json"
out = pa / "manifest.json"

def rel(p: Path) -> str:
  try:
    return str(p.resolve().relative_to(root.resolve()))
  except Exception:
    return str(p)

hboost = json.loads(hboost_manifest.read_text(encoding="utf-8"))
scan = json.loads(scan_manifest.read_text(encoding="utf-8"))

tables = sorted([rel(p) for p in (pa / "tables").glob("*") if p.is_file()])
figs = sorted([rel(p) for p in (pa / "figures").glob("*") if p.is_file()])

obj = {
  "diagnostic_only": True,
  "kind": "paper_assets_cmb_e2_closure_diagnostic",
  "generated_utc": "1980-01-01T00:00:00Z",
  "git_commit": scan.get("git_commit") or hboost.get("git_commit") or "<unknown>",
  "git_branch": scan.get("git_branch") or hboost.get("git_branch") or "<unknown>",
  "inputs": {
    "hboost_manifest": rel(hboost_manifest),
    "scan_manifest": rel(scan_manifest),
  },
  "e2_3_hboost": hboost,
  "e2_4_scan": scan,
  "contents": {
    "tables": tables,
    "figures": figs,
  },
  "notes": [
    "Diagnostic-only paper-assets snapshot for E2 closure diagnostics (E2.3 + E2.4).",
    "This is not part of the canonical late-time paper assets and must not be mixed into submission bundles.",
  ],
}
out.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("WROTE", out)
PY
  )

  # Create zip with root folder name paper_assets_cmb_e2_closure_diagnostic/.
  (cd "${ROOT_DIR}" && PAPER_ASSETS_DIR="${PAPER_ASSETS_DIR}" ZIP_OUT="${ZIP_OUT}" "${PY}" - <<'PY'
import os
import zipfile
from pathlib import Path

pa = Path(os.environ["PAPER_ASSETS_DIR"])
zip_out = Path(os.environ["ZIP_OUT"])
zip_out.parent.mkdir(parents=True, exist_ok=True)
root_name = pa.name

with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
  for p in sorted(pa.rglob("*")):
    if p.is_dir():
      continue
    if p.name == ".DS_Store" or p.name.startswith("._") or "__MACOSX" in str(p):
      continue
    arc = str(Path(root_name) / p.relative_to(pa))
    zf.write(p, arcname=arc)

print("WROTE", zip_out)
PY
  )
fi

echo "[reproduce-e2-closure] OK"
