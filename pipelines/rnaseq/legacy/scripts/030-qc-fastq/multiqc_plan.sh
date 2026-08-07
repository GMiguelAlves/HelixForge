#!/bin/bash
#SBATCH --job-name=multiqc_030
#SBATCH --output=logs/multiqc/multiqc_%j.out
#SBATCH --error=logs/multiqc/multiqc_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: sbatch $0 <PROJECT> [SCRATCH_ROOT]"
    exit 1
fi

PROJECT=$1
SCRATCH_ROOT_ARG="${2:-}"

resolve_pipeline_config() {
    if [[ -n "${PIPELINE_CONFIG:-}" && -f "$PIPELINE_CONFIG" ]]; then echo "$PIPELINE_CONFIG"; return 0; fi
    if [[ -n "${PROJECT_DIR:-}" && -f "${PROJECT_DIR}/config/pipeline_config.sh" ]]; then echo "${PROJECT_DIR}/config/pipeline_config.sh"; return 0; fi
    if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
        for candidate in "${SLURM_SUBMIT_DIR}/../config/pipeline_config.sh" "${SLURM_SUBMIT_DIR}/config/pipeline_config.sh"; do
            [[ -f "$candidate" ]] && echo "$candidate" && return 0
        done
    fi
    local script_dir; script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    for candidate in "${script_dir}/../config/pipeline_config.sh" "${script_dir}/../../config/pipeline_config.sh"; do
        [[ -f "$candidate" ]] && echo "$candidate" && return 0
    done
    return 1
}
PIPELINE_CONFIG_PATH="$(resolve_pipeline_config)" || { echo "[ERRO] Nao foi possivel localizar config/pipeline_config.sh"; exit 1; }
source "$PIPELINE_CONFIG_PATH"
activate_rna_tools

if [ -n "$SCRATCH_ROOT_ARG" ]; then
    SCRATCH_ROOT="$SCRATCH_ROOT_ARG"
fi

PROJECT_SCRATCH="${SCRATCH_ROOT}/${PROJECT}"
OUT_DIR="${PROJECT_SCRATCH}/multiqc_030"

mkdir -p "$OUT_DIR" logs/multiqc

multiqc \
    "${PROJECT_SCRATCH}/fastqc_raw" \
    "${PROJECT_SCRATCH}/fastqc_trimmed_runs" \
    "${PROJECT_SCRATCH}/fastqc_merged" \
    -o "$OUT_DIR" \
    -n "${PROJECT}_multiqc_030.html"

echo "[OK] MultiQC concluido: ${OUT_DIR}/${PROJECT}_multiqc_030.html"
