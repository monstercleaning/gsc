#!/usr/bin/env bash
set -euo pipefail

# E1.3 diagnostic reproduction entrypoint (Option 2, v11.0.0).
#
# This script produces a sensitivity scan of compressed CMB chi2 vs `bridge_z`
# for non-LCDM late-time histories, using the strict CHW2018 distance-priors
# vector+cov input (no sigma_theory by default).
#
# Outputs are intentionally isolated from the canonical late-time paper build:
#   - results:      v11.0.0/results/late_time_fit_cmb_e13_diagnostic/
#   - paper assets: v11.0.0/paper_assets_cmb_e13_diagnostic/   (opt-in)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${V101_DIR}/results/late_time_fit_cmb_e13_diagnostic"
FIG_DIR="${RESULTS_DIR}/figures"

PAPER_ASSETS_DIR="${V101_DIR}/paper_assets_cmb_e13_diagnostic"

SN_DIR="${V101_DIR}/data/sn/pantheon_plus_shoes"
SN_DAT="${SN_DIR}/Pantheon+SH0ES.dat"
SN_COV="${SN_DIR}/Pantheon+SH0ES_STAT+SYS.cov"
SN_HFLOW_CSV="${SN_DIR}/pantheon_plus_shoes_hflow_mu.csv"

BAO_CSV="${V101_DIR}/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv"
DRIFT_DEFAULT="${V101_DIR}/data/drift/elt_andes_liske_conservative_20yr_asimov.csv"

CMB_CSV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
CMB_COV="${V101_DIR}/data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

# Fixed early-time inputs for the bridge scan (Planck-like).
OMEGA_B_H2="0.02237"
OMEGA_C_H2="0.1200"
NEFF="3.046"
TCMB_K="2.7255"
RD_METHOD="eisenstein_hu_1998"

# Fixed late-time parameters (diagnostic run; not a fit).
H0="67.4"
OMEGA_M="0.315"
OMEGA_L="0.685"
GSC_P="0.6"
GSC_ZTRANS="1.8"
# r2: dense scan around the critical low bridge region for gsc_transition
BRIDGE_ZS="0.5,1,1.5,2,2.5,3,4,5,7.5,10,20,50,100"
# keep powerlaw only as a cheap "fails hard" curve
BRIDGE_ZS_POWERLAW="2,5,10,20,50,100"

DRIFT_CSV=""
SYNC_PAPER_ASSETS="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-drift)
      DRIFT_CSV="${DRIFT_DEFAULT}"
      shift
      ;;
    --no-drift)
      DRIFT_CSV=""
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
    --sync-paper-assets)
      SYNC_PAPER_ASSETS="1"
      shift
      ;;
    --bridge-z)
      BRIDGE_ZS="${2:-}"
      shift 2
      ;;
    --bridge-z-powerlaw)
      BRIDGE_ZS_POWERLAW="${2:-}"
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
    --H0)
      H0="${2:-}"
      shift 2
      ;;
    --Omega-m)
      OMEGA_M="${2:-}"
      shift 2
      ;;
    --Omega-L)
      OMEGA_L="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat >&2 <<EOF
Usage: $0 [--with-drift|--no-drift|--drift PATH] [--sync-paper-assets]
          [--bridge-z CSV] [--gsc-p P] [--gsc-ztrans ZT]
          [--H0 H0] [--Omega-m Om] [--Omega-L OL]

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
      echo "[reproduce-e1.3] bootstrapping v11.0.0 venv..."
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
    echo "[reproduce-e1.3] WARNING: falling back to Phase10 venv python (v11.0.0/.venv is missing or incomplete)."
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need numpy+scipy+matplotlib)." >&2
    exit 1
  fi
fi

mkdir -p "${RESULTS_DIR}" "${FIG_DIR}"
export MPLCONFIGDIR="${RESULTS_DIR}/.mplconfig"
mkdir -p "${MPLCONFIGDIR}"
export MPLBACKEND="Agg"

