#!/bin/bash
#SBATCH --job-name=merge_samples
#SBATCH --output=logs/merge_samples/merge_samples_%A_%a.out
#SBATCH --error=logs/merge_samples/merge_samples_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=06:00:00

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: sbatch --array=1-N $0 <QC_PLAN.csv>"
    exit 1
fi

PLAN=$1

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
activate_python_env

SCRIPT_DIR="${QC_SCRIPTS_DIR}"

mkdir -p logs/merge_samples

if [ -z "${SLURM_ARRAY_TASK_ID:-}" ]; then
    echo "[ERRO] Execute como job array: sbatch --array=1-N ..."
    exit 1
fi

SAMPLE_ID=$(
    python -c "import csv,sys; samples=sorted({r['sample_id'] for r in csv.DictReader(open(sys.argv[1], newline=''))}); print(samples[int(sys.argv[2])-1])" \
        "$PLAN" "$SLURM_ARRAY_TASK_ID"
)

python "${SCRIPT_DIR}/merge_sample_from_plan.py" \
    --plan "$PLAN" \
    --sample-id "$SAMPLE_ID"
