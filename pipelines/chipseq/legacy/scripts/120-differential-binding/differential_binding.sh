#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: differential_binding.sh CONFIG}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="120-differential-binding"
STEP_DIR="${DIFF_DIR:-${OUTPUT_DIR}/${STEP}}"
ensure_dir "${STEP_DIR}"

if is_done "${STEP}" "differential"; then
  log "Differential binding already completed; skipping"
  exit 0
fi

require_cmd "${RSCRIPT_BIN}"

"${RSCRIPT_BIN}" "${SCRIPT_DIR}/r/differential_binding.R" \
  --metadata "${METADATA_FILE}" \
  --counts-dir "${CONSENSUS_DIR:-${OUTPUT_DIR}/110-consensus-peaks}/counts" \
  --contrasts "${DIFF_CONTRASTS}" \
  --min-replicates "${MIN_REPLICATES_DIFF}" \
  --peak-set-scope "${DIFF_PEAK_SET_SCOPE}" \
  --table-suffix "${PIPELINE_TABLE_SUFFIX:-}" \
  --outdir "${STEP_DIR}"

mark_done "${STEP}" "differential"
log "Differential binding completed"
