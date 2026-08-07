#!/bin/bash
#SBATCH --job-name=deseq2_plan
#SBATCH --output=logs/deg/deseq2_%A_%a.out
#SBATCH --error=logs/deg/deseq2_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=24:00:00

set -euo pipefail

export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

if [ $# -lt 1 ]; then
    echo "Uso: sbatch --array=1-N $0 <DEG_PLAN.csv>"
    exit 1
fi

PLAN=$1

resolve_step_dir() {
    if [[ -n "${STEP_DIR:-}" && -f "${STEP_DIR}/deseq2_analysis.R" ]]; then
        echo "$STEP_DIR"
        return 0
    fi
    if [[ -n "${SLURM_SUBMIT_DIR:-}" && -f "${SLURM_SUBMIT_DIR}/deseq2_analysis.R" ]]; then
        echo "$SLURM_SUBMIT_DIR"
        return 0
    fi
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "${script_dir}/deseq2_analysis.R" ]]; then
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
    echo "[ERRO] Nao foi possivel localizar a etapa 060."
    exit 1
}

PIPELINE_CONFIG_PATH="$(resolve_pipeline_config)" || {
    echo "[ERRO] Nao foi possivel localizar config/pipeline_config.sh"
    exit 1
}

source "$PIPELINE_CONFIG_PATH"

mkdir -p "${DEG_DIR}/logs/deg"
cd "$DEG_DIR"

if [ -z "${SLURM_ARRAY_TASK_ID:-}" ]; then
    echo "[ERRO] Execute como job array: sbatch --array=1-N ..."
    exit 1
fi

activate_python_env

read -r ANALYSIS_ID COUNTS SAMPLES OUTPUT_DIR TEST_VARIABLES DESIGN_COVARIATES < <(
    python -c "import csv,sys; rows=list(csv.DictReader(open(sys.argv[1], newline='', encoding='utf-8'))); r=rows[int(sys.argv[2])-1]; print(r['analysis_id'], r['counts'], r['samples'], r['output_dir'], r['test_variables'], r['design_covariates'], sep='\t')" \
        "$PLAN" "$SLURM_ARRAY_TASK_ID"
)

echo "[INFO] Analise: $ANALYSIS_ID"
echo "[INFO] Counts: $COUNTS"
echo "[INFO] Samples: $SAMPLES"
echo "[INFO] Output: $OUTPUT_DIR"

activate_r_analysis

Rscript "${STEP_DIR_PATH}/deseq2_analysis.R" \
    --analysis-id "$ANALYSIS_ID" \
    --counts "$COUNTS" \
    --samples "$SAMPLES" \
    --metadata "$(metadata_default)" \
    --output-dir "$OUTPUT_DIR" \
    --gff "$REF_GFF3" \
    --test-variables "$TEST_VARIABLES" \
    --design-covariates "$DESIGN_COVARIATES"
