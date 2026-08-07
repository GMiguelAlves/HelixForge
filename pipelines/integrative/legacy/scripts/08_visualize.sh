#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${1:-config/pipeline_config.sh}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
create_output_tree

if [[ "${ENV_BACKEND:-none}" == "conda" && -n "${VISUALIZATION_CONDA_ENV:-}" ]]; then
  export CONDA_ENV="${VISUALIZATION_CONDA_ENV}"
elif ! command -v "${RSCRIPT_BIN}" >/dev/null 2>&1 && [[ -n "${VISUALIZATION_CONDA_ENV:-}" ]]; then
  if [[ -n "${CONDA_BASE:-}" || -f "${HOME:-}/miniconda3/etc/profile.d/conda.sh" || -n "$(command -v conda || true)" ]]; then
    log "Rscript is not in PATH; trying conda environment '${VISUALIZATION_CONDA_ENV}'"
    export ENV_BACKEND="conda"
    export CONDA_ENV="${VISUALIZATION_CONDA_ENV}"
  fi
fi

STEP_DIR="090-visualizations"
if is_done "${STEP_DIR}" "visualize"; then
  log "Visualizations already completed; skipping"
  exit 0
fi

activate_runtime
if ! command -v "${RSCRIPT_BIN}" >/dev/null 2>&1; then
  die "Required command not found in PATH: ${RSCRIPT_BIN}. Set ENV_BACKEND=conda and VISUALIZATION_CONDA_ENV to an environment that provides Rscript, or set RSCRIPT_BIN to the full Rscript path."
fi
"${RSCRIPT_BIN}" "${SCRIPT_DIR}/r/visualize_integrative.R" \
  --project-dir "${INTEGRATION_OUTPUT_DIR}" \
  --outdir "${INTEGRATION_OUTPUT_DIR}/${STEP_DIR}"
mark_done "${STEP_DIR}" "visualize"
