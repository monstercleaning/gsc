#!/usr/bin/env bash
set -euo pipefail

V11_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAPER_DIR="${V11_DIR}/papers/paper2_measurement_model_epsilon"
MAIN_TEX="${PAPER_DIR}/paper2.tex"
BUILD_DIR="${V11_DIR}/paper_assets/build_paper2"
OUT_PDF="${V11_DIR}/paper_assets/paper2_measurement_model_epsilon.pdf"
ASSETS_DIR_DEFAULT="${V11_DIR}/out/paper2_ci_assets"
ASSETS_DIR="${PAPER2_ASSETS_DIR:-${ASSETS_DIR_DEFAULT}}"

if [[ ! -f "${MAIN_TEX}" ]]; then
  echo "ERROR: missing ${MAIN_TEX}" >&2
  exit 1
fi

mkdir -p "${BUILD_DIR}" "${V11_DIR}/paper_assets"

if [[ -d "${ASSETS_DIR}" ]]; then
  if [[ -f "${ASSETS_DIR}/numbers.tex" ]]; then
    cp -f "${ASSETS_DIR}/numbers.tex" "${PAPER_DIR}/numbers.tex"
  fi
  if [[ -d "${ASSETS_DIR}/figures" ]]; then
    mkdir -p "${PAPER_DIR}/figures"
    cp -f "${ASSETS_DIR}/figures/"*.png "${PAPER_DIR}/figures/" 2>/dev/null || true
  fi
fi

if command -v latexmk >/dev/null 2>&1; then
  (cd "${PAPER_DIR}" && latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="${BUILD_DIR}" paper2.tex)
elif command -v pdflatex >/dev/null 2>&1; then
  (cd "${PAPER_DIR}" && pdflatex -interaction=nonstopmode -halt-on-error -output-directory="${BUILD_DIR}" paper2.tex >/dev/null)
  (cd "${PAPER_DIR}" && pdflatex -interaction=nonstopmode -halt-on-error -output-directory="${BUILD_DIR}" paper2.tex >/dev/null)
else
  echo "ERROR: need latexmk or pdflatex on PATH" >&2
  exit 1
fi

PDF_BUILT="${BUILD_DIR}/paper2.pdf"
if [[ ! -f "${PDF_BUILT}" ]]; then
  echo "ERROR: expected PDF not found: ${PDF_BUILT}" >&2
  exit 1
fi

cp -f "${PDF_BUILT}" "${OUT_PDF}"
echo "[paper2] wrote: ${OUT_PDF}"
