#!/bin/bash
#SBATCH --job-name=040_star_project
#SBATCH --output=logs/star_project_%j.out
#SBATCH --error=logs/star_project_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=7-00:00:00
#
# Coordinate STAR alignment/gene-count quantification for one project.
#

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Uso: $0 <PROJECT> <QC_PLAN.csv> [opcoes]"
    echo ""
    echo "Opcoes:"
    echo "  --index PATH          Default: STAR_QUANT_INDEX_DIR do config/pipeline_config.sh"
    echo "  --output-root PATH    Default: STAR_QUANT_DIR do config/pipeline_config.sh"
    echo "  --plan PATH           Default: work/<PROJECT>_star_plan.csv"
    echo "  --concurrency N       Default: STAR_QUANT_CONCURRENCY do config/pipeline_config.sh"
    echo "  --allow-missing       Permite gerar plano mesmo com FASTQs merged ausentes"
    echo "  --executor slurm|local Default: PIPELINE_EXECUTOR do config/pipeline_config.sh"
    echo "  --local               Atalho para --executor local"
    echo "  --dry-run             Mostra comandos sem submeter jobs"
    exit 1
fi

PROJECT=$1
QC_PLAN=$2
shift 2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
source "${PROJECT_DIR}/config/pipeline_config.sh"
STEP_DIR="$ALIGN_DIR"
mkdir -p "$STEP_DIR"
cd "$STEP_DIR"

INDEX_DIR="$STAR_QUANT_INDEX_DIR"
OUTPUT_ROOT="$STAR_QUANT_DIR"
PLAN=""
CONCURRENCY="$STAR_QUANT_CONCURRENCY"
EXECUTOR="$PIPELINE_EXECUTOR"
ALLOW_MISSING=0
DRY_RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --index)
            INDEX_DIR=$2
            shift 2
            ;;
        --output-root)
            OUTPUT_ROOT=$2
            shift 2
            ;;
        --plan)
            PLAN=$2
            shift 2
            ;;
        --concurrency)
            CONCURRENCY=$2
            shift 2
            ;;
        --executor)
            EXECUTOR=$2
            shift 2
            ;;
        --local)
            EXECUTOR="local"
            shift
            ;;
        --allow-missing)
            ALLOW_MISSING=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        *)
            echo "[ERRO] Opcao desconhecida: $1"
            exit 1
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

if [ -z "$PLAN" ]; then
    PLAN="work/${PROJECT}_star_plan.csv"
fi

mkdir -p work logs/star

run_cmd() {
    echo "+ $*"
    if [ "$DRY_RUN" -eq 0 ]; then
        "$@"
    fi
}

submit_job() {
    local output
    echo "+ $*" >&2
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "DRYRUN_JOB"
        return 0
    fi
    output=$("$@")
    echo "$output" >&2
    echo "$output" | tail -n 1 | cut -d';' -f1
}

echo "[INFO] Projeto: $PROJECT"
echo "[INFO] QC plan: $QC_PLAN"
echo "[INFO] STAR index: $INDEX_DIR"
echo "[INFO] Output root: $OUTPUT_ROOT"
echo "[INFO] STAR plan: $PLAN"
echo "[INFO] Executor: $EXECUTOR"

GEN_PLAN_CMD=(
    python "${SCRIPT_DIR}/generate_star_plan.py"
    --qc-plan "$QC_PLAN"
    --project "$PROJECT"
    --output-root "$OUTPUT_ROOT"
    --output "$PLAN"
)

if [ "$ALLOW_MISSING" -eq 1 ]; then
    GEN_PLAN_CMD+=(--allow-missing)
fi

activate_python_env
run_cmd "${GEN_PLAN_CMD[@]}"

if [ "$DRY_RUN" -eq 1 ]; then
    if [ "$EXECUTOR" = "local" ]; then
        echo "[DRY-RUN] Exemplo de execucao local:"
        echo "  SLURM_ARRAY_TASK_ID=1 bash ${SCRIPT_DIR}/star_quant_plan.sh $PLAN $INDEX_DIR"
    else
        echo "[DRY-RUN] Exemplo de submissao:"
        echo "  sbatch --parsable --array=1-SAMPLES%${CONCURRENCY} ${SCRIPT_DIR}/star_quant_plan.sh $PLAN $INDEX_DIR"
    fi
    exit 0
fi

COUNTS=$(python "${SCRIPT_DIR}/star_plan_counts.py" "$PLAN")
SAMPLES=$(echo "$COUNTS" | awk -F= '$1=="samples" {print $2}')

if [ -z "$SAMPLES" ]; then
    echo "[ERRO] Nao foi possivel ler samples de $PLAN"
    echo "$COUNTS"
    exit 1
fi

echo "[INFO] Amostras para STAR: $SAMPLES"

if [ "$EXECUTOR" = "local" ]; then
    echo "[INFO] Rodando STAR localmente em ordem sequencial."
    run_local_array "STAR quant" "$SAMPLES" "${SCRIPT_DIR}/star_quant_plan.sh" "$PLAN" "$INDEX_DIR"
    echo "[OK] Etapa 040 STAR concluida localmente."
    exit 0
fi

STAR_JOB=$(
    submit_job sbatch --parsable \
        --export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${PROJECT_DIR}/config/pipeline_config.sh,PIPELINE_EXECUTOR=${EXECUTOR}" \
        --array="1-${SAMPLES}%${CONCURRENCY}" \
        "${SCRIPT_DIR}/star_quant_plan.sh" "$PLAN" "$INDEX_DIR"
)

echo "[OK] Job STAR submetido: $STAR_JOB"

if [ -n "${SLURM_JOB_ID:-}" ]; then
    echo "[INFO] Aguardando job STAR para liberar dependencias downstream."
    wait_for_slurm_jobs "$STAR_JOB"
fi
