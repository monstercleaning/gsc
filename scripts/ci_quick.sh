#!/usr/bin/env bash
set -euo pipefail

V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export MPLBACKEND="Agg"

python_has_deps() {
  local py="$1"
  "${py}" - <<'PY' >/dev/null 2>&1
import numpy  # noqa: F401
import scipy  # noqa: F401
import matplotlib  # noqa: F401
PY
}

PY_V101="${V101_DIR}/.venv/bin/python"
PY_PHASE10="${V101_DIR}/B/GSC_v10_8_PUBLICATION_BUNDLE/.venv/bin/python"
PY=""

if [[ -n "${GSC_PYTHON:-}" ]]; then
  if [[ ! -x "${GSC_PYTHON}" ]]; then
    echo "ERROR: GSC_PYTHON is not executable: ${GSC_PYTHON}" >&2
    exit 1
  fi
  if ! python_has_deps "${GSC_PYTHON}"; then
    echo "ERROR: GSC_PYTHON does not have required deps (numpy+scipy+matplotlib): ${GSC_PYTHON}" >&2
    exit 1
  fi
  PY="${GSC_PYTHON}"
fi

if [[ -z "${PY}" ]]; then
  if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
    PY="${PY_V101}"
  else
    if [[ "${GSC_SKIP_BOOTSTRAP:-0}" != "1" ]]; then
      echo "[ci] bootstrap venv"
      if bash "${V101_DIR}/scripts/bootstrap_venv.sh"; then
        if [[ -x "${PY_V101}" ]] && python_has_deps "${PY_V101}"; then
          PY="${PY_V101}"
        fi
      fi
    fi
  fi
fi

if [[ -z "${PY}" ]]; then
  if [[ -x "${PY_PHASE10}" ]] && python_has_deps "${PY_PHASE10}"; then
    echo "[ci] WARNING: falling back to Phase10 venv python"
    PY="${PY_PHASE10}"
  else
    echo "ERROR: no usable python found (need numpy+scipy+matplotlib)." >&2
    exit 1
  fi
fi

echo "[ci] unit tests"
"${PY}" -m unittest discover -s "${V101_DIR}/tests" -p 'test_*.py' -v

echo "[ci] docs claims lint"
"${PY}" "${V101_DIR}/scripts/docs_claims_lint.py" --repo-root "${V101_DIR}"

if [[ -n "${GSC_OUTDIR:-}" ]]; then
  mkdir -p "${GSC_OUTDIR}"
  if ! TMP_DIR="$(mktemp -d "${GSC_OUTDIR%/}/ci_quick.XXXXXX" 2>/dev/null)"; then
    echo "ERROR: failed to create temp dir under GSC_OUTDIR=${GSC_OUTDIR}" >&2
    exit 1
  fi
else
  TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t gsc_ci)"
fi
FIT_DIR="${TMP_DIR}/late_time_fit"
FIT_DIR_EARLY="${TMP_DIR}/late_time_fit_rd_early"
mkdir -p "${FIT_DIR}"
mkdir -p "${FIT_DIR_EARLY}"

export GSC_CI_TMP_DIR="${TMP_DIR}"
echo "[ci] generating synthetic datasets in ${TMP_DIR}"
"${PY}" - <<'PY'
import csv
import os
import sys
from pathlib import Path

ROOT = Path("v11.0.0").resolve()
sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    H0_to_SI,
    distance_modulus_flat,
    delta_v_cm_s,
)
from gsc.early_time import compute_lcdm_shift_params  # noqa: E402

tmp_dir = Path(os.environ["GSC_CI_TMP_DIR"])
sn_path = tmp_dir / "sn.csv"
bao_path = tmp_dir / "bao.csv"
drift_path = tmp_dir / "drift.csv"
cmb_path = tmp_dir / "cmb_priors.csv"

H0 = H0_to_SI(67.4)
model = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)

# SN: exact LCDM + a constant ΔM (fit should absorb it cleanly).
zs = [0.05, 0.2, 0.7]
delta_M = 0.1
mu = [distance_modulus_flat(z=z, H_of_z=model.H, n=2000) + delta_M for z in zs]
sig = [0.2, 0.2, 0.2]
with sn_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["z", "mu", "sigma_mu"])
    for z, m, s in zip(zs, mu, sig):
        w.writerow([f"{z:.10g}", f"{m:.10g}", f"{s:.10g}"])

