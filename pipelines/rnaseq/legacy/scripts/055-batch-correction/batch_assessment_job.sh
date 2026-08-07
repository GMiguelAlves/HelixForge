#!/bin/bash
#SBATCH --job-name=batch_assess
#SBATCH --output=logs/batch/batch_assess_%j.out
#SBATCH --error=logs/batch/batch_assess_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=06:00:00

set -euo pipefail

resolve_step_dir() {
    if [[ -n "${STEP_DIR:-}" && -f "${STEP_DIR}/run_batch_assessment.sh" ]]; then
        echo "$STEP_DIR"
        return 0
    fi

    if [[ -n "${SLURM_SUBMIT_DIR:-}" && -f "${SLURM_SUBMIT_DIR}/run_batch_assessment.sh" ]]; then
        echo "$SLURM_SUBMIT_DIR"
        return 0
    fi

    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "${script_dir}/run_batch_assessment.sh" ]]; then
        echo "$script_dir"
        return 0
    fi

    return 1
}

resolve_pipeline_config() {
    if [[ -n "${PIPELINE_CONFIG:-}" && -f "$PIPELINE_CONFIG" ]]; then
        echo "$PIPELINE_CONFIG"
        return 0
    fi

    if [[ -n "${PROJECT_DIR:-}" && -f "${PROJECT_DIR}/config/pipeline_config.sh" ]]; then
        echo "${PROJECT_DIR}/config/pipeline_config.sh"
        return 0
    fi

    local step_dir
    step_dir="$(resolve_step_dir)" || return 1
    if [[ -f "${step_dir}/../config/pipeline_config.sh" ]]; then
        echo "${step_dir}/../config/pipeline_config.sh"
        return 0
    fi
    if [[ -f "${step_dir}/../../config/pipeline_config.sh" ]]; then
        echo "${step_dir}/../../config/pipeline_config.sh"
        return 0
    fi

    return 1
}

STEP_DIR_PATH="$(resolve_step_dir)" || {
    echo "[ERRO] Nao foi possivel localizar a etapa 055."
    echo "[ERRO] Defina STEP_DIR ao submeter o job."
    exit 1
}

PIPELINE_CONFIG_PATH="$(resolve_pipeline_config)" || {
    echo "[ERRO] Nao foi possivel localizar config/pipeline_config.sh"
    echo "[ERRO] Defina PIPELINE_CONFIG ou PROJECT_DIR ao submeter o job."
    exit 1
}

source "$PIPELINE_CONFIG_PATH"
mkdir -p "${BATCH_DIR}/logs/batch"
cd "$BATCH_DIR"

echo "[INFO] SLURM job: ${SLURM_JOB_ID:-NA}"
echo "[INFO] STEP_DIR: $STEP_DIR_PATH"
echo "[INFO] OUTPUT_DIR: $BATCH_DIR"
echo "[INFO] PIPELINE_CONFIG: $PIPELINE_CONFIG_PATH"

bash "${STEP_DIR_PATH}/run_batch_assessment.sh" "$@"
