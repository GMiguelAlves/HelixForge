#!/bin/bash
#SBATCH --job-name=star_quant
#SBATCH --output=logs/star/star_%A_%a.out
#SBATCH --error=logs/star/star_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Uso: sbatch --array=1-N $0 <STAR_PLAN.csv> <STAR_INDEX>"
    exit 1
fi

PLAN=$1
INDEX_DIR=$2

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
check_command STAR

mkdir -p logs/star

if [ -z "${SLURM_ARRAY_TASK_ID:-}" ]; then
    echo "[ERRO] Execute como job array: sbatch --array=1-N ..."
    exit 1
fi

read -r SAMPLE_ID R1 R2 STAR_DIR COUNTS_FILE < <(
    python -c "import csv,sys; rows=list(csv.DictReader(open(sys.argv[1], newline=''))); r=rows[int(sys.argv[2])-1]; print(r['sample_id'], r['merged_sample_r1'], r['merged_sample_r2'], r['star_dir'], r['counts_file'], sep='\t')" \
        "$PLAN" "$SLURM_ARRAY_TASK_ID"
)

if [[ ! -f "$R1" || ! -f "$R2" ]]; then
    echo "[ERRO] FASTQs merged ausentes para ${SAMPLE_ID}"
    echo "$R1"
    echo "$R2"
    exit 1
fi

if [[ ! -d "$INDEX_DIR" ]]; then
    echo "[ERRO] STAR index ausente: $INDEX_DIR"
    exit 1
fi

if [[ -s "$COUNTS_FILE" ]]; then
    echo "[SKIP] ReadsPerGene.out.tab ja existe para ${SAMPLE_ID}: $COUNTS_FILE"
    exit 0
fi

mkdir -p "$STAR_DIR"

CMD=(
    STAR
    --genomeDir "$INDEX_DIR"
    --readFilesIn "$R1" "$R2"
    --runThreadN "${SLURM_CPUS_PER_TASK:-$THREADS}"
    --outFileNamePrefix "${STAR_DIR}/"
    --outSAMtype BAM SortedByCoordinate
    --quantMode GeneCounts
)

if [[ -n "${STAR_READ_FILES_COMMAND:-}" ]]; then
    CMD+=(--readFilesCommand "$STAR_READ_FILES_COMMAND")
fi

if [[ -n "${STAR_EXTRA_ARGS:-}" ]]; then
    # shellcheck disable=SC2206
    EXTRA_ARGS=($STAR_EXTRA_ARGS)
    CMD+=("${EXTRA_ARGS[@]}")
fi

echo "[INFO] STAR quant: ${SAMPLE_ID}"
echo "+ ${CMD[*]}"
"${CMD[@]}"

if [[ ! -s "$COUNTS_FILE" ]]; then
    echo "[ERRO] STAR nao gerou counts esperados: $COUNTS_FILE"
    exit 1
fi

echo "[OK] STAR concluido: ${SAMPLE_ID}"
