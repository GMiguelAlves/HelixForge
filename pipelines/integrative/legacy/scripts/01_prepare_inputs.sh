#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${1:-config/pipeline_config.sh}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
create_output_tree

STEP_DIR="020-prepared-inputs"
if is_done "${STEP_DIR}" "prepare"; then
  log "Input preparation already completed; skipping"
  exit 0
fi

run_python_step prepare
mark_done "${STEP_DIR}" "prepare"
