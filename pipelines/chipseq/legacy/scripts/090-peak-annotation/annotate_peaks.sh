#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: annotate_peaks.sh CONFIG}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="090-peak-annotation"
STEP_DIR="${ANNOTATION_DIR:-${OUTPUT_DIR}/${STEP}}"
ensure_dir "${STEP_DIR}"

if is_done "${STEP}" "annotation"; then
  log "Peak annotation already completed; skipping"
  exit 0
fi

require_cmd "${RSCRIPT_BIN}"

"${RSCRIPT_BIN}" "${SCRIPT_DIR}/r/annotate_peaks.R" \
  --peaks-dir "${PEAK_DIR:-${OUTPUT_DIR}/080-peak-calling}" \
  --consensus-dir "${CONSENSUS_DIR:-${OUTPUT_DIR}/110-consensus-peaks}/groups" \
  --annotation-dir "${REF_DIR:-${OUTPUT_DIR}/010-reference}/annotation" \
  --functional-annotation "${FUNCTIONAL_ANNOTATION}" \
  --table-suffix "${PIPELINE_TABLE_SUFFIX:-}" \
  --outdir "${STEP_DIR}"

mark_done "${STEP}" "annotation"
log "Peak annotation completed"
