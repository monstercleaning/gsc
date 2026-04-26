#!/usr/bin/env bash
set -euo pipefail

V101_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIT_DIR="${1:-${V101_DIR}/results/late_time_fit}"
OUT_DIR="${2:-${V101_DIR}/paper_assets}"

FIG_SRC="${FIT_DIR}/figures"
CONF_SRC="${FIT_DIR}/confidence"
TABLE_SRC="${FIT_DIR}/bestfit_summary.tex"
MANIFEST_SRC="${FIT_DIR}/manifest.json"

if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync is required for sync_paper_assets.sh" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}/figures" "${OUT_DIR}/tables"

if [[ ! -d "${FIG_SRC}" ]]; then
  echo "ERROR: missing figures dir: ${FIG_SRC}" >&2
  exit 1
fi

echo "[sync] figures: ${FIG_SRC} -> ${OUT_DIR}/figures/"
rsync -av --delete --exclude ".mplconfig/" --exclude "confidence/" "${FIG_SRC}/" "${OUT_DIR}/figures/"

if [[ -d "${CONF_SRC}" ]]; then
  mkdir -p "${OUT_DIR}/figures/confidence"
  echo "[sync] confidence: ${CONF_SRC} -> ${OUT_DIR}/figures/confidence/"
  rsync -av --delete "${CONF_SRC}/" "${OUT_DIR}/figures/confidence/"
fi

if [[ -f "${TABLE_SRC}" ]]; then
  echo "[sync] table: ${TABLE_SRC} -> ${OUT_DIR}/tables/bestfit_summary.tex"
  cp -f "${TABLE_SRC}" "${OUT_DIR}/tables/bestfit_summary.tex"
else
  echo "[sync] WARNING: missing table: ${TABLE_SRC}" >&2
fi

if [[ -f "${MANIFEST_SRC}" ]]; then
  echo "[sync] manifest: ${MANIFEST_SRC} -> ${OUT_DIR}/manifest.json"
  cp -f "${MANIFEST_SRC}" "${OUT_DIR}/manifest.json"
fi

echo "[sync] done"
