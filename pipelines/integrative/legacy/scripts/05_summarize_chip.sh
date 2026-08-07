#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${1:-config/pipeline_config.sh}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
create_output_tree

STEP_DIR="060-chipseq-summary"
if is_done "${STEP_DIR}" "summarize-chip"; then
  log "ChIP-seq summary already completed; skipping"
  exit 0
fi

run_python_step summarize-chip
mark_done "${STEP_DIR}" "summarize-chip"
