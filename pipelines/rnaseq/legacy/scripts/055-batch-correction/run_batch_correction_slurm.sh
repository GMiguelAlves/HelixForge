#!/bin/bash
#
# Submit step 055 batch correction to SLURM.
#
# Usage:
#   bash run_batch_correction_slurm.sh --all --batch-column dataset --covariates life_stage,tissue,sex
#   bash run_batch_correction_slurm.sh --all --sbatch-dry-run
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
source "${PROJECT_DIR}/config/pipeline_config.sh"
STEP_DIR="$BATCH_DIR"
mkdir -p "$STEP_DIR"
cd "$STEP_DIR"

SBATCH_DRY_RUN=0
EXECUTOR="$PIPELINE_EXECUTOR"
ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --executor)
            EXECUTOR=$2
            shift 2
            ;;
        --local)
            EXECUTOR="local"
            shift
            ;;
        --sbatch-dry-run)
            SBATCH_DRY_RUN=1
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

case "$EXECUTOR" in
    slurm|local)
        ;;
    *)
        echo "[ERRO] Executor invalido: $EXECUTOR. Use slurm ou local."
        exit 1
        ;;
esac

if [ "${#ARGS[@]}" -eq 0 ]; then
    echo "Uso: $0 [PROJECT|--all] [opcoes de run_batch_correction.sh] [--sbatch-dry-run]"
    exit 1
fi

mkdir -p logs/batch

if [ "$EXECUTOR" = "local" ]; then
    CMD=(
        env
        "PROJECT_DIR=${PROJECT_DIR}"
        "PIPELINE_CONFIG=${PROJECT_DIR}/config/pipeline_config.sh"
        "PIPELINE_EXECUTOR=local"
        "STEP_DIR=${SCRIPT_DIR}"
        bash "${SCRIPT_DIR}/batch_correction_job.sh"
        "${ARGS[@]}"
    )
else
    CMD=(
        sbatch --parsable
        --export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${PROJECT_DIR}/config/pipeline_config.sh,PIPELINE_EXECUTOR=${EXECUTOR},STEP_DIR=${SCRIPT_DIR}"
        "${SCRIPT_DIR}/batch_correction_job.sh"
        "${ARGS[@]}"
    )
fi

echo "[INFO] Executor: $EXECUTOR"
echo "[INFO] STEP_DIR: $SCRIPT_DIR"
echo "[INFO] OUTPUT_DIR: $STEP_DIR"
echo "[INFO] PROJECT_DIR: $PROJECT_DIR"

if [ "$SBATCH_DRY_RUN" -eq 1 ]; then
    echo "[DRY-RUN] Comando:"
    printf ' %q' "${CMD[@]}"
    echo
    exit 0
fi

if [ "$EXECUTOR" = "local" ]; then
    "${CMD[@]}"
    echo "[OK] Correcao de batch concluida localmente."
else
    JOB_ID=$("${CMD[@]}" | tail -n 1 | cut -d';' -f1)
    echo "[OK] Job batch correction submetido: $JOB_ID"
fi
