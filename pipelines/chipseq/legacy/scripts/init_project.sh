#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

copy_if_missing() {
  local src="$1"
  local dst="$2"
  if [[ -e "${dst}" ]]; then
    echo "exists: ${dst}"
  else
    cp "${src}" "${dst}"
    echo "created: ${dst}"
  fi
}

mkdir -p "${PROJECT_DIR}/data/fastq" "${PROJECT_DIR}/reference"

copy_if_missing \
  "${PROJECT_DIR}/config/user_settings_template.sh" \
  "${PROJECT_DIR}/config/user_settings.sh"

copy_if_missing \
  "${PROJECT_DIR}/config/metadata_template.tsv" \
  "${PROJECT_DIR}/config/metadata.tsv"

echo
echo "Next steps:"
echo "1. Edit config/user_settings.sh"
echo "2. Edit config/metadata.tsv"
echo "3. Run: bash scripts/check_install.sh"
echo "4. Run: bash chipseq_pipeline.sh --all --dry-run"