echo "[reproduce-e1.3] python=${PY}"
echo "[reproduce-e1.3] knobs:"
echo "  results_dir=${RESULTS_DIR}"
echo "  sync_paper_assets=${SYNC_PAPER_ASSETS}  paper_assets_dir=${PAPER_ASSETS_DIR}"
echo "  base_models=gsc_powerlaw,gsc_transition"
echo "  gsc_p=${GSC_P}  gsc_ztrans=${GSC_ZTRANS}"
echo "  H0=${H0}  Omega_m=${OMEGA_M}  Omega_L=${OMEGA_L}"
echo "  bridge_zs_transition=${BRIDGE_ZS}"
echo "  bridge_zs_powerlaw=${BRIDGE_ZS_POWERLAW}"
echo "  rd_mode=early  rd_method=${RD_METHOD}"
echo "  early_params: omega_b_h2=${OMEGA_B_H2} omega_c_h2=${OMEGA_C_H2} Neff=${NEFF} Tcmb_K=${TCMB_K}"
echo "  cmb_csv=${CMB_CSV}"
echo "  cmb_cov=${CMB_COV}"
RS_STAR_CALIB="$("${PY}" - <<'PY' 2>/dev/null || true
import sys
from pathlib import Path
sys.path.insert(0, str(Path("v11.0.0").resolve()))
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018
print(float(_RS_STAR_CALIB_CHW2018))
PY
)"
if [[ -n "${RS_STAR_CALIB}" ]]; then
  echo "  rs_star_calibration(CHW2018)=${RS_STAR_CALIB} (applied to r_s(z*) only)"
fi

if [[ ! -f "${CMB_CSV}" || ! -f "${CMB_COV}" ]]; then
  echo "Missing expected CHW2018 CMB priors files:" >&2
  echo "  ${CMB_CSV}" >&2
  echo "  ${CMB_COV}" >&2
  exit 1
fi

if [[ ! -f "${SN_DAT}" || ! -f "${SN_COV}" ]]; then
  echo "[reproduce-e1.3] fetching Pantheon+SH0ES raw files..."
  (cd "${ROOT_DIR}" && bash "${V101_DIR}/scripts/fetch_pantheon_plus_shoes.sh")
fi

echo "[reproduce-e1.3] converting Pantheon+SH0ES .dat -> CSVs..."
(cd "${ROOT_DIR}" && "${PY}" "${V101_DIR}/scripts/pantheon_plus_shoes_to_csv.py")

if [[ ! -f "${SN_HFLOW_CSV}" ]]; then
  echo "Missing expected CSV: ${SN_HFLOW_CSV}" >&2
  exit 1
fi
if [[ ! -f "${BAO_CSV}" ]]; then
  echo "Missing expected BAO CSV: ${BAO_CSV}" >&2
  exit 1
fi

DRIFT_ARGS=()
if [[ -n "${DRIFT_CSV}" ]]; then
  if [[ ! -f "${DRIFT_CSV}" ]]; then
    echo "Missing expected drift CSV: ${DRIFT_CSV}" >&2
    exit 1
  fi
  DRIFT_ARGS=(--drift "${DRIFT_CSV}")
fi

echo "[reproduce-e1.3] scan: gsc_powerlaw + gsc_transition (bridge_z=${BRIDGE_ZS})"
if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  "${PY}" "${V101_DIR}/scripts/cmb_bridge_scan_e1_3.py" \
    --out-dir "${RESULTS_DIR}" \
    --sync-paper-assets-dir "${PAPER_ASSETS_DIR}" \
    --sn "${SN_HFLOW_CSV}" \
    --sn-cov "${SN_COV}" \
    --bao "${BAO_CSV}" \
    ${DRIFT_ARGS[@]+"${DRIFT_ARGS[@]}"} \
    --cmb "${CMB_CSV}" \
    --cmb-cov "${CMB_COV}" \
    --bridge-z "${BRIDGE_ZS}" \
    --bridge-z-powerlaw "${BRIDGE_ZS_POWERLAW}" \
    --H0 "${H0}" \
    --Omega-m "${OMEGA_M}" \
    --Omega-L "${OMEGA_L}" \
    --gsc-p "${GSC_P}" \
    --gsc-ztrans "${GSC_ZTRANS}" \
    --omega-b-h2 "${OMEGA_B_H2}" \
    --omega-c-h2 "${OMEGA_C_H2}" \
    --Neff "${NEFF}" \
    --Tcmb-K "${TCMB_K}" \
    --rd-method "${RD_METHOD}"
