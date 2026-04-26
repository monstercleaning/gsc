#!/usr/bin/env bash
set -euo pipefail

V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEX="${V101_DIR}/GSC_Framework_v10_1_FINAL.tex"
TEX_BASENAME="$(basename "${TEX}")"
JOBNAME="$(basename "${TEX}" .tex)"
ASSETS_DIR="${V101_DIR}/paper_assets"
BUILD_DIR="${ASSETS_DIR}/build"
OUT_PDF="${ASSETS_DIR}/GSC_Framework_v10_1_FINAL.pdf"
REPO_ROOT="$(cd "${V101_DIR}/.." && pwd)"

DO_REPRODUCE="1"
REPRO_ARGS=(--with-drift --sync-paper-assets)
PHASE2_E2_BUNDLE=""
PHASE2_E2_BUNDLE_DIRS=()
PHASE2_E2_BUNDLE_SELECT="best_plausible"
PHASE2_E2_RESOLVE_ONLY="0"
PHASE2_E2_EXTRACT_ROOT="${REPO_ROOT}"

usage() {
  cat <<EOF
Usage: $0 [--no-reproduce] [--repro-args "..."]
          [--phase2-e2-bundle PATH]
          [--phase2-e2-bundle-dir DIR ...]
          [--phase2-e2-bundle-select {best_plausible,best_eligible,latest}]
          [--phase2-e2-extract-root PATH]
          [--phase2-e2-resolve-only]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-reproduce)
      DO_REPRODUCE="0"
      shift
      ;;
    --repro-args)
      shift
      if [[ $# -eq 0 ]]; then
        echo "ERROR: --repro-args requires a single string argument" >&2
        exit 2
      fi
      # Split on spaces intentionally; use with care.
      # Example: --repro-args "--no-drift --sync-paper-assets"
      read -r -a REPRO_ARGS <<<"$1"
      shift
      ;;
    --phase2-e2-bundle)
      shift
      if [[ $# -eq 0 ]]; then
        echo "ERROR: --phase2-e2-bundle requires a path argument" >&2
        exit 2
      fi
      PHASE2_E2_BUNDLE="$1"
      shift
      ;;
    --phase2-e2-bundle-dir)
      shift
      if [[ $# -eq 0 ]]; then
        echo "ERROR: --phase2-e2-bundle-dir requires a path argument" >&2
        exit 2
      fi
      PHASE2_E2_BUNDLE_DIRS+=("$1")
      shift
      ;;
    --phase2-e2-bundle-select)
      shift
      if [[ $# -eq 0 ]]; then
        echo "ERROR: --phase2-e2-bundle-select requires a value" >&2
        exit 2
      fi
      case "$1" in
        best_plausible|best_eligible|latest)
          PHASE2_E2_BUNDLE_SELECT="$1"
          ;;
        *)
          echo "ERROR: invalid --phase2-e2-bundle-select: $1" >&2
          exit 2
          ;;
      esac
      shift
      ;;
    --phase2-e2-resolve-only)
      PHASE2_E2_RESOLVE_ONLY="1"
      shift
      ;;
    --phase2-e2-extract-root)
      shift
      if [[ $# -eq 0 ]]; then
        echo "ERROR: --phase2-e2-extract-root requires a path argument" >&2
        exit 2
      fi
      PHASE2_E2_EXTRACT_ROOT="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

PHASE2_E2_BUNDLE_RESOLVED=""
if [[ -n "${PHASE2_E2_BUNDLE}" ]]; then
  PHASE2_E2_BUNDLE_RESOLVED="$(python3 - "${PHASE2_E2_BUNDLE}" <<'PY'
import pathlib
import sys
print(pathlib.Path(sys.argv[1]).expanduser().resolve())
PY
)"
elif [[ ${#PHASE2_E2_BUNDLE_DIRS[@]} -gt 0 ]]; then
  SELECT_SCRIPT="${V101_DIR}/scripts/phase2_e2_select_bundle.py"
  if [[ ! -f "${SELECT_SCRIPT}" ]]; then
    echo "ERROR: missing selector script: ${SELECT_SCRIPT}" >&2
    exit 1
  fi
  select_cmd=(python3 "${SELECT_SCRIPT}" --select "${PHASE2_E2_BUNDLE_SELECT}" --require-plan-coverage complete --print-path)
  for dir_path in "${PHASE2_E2_BUNDLE_DIRS[@]}"; do
    select_cmd+=(--input "${dir_path}")
  done
  if ! PHASE2_E2_BUNDLE_RESOLVED="$("${select_cmd[@]}")"; then
    rc=$?
    if [[ $rc -eq 2 ]]; then
      echo "ERROR: Phase-2 bundle auto-selection failed coverage/selection constraints" >&2
      exit 2
    fi
    echo "ERROR: Phase-2 bundle auto-selection failed" >&2
    exit 1
  fi
  PHASE2_E2_BUNDLE_RESOLVED="$(python3 - "${PHASE2_E2_BUNDLE_RESOLVED}" <<'PY'
import pathlib
import sys
print(pathlib.Path(sys.argv[1]).expanduser().resolve())
PY
)"
fi

if [[ "${PHASE2_E2_RESOLVE_ONLY}" == "1" ]]; then
  if [[ -n "${PHASE2_E2_BUNDLE_RESOLVED}" ]]; then
    printf '%s\n' "${PHASE2_E2_BUNDLE_RESOLVED}"
    exit 0
  fi
  echo "ERROR: --phase2-e2-resolve-only requires --phase2-e2-bundle or --phase2-e2-bundle-dir" >&2
  exit 1
fi

if [[ "${DO_REPRODUCE}" == "1" ]]; then
  echo "[paper] reproduce + sync assets"
  bash "${V101_DIR}/scripts/reproduce_v10_1_late_time.sh" "${REPRO_ARGS[@]}"
fi

if [[ -n "${PHASE2_E2_BUNDLE_RESOLVED}" ]]; then
  VERIFY_SCRIPT="${V101_DIR}/scripts/phase2_e2_verify_bundle.py"
  if [[ ! -f "${VERIFY_SCRIPT}" ]]; then
    echo "ERROR: missing verifier script: ${VERIFY_SCRIPT}" >&2
    exit 1
  fi
  echo "[paper] verify + extract Phase-2 E2 paper assets from bundle"
  python3 "${VERIFY_SCRIPT}" \
    --bundle "${PHASE2_E2_BUNDLE_RESOLVED}" \
    --plan-coverage complete \
    --paper-assets require \
    --extract-paper-assets \
    --extract-root "${PHASE2_E2_EXTRACT_ROOT}" \
    --extract-mode clean_overwrite

  PHASE2_ASSET_ROOT="${PHASE2_E2_EXTRACT_ROOT}"
  if [[ -d "${PHASE2_E2_EXTRACT_ROOT}/v11.0.0" ]]; then
    PHASE2_ASSET_ROOT="${PHASE2_E2_EXTRACT_ROOT}/v11.0.0"
  fi
  PHASE2_REQUIRED_SNIPPETS=(
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.tex"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.md"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_sf_rsd_summary.tex"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_sf_rsd_summary.md"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_sf_fsigma8.tex"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_sf_fsigma8.md"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_rg_flow_table.tex"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_rg_flow_table.md"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_rg_pade_fit.tex"
    "${PHASE2_ASSET_ROOT}/paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_rg_pade_fit.md"
  )
  for snippet in "${PHASE2_REQUIRED_SNIPPETS[@]}"; do
    if [[ ! -f "${snippet}" ]]; then
      echo "ERROR: missing Phase-2 E2 snippet after bundle extraction: ${snippet}" >&2
      echo "Bundle may be older than v10.1.1-phase2-m70; regenerate paper assets/snippets and rebuild bundle." >&2
      exit 1
    fi
  done
fi

mkdir -p "${BUILD_DIR}"

if [[ ! -f "${TEX}" ]]; then
  echo "ERROR: missing LaTeX source: ${TEX}" >&2
  exit 1
fi

echo "[paper] build: ${TEX}"
# Strict asset mode: fail if expected paper_assets are missing.
STRICT_INPUT="\\def\\GSCSTRICTASSETS{1}\\input{${TEX_BASENAME}}"
if [[ -n "${PHASE2_E2_BUNDLE_RESOLVED}" ]]; then
  STRICT_INPUT="\\def\\GSCSTRICTASSETS{1}\\def\\GSCWITHPHASE2E2{1}\\input{${TEX_BASENAME}}"
fi
if command -v latexmk >/dev/null 2>&1; then
  (cd "${V101_DIR}" && latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="${BUILD_DIR}" -pdflatex="pdflatex -interaction=nonstopmode -halt-on-error -jobname=${JOBNAME} %O \"${STRICT_INPUT}\"" "${TEX_BASENAME}")
elif command -v pdflatex >/dev/null 2>&1; then
  (cd "${V101_DIR}" && pdflatex -interaction=nonstopmode -halt-on-error -jobname="${JOBNAME}" -output-directory="${BUILD_DIR}" "${STRICT_INPUT}" >/dev/null)
  (cd "${V101_DIR}" && pdflatex -interaction=nonstopmode -halt-on-error -jobname="${JOBNAME}" -output-directory="${BUILD_DIR}" "${STRICT_INPUT}" >/dev/null)
else
  echo "ERROR: need latexmk or pdflatex on PATH to build the paper." >&2
  exit 1
fi

PDF_BUILT="${BUILD_DIR}/$(basename "${TEX}" .tex).pdf"
if [[ ! -f "${PDF_BUILT}" ]]; then
  echo "ERROR: expected PDF not found: ${PDF_BUILT}" >&2
  exit 1
fi

cp -f "${PDF_BUILT}" "${OUT_PDF}"
echo "[paper] wrote: ${OUT_PDF}"
