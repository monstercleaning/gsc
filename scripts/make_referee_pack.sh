#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/paper_assets_v10.1.1-late-time-rX.zip [out_zip]" >&2
  exit 2
fi

ASSETS_ZIP="$1"
OUT_ZIP="${2:-}"

PY="${GSC_PYTHON:-}"
if [[ -z "${PY}" ]]; then
  if [[ -x "${SCRIPT_DIR}/../.venv/bin/python" ]]; then
    PY="${SCRIPT_DIR}/../.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
  else
    echo "ERROR: python3 not found and v11.0.0/.venv/bin/python missing." >&2
    exit 2
  fi
fi

base="$(basename -- "${ASSETS_ZIP}")"
tag="unknown"
if [[ "${base}" == paper_assets_*.zip ]]; then
  tag="${base#paper_assets_}"
  tag="${tag%.zip}"
fi

tmp_dir="$(mktemp -d 2>/dev/null || mktemp -d -t gsc_referee_pack)"
cleanup() { rm -rf "${tmp_dir}"; }
trap cleanup EXIT

sub_zip="${tmp_dir}/submission_bundle_${tag}.zip"

# Build a nested submission bundle first (preflight verified by make_submission_bundle.py).
"${PY}" "${SCRIPT_DIR}/make_submission_bundle.py" "${ASSETS_ZIP}" "${sub_zip}"

if [[ -z "${OUT_ZIP}" ]]; then
  OUT_ZIP="referee_pack_${tag}.zip"
fi

"${PY}" "${SCRIPT_DIR}/make_referee_pack.py" \
  --assets-zip "${ASSETS_ZIP}" \
  --submission-zip "${sub_zip}" \
  --out-zip "${OUT_ZIP}"

echo "[referee-pack] wrote: ${OUT_ZIP}"