else
  "${PY}" "${V101_DIR}/scripts/cmb_bridge_scan_e1_3.py" \
    --out-dir "${RESULTS_DIR}" \
    --sn "${SN_HFLOW_CSV}" \
    --sn-cov "${SN_COV}" \
    --bao "${BAO_CSV}" \
    ${DRIFT_ARGS[@]+"${DRIFT_ARGS[@]}"} \
    --cmb "${CMB_CSV}" \
    --cmb-cov "${CMB_COV}" \
    --bridge-z "${BRIDGE_ZS}" \
    --bridge-z-powerlaw "${BRIDGE_ZS_POWERLAW}" \
    --H0 "${H0}" \
    --Omega-m "${OMEGA_M}" \
    --Omega-L "${OMEGA_L}" \
    --gsc-p "${GSC_P}" \
    --gsc-ztrans "${GSC_ZTRANS}" \
    --omega-b-h2 "${OMEGA_B_H2}" \
    --omega-c-h2 "${OMEGA_C_H2}" \
    --Neff "${NEFF}" \
    --Tcmb-K "${TCMB_K}" \
    --rd-method "${RD_METHOD}"
fi

TABLES_DIR="${RESULTS_DIR}/tables"
mkdir -p "${TABLES_DIR}"
if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  mkdir -p "${PAPER_ASSETS_DIR}/tables"
fi

BEST_BRIDGE_Z="$("${PY}" - <<PY 2>/dev/null || true
import csv, math
from pathlib import Path
p = Path(r"${RESULTS_DIR}") / "cmb_bridge_scan.csv"
best = None
with p.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        if (row.get("base_model") or "").strip() != "gsc_transition":
            continue
        is_deg = (row.get("is_degenerate") or "").strip().lower() in ("1", "true", "yes", "y")
        if is_deg:
            # Degenerate points are LCDM-only for the CMB distance integral and
            # are not meaningful diagnostics of the powerlaw segment.
            continue
        try:
            chi = float(row.get("chi2_cmb") or "nan")
            zb = float(row.get("bridge_z") or row.get("bridge_z_requested") or "nan")
        except Exception:
            continue
        if not (math.isfinite(chi) and math.isfinite(zb)):
            continue
        if best is None or chi < best[0]:
            best = (chi, zb)
if best is None:
    raise SystemExit(1)
print(best[1])
PY
)"

if [[ -n "${BEST_BRIDGE_Z}" ]]; then
  echo "[reproduce-e1.3] best (gsc_transition) bridge_z=${BEST_BRIDGE_Z} (min chi2_cmb)"
  DEBUG_OUT="${TABLES_DIR}/cmb_best_debug.txt"
  "${PY}" "${V101_DIR}/scripts/late_time_scorecard.py" \
    --model gsc_transition \
    --H0 "${H0}" \
    --Omega-m "${OMEGA_M}" \
    --Omega-L "${OMEGA_L}" \
    --gsc-p "${GSC_P}" \
    --gsc-ztrans "${GSC_ZTRANS}" \
    --sn "${SN_HFLOW_CSV}" \
    --sn-cov "${SN_COV}" \
    --bao "${BAO_CSV}" \
    ${DRIFT_ARGS[@]+"${DRIFT_ARGS[@]}"} \
    --rd-mode early \
    --rd-method "${RD_METHOD}" \
    --omega-b-h2 "${OMEGA_B_H2}" \
    --omega-c-h2 "${OMEGA_C_H2}" \
    --Neff "${NEFF}" \
    --Tcmb-K "${TCMB_K}" \
    --cmb "${CMB_CSV}" \
    --cmb-cov "${CMB_COV}" \
    --cmb-mode distance_priors \
    --cmb-bridge-z "${BEST_BRIDGE_Z}" \
    --cmb-debug \
    > "${DEBUG_OUT}"
  if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
    cp -f "${DEBUG_OUT}" "${PAPER_ASSETS_DIR}/tables/cmb_best_debug.txt"
  fi
fi

echo "[reproduce-e1.3] coarse scan over (p, z_transition) at bridge_z={2,5,10,20} (CMB-only + drift sign guardrail; excludes degenerate bridge_z<=z_transition from 'best')"
COARSE_OUT="${TABLES_DIR}/cmb_pzt_coarse_scan.csv"
"${PY}" "${V101_DIR}/scripts/cmb_bridge_pzt_coarse_scan_e1_3.py" \
  --out "${COARSE_OUT}" \
  --cmb "${CMB_CSV}" \
  --cmb-cov "${CMB_COV}" \
  --bridge-z "2,5,10,20" \
  --H0 "${H0}" \
  --Omega-m "${OMEGA_M}" \
  --Omega-L "${OMEGA_L}" \
  --p-grid "0.55,0.6,0.65,0.7,0.8,0.9" \
  --ztrans-grid "1.2,1.5,1.8,2.2,3.0" \
  --omega-b-h2 "${OMEGA_B_H2}" \
  --omega-c-h2 "${OMEGA_C_H2}" \
  --Neff "${NEFF}" \
  --Tcmb-K "${TCMB_K}" \
  || true
