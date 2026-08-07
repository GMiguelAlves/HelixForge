#!/bin/bash
#SBATCH --job-name=060_deg_submit
#SBATCH --output=logs/deg_submit_%j.out
#SBATCH --error=logs/deg_submit_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=7-00:00:00
#
# Generate and submit DEG analyses for projects/all, raw/corrected, via SLURM.
#
# Usage:
#   bash run_deg_analysis_slurm.sh --include-all --include-corrected
#   bash run_deg_analysis_slurm.sh --projects PRJXXXX,PRJYYYY --include-all --include-corrected --allow-missing --sbatch-dry-run
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
source "${PROJECT_DIR}/config/pipeline_config.sh"
STEP_DIR="$DEG_DIR"
mkdir -p "$STEP_DIR"
cd "$STEP_DIR"

DEFAULT_METADATA="${METADATA_FINAL_NEW:-}"
if [ -z "$DEFAULT_METADATA" ] || [ ! -f "$DEFAULT_METADATA" ]; then
    DEFAULT_METADATA="$METADATA_FINAL"
fi

METADATA="$DEFAULT_METADATA"
PROJECTS="auto"
INCLUDE_ALL=0
INCLUDE_CORRECTED=0
ALLOW_MISSING=0
SBATCH_DRY_RUN=0
CONCURRENCY="$DEG_CONCURRENCY"
EXECUTOR="$PIPELINE_EXECUTOR"
PLAN=""
TEST_VARIABLES="$DEG_TEST_VARIABLES"
DESIGN_COVARIATES="$DEG_DESIGN_COVARIATES"
DEPENDENCY=""

usage() {
    echo "Uso: $0 [opcoes]"
    echo ""
    echo "Opcoes:"
    echo "  --metadata PATH          Default: METADATA_FINAL_NEW, fallback METADATA_FINAL"
    echo "  --projects A,B|auto      Default: auto"
    echo "  --include-all            Inclui analise combinada all_projects"
    echo "  --include-corrected      Inclui matrizes corrigidas da etapa 055"
    echo "  --test-variables A,B     Default: condition,stage,sex,tissue,infection_mode"
    echo "  --design-covariates A,B  Covariaveis no design DESeq2, default vazio"
    echo "  --plan PATH              Default: work/deg_plan.csv"
    echo "  --concurrency N          Default: DEG_CONCURRENCY do config/pipeline_config.sh"
    echo "  --dependency SPEC        Ex.: afterok:12345"
    echo "  --executor slurm|local   Default: PIPELINE_EXECUTOR do config/pipeline_config.sh"
    echo "  --local                  Atalho para --executor local"
    echo "  --allow-missing          Inclui caminhos esperados mesmo se ainda nao existem"
    echo "  --sbatch-dry-run         Mostra submissao/execucao sem executar"
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --metadata)
            METADATA=$2
            shift 2
            ;;
        --projects)
            PROJECTS=$2
            shift 2
            ;;
        --include-all)
            INCLUDE_ALL=1
            shift
            ;;
        --include-corrected)
            INCLUDE_CORRECTED=1
            shift
            ;;
        --test-variables)
            TEST_VARIABLES=$2
            shift 2
            ;;
        --design-covariates)
            DESIGN_COVARIATES=$2
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
        --dependency)
            DEPENDENCY=$2
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
        --sbatch-dry-run|--dry-run)
            SBATCH_DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
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

if [ "$INCLUDE_ALL" -eq 0 ]; then
    INCLUDE_ALL=1
fi

if [ -z "$PLAN" ]; then
    PLAN="work/deg_plan.csv"
fi

mkdir -p work logs/deg

GEN_CMD=(
    python "${SCRIPT_DIR}/generate_deg_plan.py"
    --metadata "$METADATA"
    --quantification-dir "$QUANTIFICATION_DIR"
    --batch-dir "$BATCH_DIR"
    --output-root "$DEG_DIR"
    --projects "$PROJECTS"
    --test-variables "$TEST_VARIABLES"
    --design-covariates "$DESIGN_COVARIATES"
    --output "$PLAN"
)

if [ "$INCLUDE_ALL" -eq 1 ]; then
    GEN_CMD+=(--include-all)
fi

if [ "$INCLUDE_CORRECTED" -eq 1 ]; then
    GEN_CMD+=(--include-corrected)
fi

if [ "$ALLOW_MISSING" -eq 1 ]; then
    GEN_CMD+=(--allow-missing)
fi

echo "[INFO] Metadata: $METADATA"
echo "[INFO] Plano: $PLAN"
echo "[INFO] Projetos: $PROJECTS"
echo "[INFO] Include all: $INCLUDE_ALL"
echo "[INFO] Include corrected: $INCLUDE_CORRECTED"
echo "[INFO] Executor: $EXECUTOR"

activate_python_env
echo "+ ${GEN_CMD[*]}"
"${GEN_CMD[@]}"

COUNTS=$(python "${SCRIPT_DIR}/deg_plan_counts.py" "$PLAN")
ANALYSES=$(echo "$COUNTS" | awk -F= '$1=="analyses" {print $2}')

if [ -z "$ANALYSES" ]; then
    echo "[ERRO] Nao foi possivel ler numero de analises em $PLAN"
    echo "$COUNTS"
    exit 1
fi

if [ "$EXECUTOR" = "local" ]; then
    if [ "$SBATCH_DRY_RUN" -eq 1 ]; then
        echo "[DRY-RUN] Exemplo de execucao local:"
        echo "  SLURM_ARRAY_TASK_ID=1 bash ${SCRIPT_DIR}/deseq2_plan_job.sh $PLAN"
        exit 0
    fi
    echo "[INFO] Rodando DEG localmente em ordem sequencial."
    run_local_array "DESeq2" "$ANALYSES" "${SCRIPT_DIR}/deseq2_plan_job.sh" "$PLAN"
    echo "[OK] Etapa 060 concluida localmente."
    exit 0
fi

CMD=(
    sbatch --parsable
    --export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${PROJECT_DIR}/config/pipeline_config.sh,STEP_DIR=${SCRIPT_DIR}"
    --array="1-${ANALYSES}%${CONCURRENCY}"
)

if [ -n "$DEPENDENCY" ]; then
    CMD+=(--dependency="$DEPENDENCY")
fi

CMD+=("${SCRIPT_DIR}/deseq2_plan_job.sh" "$PLAN")

if [ "$SBATCH_DRY_RUN" -eq 1 ]; then
    echo "[DRY-RUN] Comando:"
    printf ' %q' "${CMD[@]}"
    echo
    exit 0
fi

JOB_ID=$("${CMD[@]}" | tail -n 1 | cut -d';' -f1)
echo "[OK] Job DEG submetido: $JOB_ID"

if [ -n "${SLURM_JOB_ID:-}" ]; then
    echo "[INFO] Aguardando jobs DEG para liberar dependencias downstream."
    wait_for_slurm_jobs "$JOB_ID"
fi