# BAO: two isotropic points (arbitrary positive ratios).
with bao_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["type", "z", "dv_over_rd", "sigma_dv_over_rd", "survey", "label"])
    w.writerow(["DV_over_rd", "0.1", "3.0", "0.1", "CI", "DV1"])
    w.writerow(["DV_over_rd", "0.2", "4.0", "0.15", "CI", "DV2"])

# Drift: 2 points, Asimov from the same fiducial model over a 10-year baseline.
baseline = 10.0
z_d = [3.0, 4.0]
dv = [delta_v_cm_s(z=z, years=baseline, H0=model.H(0.0), H_of_z=model.H) for z in z_d]
sig_d = [1.0, 1.0]
with drift_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["z", "dv_cm_s", "sigma_dv_cm_s", "baseline_years"])
    for z, v, s in zip(z_d, dv, sig_d):
        w.writerow([f"{z:.10g}", f"{v:.10g}", f"{s:.10g}", f"{baseline:.10g}"])

# CMB priors: tiny synthetic set matching LCDM predictor at the same parameters.
pred = compute_lcdm_shift_params(
    H0_km_s_Mpc=67.4,
    Omega_m=0.315,
    omega_b_h2=0.02237,
    omega_c_h2=0.1200,
    N_eff=3.046,
    Tcmb_K=2.7255,
)
with cmb_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["name", "value", "sigma"])
    w.writerow(["theta_star", f"{float(pred['theta_star']):.16g}", "1e-5"])
    w.writerow(["R", f"{float(pred['R']):.16g}", "1e-3"])

print("WROTE", sn_path)
print("WROTE", bao_path)
print("WROTE", drift_path)
print("WROTE", cmb_path)
PY

echo "[ci] smoke fit (lcdm)"
"${PY}" "${V101_DIR}/scripts/late_time_fit_grid.py" \
  --model lcdm \
  --sn "${TMP_DIR}/sn.csv" \
  --bao "${TMP_DIR}/bao.csv" \
  --drift "${TMP_DIR}/drift.csv" --profile-H0 \
  --H0-grid "60:80:1" \
  --Omega-m-grid "0.25:0.35:0.05" \
  --top-k 20 \
  --out-dir "${FIT_DIR}"

echo "[ci] smoke fit (lcdm, rd-mode=early)"
"${PY}" "${V101_DIR}/scripts/late_time_fit_grid.py" \
  --model lcdm \
  --sn "${TMP_DIR}/sn.csv" \
  --bao "${TMP_DIR}/bao.csv" \
  --rd-mode early \
  --omega-b-h2 "0.02237" \
  --omega-c-h2 "0.1200" \
  --Neff "3.046" \
  --Tcmb-K "2.7255" \
  --H0-grid "67.4" \
  --Omega-m-grid "0.315" \
  --top-k 5 \
  --out-dir "${FIT_DIR_EARLY}"

echo "[ci] verify derived-rd metadata"
"${PY}" - <<'PY'
import json
import os
from pathlib import Path

tmp = Path(os.environ["GSC_CI_TMP_DIR"])
bestfit = tmp / "late_time_fit_rd_early" / "lcdm_bestfit.json"
if not bestfit.is_file():
    raise SystemExit(f"missing bestfit output: {bestfit}")
obj = json.loads(bestfit.read_text(encoding="utf-8"))
rd = obj.get("rd") or {}
bao = ((obj.get("best") or {}).get("parts") or {}).get("bao") or {}
if str(rd.get("rd_mode")) != "early":
    raise SystemExit(f"unexpected rd_mode: {rd.get('rd_mode')!r}")
if str(bao.get("rd_fit_mode")) != "fixed":
    raise SystemExit(f"unexpected bao.rd_fit_mode: {bao.get('rd_fit_mode')!r}")
if float(bao.get("rd_Mpc", 0.0)) <= 0.0 or float(bao.get("rd_m", 0.0)) <= 0.0:
    raise SystemExit("derived-rd metadata is missing positive rd values")
print("derived-rd metadata OK")
PY

echo "[ci] smoke early-time CMB priors batch report"
"${PY}" "${V101_DIR}/scripts/early_time_cmb_priors_report.py" \
  --fit-dir "${FIT_DIR}" \
  --cmb "${TMP_DIR}/cmb_priors.csv" \
  --omega-b-h2 "0.02237" \
  --omega-c-h2 "0.1200" \
  --out-dir "${TMP_DIR}"

