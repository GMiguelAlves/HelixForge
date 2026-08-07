#!/bin/bash
#SBATCH --job-name=salmon_quant
#SBATCH --output=logs/salmon/salmon_%A_%a.out
#SBATCH --error=logs/salmon/salmon_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Uso: sbatch --array=1-N $0 <SALMON_PLAN.csv> <SALMON_INDEX>"
    exit 1
fi

PLAN=$1
INDEX_DIR=$2

resolve_pipeline_config() {
    if [[ -n "${PIPELINE_CONFIG:-}" && -f "$PIPELINE_CONFIG" ]]; then
        echo "$PIPELINE_CONFIG"
        return 0
    fi

    if [[ -n "${PROJECT_DIR:-}" && -f "${PROJECT_DIR}/config/pipeline_config.sh" ]]; then
        echo "${PROJECT_DIR}/config/pipeline_config.sh"
        return 0
    fi

    if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
        for candidate in \
            "${SLURM_SUBMIT_DIR}/../config/pipeline_config.sh" \
            "${SLURM_SUBMIT_DIR}/config/pipeline_config.sh"
        do
            if [[ -f "$candidate" ]]; then
                echo "$candidate"
                return 0
            fi
        done
    fi

    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    for candidate in \
        "${script_dir}/../config/pipeline_config.sh" \
        "${script_dir}/../../config/pipeline_config.sh"
    do
        if [[ -f "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

PIPELINE_CONFIG_PATH="$(resolve_pipeline_config)" || {
    echo "[ERRO] Nao foi possivel localizar config/pipeline_config.sh"
    echo "[ERRO] Defina PIPELINE_CONFIG ou PROJECT_DIR antes de submeter o job."
    exit 1
}

source "$PIPELINE_CONFIG_PATH"
activate_rna_tools

mkdir -p logs/salmon

if [ -z "${SLURM_ARRAY_TASK_ID:-}" ]; then
    echo "[ERRO] Execute como job array: sbatch --array=1-N ..."
    exit 1
fi

read -r SAMPLE_ID R1 R2 QUANT_DIR < <(
    python -c "import csv,sys; rows=list(csv.DictReader(open(sys.argv[1], newline=''))); r=rows[int(sys.argv[2])-1]; print(r['sample_id'], r['merged_sample_r1'], r['merged_sample_r2'], r['quant_dir'], sep='\t')" \
        "$PLAN" "$SLURM_ARRAY_TASK_ID"
)

if [[ ! -f "$R1" || ! -f "$R2" ]]; then
    echo "[ERRO] FASTQs merged ausentes para ${SAMPLE_ID}"
    echo "$R1"
    echo "$R2"
    exit 1
fi

if [[ ! -d "$INDEX_DIR" ]]; then
    echo "[ERRO] Salmon index ausente: $INDEX_DIR"
    exit 1
fi

if [[ -s "${QUANT_DIR}/quant.sf" ]]; then
    echo "[SKIP] quant.sf ja existe para ${SAMPLE_ID}: ${QUANT_DIR}/quant.sf"
    exit 0
fi

mkdir -p "$(dirname "$QUANT_DIR")"

echo "[INFO] Salmon quant: ${SAMPLE_ID}"
salmon quant \
    -i "$INDEX_DIR" \
    -l A \
    -1 "$R1" \
    -2 "$R2" \
    -p "${SLURM_CPUS_PER_TASK:-$THREADS}" \
    --validateMappings \
    -o "$QUANT_DIR"

echo "[OK] Salmon concluido: ${SAMPLE_ID}"
