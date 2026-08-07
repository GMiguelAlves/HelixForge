#!/bin/bash
#SBATCH --job-name=gene_report
#SBATCH --output=logs/gene_report_%j.out
#SBATCH --error=logs/gene_report_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=04:00:00

set -euo pipefail

export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

resolve_step_dir() {
    if [[ -n "${STEP_DIR:-}" && -f "${STEP_DIR}/gene_set_report.R" ]]; then
        echo "$STEP_DIR"
        return 0
    fi
    if [[ -n "${SLURM_SUBMIT_DIR:-}" && -f "${SLURM_SUBMIT_DIR}/gene_set_report.R" ]]; then
        echo "$SLURM_SUBMIT_DIR"
        return 0
    fi
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "${script_dir}/gene_set_report.R" ]]; then
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
    echo "[ERRO] Nao foi possivel localizar a etapa 090."
    exit 1
}

PIPELINE_CONFIG_PATH="$(resolve_pipeline_config)" || {
    echo "[ERRO] Nao foi possivel localizar config/pipeline_config.sh"
    exit 1
}

source "$PIPELINE_CONFIG_PATH"
mkdir -p "${GENE_REPORT_DIR}/logs"
cd "$GENE_REPORT_DIR"

activate_r_analysis
check_command Rscript

Rscript "${STEP_DIR_PATH}/gene_set_report.R" "$@"
