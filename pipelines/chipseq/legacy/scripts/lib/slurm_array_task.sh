#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: slurm_array_task.sh CONFIG target_file step script}"
TARGET_FILE="${2:?Usage: slurm_array_task.sh CONFIG target_file step script}"
STEP="${3:?Usage: slurm_array_task.sh CONFIG target_file step script}"
STEP_SCRIPT="${4:?Usage: slurm_array_task.sh CONFIG target_file step script}"

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"

TASK_ID="${SLURM_ARRAY_TASK_ID:-}"
[[ -n "${TASK_ID}" ]] || die "SLURM_ARRAY_TASK_ID is not set; this wrapper must run as a Slurm array task"
[[ -s "${TARGET_FILE}" ]] || die "Array target file not found or empty: ${TARGET_FILE}"
[[ -x "${STEP_SCRIPT}" || -f "${STEP_SCRIPT}" ]] || die "Step script not found: ${STEP_SCRIPT}"

TARGET="$(awk -v n="${TASK_ID}" 'NR == n { print; found = 1; exit } END { if (!found) exit 1 }' "${TARGET_FILE}")" \
  || die "No target at array index ${TASK_ID} in ${TARGET_FILE}"
[[ -n "${TARGET}" ]] || die "Empty target at array index ${TASK_ID} in ${TARGET_FILE}"

SAFE_TARGET="$(safe_name "${TARGET}")"
STEP_LOG_DIR="${LOG_DIR}/${STEP}"
ensure_dir "${STEP_LOG_DIR}"

exec >"${STEP_LOG_DIR}/${SAFE_TARGET}.out" 2>"${STEP_LOG_DIR}/${SAFE_TARGET}.err"

log "Array task ${SLURM_ARRAY_JOB_ID:-unknown}.${TASK_ID}: ${STEP}/${TARGET}"
bash "${STEP_SCRIPT}" "${CONFIG_FILE}" "${TARGET}"