if [[ "${SYNC_PAPER_ASSETS}" == "1" && -f "${COARSE_OUT}" ]]; then
  cp -f "${COARSE_OUT}" "${PAPER_ASSETS_DIR}/tables/cmb_pzt_coarse_scan.csv"
fi

TOPN_OUT="${TABLES_DIR}/cmb_pzt_topN.csv"
"${PY}" - <<PY 2>/dev/null || true
import csv, math
from pathlib import Path

src = Path(r"${COARSE_OUT}")
dst = Path(r"${TOPN_OUT}")

if not src.exists():
    raise SystemExit(0)

rows = []
with src.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        if not row:
            continue
        try:
            row["bridge_z"] = float(row.get("bridge_z") or "nan")
            row["chi2_cmb"] = float(row.get("chi2_cmb") or "nan")
        except Exception:
            continue
        row["drift_ok"] = (row.get("drift_guardrail_positive") or "").strip().lower() in ("1", "true", "yes", "y")
        row["is_degenerate"] = (row.get("is_degenerate") or "").strip().lower() in ("1", "true", "yes", "y")
        rows.append(row)

bridge_zs = (2.0, 5.0, 10.0, 20.0)
out_rows = []
for zb in bridge_zs:
    rr = [r for r in rows if math.isfinite(r["chi2_cmb"]) and r["drift_ok"] and (not r["is_degenerate"]) and float(r["bridge_z"]) == zb]
    rr.sort(key=lambda x: float(x["chi2_cmb"]))
    out_rows.extend(rr[:10])

cols = [
    "bridge_z",
    "gsc_p",
    "gsc_ztrans",
    "chi2_cmb",
    "pull_R",
    "pull_lA",
    "pull_omega_b_h2",
    "R_pred",
    "lA_pred",
    "omega_b_h2_pred",
    "frac_DM_non_lcdm",
    "drift_guardrail_positive",
    "is_degenerate",
]

with dst.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in out_rows:
        w.writerow({k: r.get(k, "") for k in cols})

def best_for(zb: float):
    rr = [r for r in rows if math.isfinite(r["chi2_cmb"]) and r["drift_ok"] and (not r["is_degenerate"]) and float(r["bridge_z"]) == zb]
    rr.sort(key=lambda x: float(x["chi2_cmb"]))
    return rr[0] if rr else None

best_ge5 = min(
    [r for r in rows if math.isfinite(r["chi2_cmb"]) and r["drift_ok"] and (not r["is_degenerate"]) and float(r["bridge_z"]) >= 5.0],
    key=lambda x: float(x["chi2_cmb"]),
    default=None,
)

print("[reproduce-e1.3] coarse-scan top10 summary wrote:", dst)
for zb in bridge_zs:
    b = best_for(zb)
    if b is None:
        print(f"  bridge_z={zb:g}: no drift-positive non-degenerate points")
    else:
        print(f"  bridge_z={zb:g}: min chi2_cmb={b['chi2_cmb']:.6g} at p={b.get('gsc_p')} zt={b.get('gsc_ztrans')}")
if best_ge5 is None:
    print("  bridge_z>=5: no drift-positive non-degenerate points")
else:
    print(f"  bridge_z>=5: global min chi2_cmb={best_ge5['chi2_cmb']:.6g} at bridge_z={best_ge5['bridge_z']:.6g} p={best_ge5.get('gsc_p')} zt={best_ge5.get('gsc_ztrans')}")
PY

if [[ "${SYNC_PAPER_ASSETS}" == "1" && -f "${TOPN_OUT}" ]]; then
  cp -f "${TOPN_OUT}" "${PAPER_ASSETS_DIR}/tables/cmb_pzt_topN.csv"
fi

echo "[reproduce-e1.3] manifest..."
"${PY}" "${V101_DIR}/scripts/late_time_make_manifest.py" --fit-dir "${RESULTS_DIR}"

if [[ "${SYNC_PAPER_ASSETS}" == "1" ]]; then
  echo "[reproduce-e1.3] syncing manifest..."
  mkdir -p "${PAPER_ASSETS_DIR}"
  cp -f "${RESULTS_DIR}/manifest.json" "${PAPER_ASSETS_DIR}/manifest.json"
fi

echo "[reproduce-e1.3] done: ${RESULTS_DIR}"
