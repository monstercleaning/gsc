#!/usr/bin/env bash
set -euo pipefail

# Fetch public Pantheon+SH0ES DataRelease artifacts needed by the v11.0.0 harness.
#
# Outputs:
#   v11.0.0/data/sn/pantheon_plus_shoes/Pantheon+SH0ES.dat
#   v11.0.0/data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov
#
# Notes:
# - The harness converts the .dat table into small CSVs via:
#     python3 v11.0.0/scripts/pantheon_plus_shoes_to_csv.py
# - The .cov file can be cached as .npz automatically when used.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/data/sn/pantheon_plus_shoes"
mkdir -p "${OUT_DIR}"

curl -L \
  -o "${OUT_DIR}/Pantheon+SH0ES.dat" \
  "https://raw.githubusercontent.com/PantheonPlusSH0ES/DataRelease/main/Pantheon%2B_Data/4_DISTANCES_AND_COVAR/Pantheon%2BSH0ES.dat"

curl -L \
  -o "${OUT_DIR}/Pantheon+SH0ES_STAT+SYS.cov" \
  "https://raw.githubusercontent.com/PantheonPlusSH0ES/DataRelease/main/Pantheon%2B_Data/4_DISTANCES_AND_COVAR/Pantheon%2BSH0ES_STAT%2BSYS.cov"

ls -lh "${OUT_DIR}/Pantheon+SH0ES.dat" "${OUT_DIR}/Pantheon+SH0ES_STAT+SYS.cov"