echo "[ci] verify early-time numerics invariants report"
"${PY}" - <<'PY'
import json
import os
from pathlib import Path

tmp = Path(os.environ["GSC_CI_TMP_DIR"])
path = tmp / "early_time" / "numerics_invariants_report.json"
if not path.is_file():
    raise SystemExit(f"missing numerics invariants report: {path}")
obj = json.loads(path.read_text(encoding="utf-8"))
required = {
    "finite_positive_core",
    "alias_theta_star_100theta_star",
    "identity_lA_equals_pi_over_theta_star",
    "identity_rd_m_equals_rd_Mpc_times_MPC_SI",
}
if obj.get("schema_version") != "phase2.m8.early_time_invariants_report.v1":
    raise SystemExit(f"unexpected invariants schema_version: {obj.get('schema_version')!r}")
if obj.get("model_invariants_schema_version") != 1:
    raise SystemExit(
        f"unexpected model_invariants_schema_version: {obj.get('model_invariants_schema_version')!r}"
    )
if obj.get("strict") is not True:
    raise SystemExit(f"invariants report strict must be true, got {obj.get('strict')!r}")
if obj.get("ok") is not True:
    raise SystemExit("numerics invariants report is not OK")
top_required = set(obj.get("required_check_ids") or [])
missing_top = sorted(required - top_required)
if missing_top:
    raise SystemExit(f"top-level required checks missing: {missing_top}")
checks = obj.get("checks")
if not isinstance(checks, dict) or not checks:
    raise SystemExit("invariants report checks must be a non-empty object")
for model_id, model_payload in checks.items():
    if not isinstance(model_payload, dict):
        raise SystemExit(f"model payload is not an object: {model_id!r}")
    if model_payload.get("schema_version") != 1:
        raise SystemExit(f"{model_id}: schema_version must be 1")
    if model_payload.get("strict") is not True:
        raise SystemExit(f"{model_id}: strict must be true")
    model_required = set(model_payload.get("required_check_ids") or [])
    missing_model_required = sorted(required - model_required)
    if missing_model_required:
        raise SystemExit(f"{model_id}: missing required_check_ids: {missing_model_required}")
    model_checks = model_payload.get("checks")
    if not isinstance(model_checks, dict):
        raise SystemExit(f"{model_id}: checks must be an object")
    for check_id in sorted(required):
        check = model_checks.get(check_id)
        if not isinstance(check, dict):
            raise SystemExit(f"{model_id}: missing check payload: {check_id}")
        if check.get("ok") is not True or str(check.get("status", "")).upper() != "PASS":
            raise SystemExit(
                f"{model_id}: required check failed: {check_id} "
                f"(ok={check.get('ok')!r}, status={check.get('status')!r})"
            )
print("numerics invariants OK (strict M8 contract)")
PY

echo "[ci] smoke figures/summary"
"${PY}" "${V101_DIR}/scripts/late_time_make_figures.py" \
  --fit-dir "${FIT_DIR}" \
  --models lcdm \
  --out-dir "${FIT_DIR}/figures"

echo "[ci] smoke confidence"
"${PY}" "${V101_DIR}/scripts/late_time_make_confidence.py" --fit-dir "${FIT_DIR}" --models lcdm

echo "[ci] smoke tables"
"${PY}" "${V101_DIR}/scripts/late_time_make_tables.py" \
  --fit-dir "${FIT_DIR}" \
  --out-tex "${FIT_DIR}/bestfit_summary.tex"

echo "[ci] smoke manifest"
"${PY}" "${V101_DIR}/scripts/late_time_make_manifest.py" \
  --fit-dir "${FIT_DIR}" \
  --out "${FIT_DIR}/manifest.json"

test -f "${FIT_DIR}/lcdm_bestfit.json"
test -f "${FIT_DIR}/bestfit_summary.csv"
test -f "${FIT_DIR}/bestfit_summary.tex"
test -f "${FIT_DIR}/manifest.json"
test -f "${FIT_DIR_EARLY}/lcdm_bestfit.json"
test -f "${TMP_DIR}/early_time/cmb_priors_report.json"
test -f "${TMP_DIR}/early_time/cmb_priors_table.csv"
test -f "${TMP_DIR}/early_time/numerics_invariants_report.json"

echo "[ci] OK"
