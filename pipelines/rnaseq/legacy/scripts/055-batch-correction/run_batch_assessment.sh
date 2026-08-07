#!/bin/bash
#
# Coordinate step 055a: assess batch-effect strength before/after correction.
#
# Usage:
#   bash run_batch_assessment.sh --all --batch-column dataset
#   bash run_batch_assessment.sh --all --batch-column dataset --corrected-counts all_projects/counts_batch_corrected.tsv
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
source "${PROJECT_DIR}/config/pipeline_config.sh"
STEP_DIR="$BATCH_DIR"
mkdir -p "$STEP_DIR"
cd "$STEP_DIR"

PROJECT=""
BATCH_COLUMN="$BATCH_COLUMN"
COVARIATES="$BATCH_COVARIATES"
COUNTS=""
SAMPLES=""
CORRECTED_COUNTS=""
OUTPUT_DIR=""
TOP_VARIABLE_GENES=5000
MIN_TOTAL_COUNT=10
N_PCS=10
PERMUTATIONS=199
DRY_RUN=0

usage() {
    echo "Uso: $0 [PROJECT|--all] [opcoes]"
    echo ""
    echo "Opcoes:"
    echo "  --counts PATH              Matriz de counts da etapa 050"
    echo "  --samples PATH             Tabela de amostras da etapa 050"
    echo "  --corrected-counts PATH    Matriz corrigida opcional da etapa 055"
    echo "  --output-dir PATH          Default: BATCH_DIR/<PROJECT|all_projects>/assessment"
    echo "  --batch-column COL         Default: dataset"
    echo "  --covariates A,B,C         Covariaveis biologicas tambem avaliadas"
    echo "  --top-variable-genes N     Default: 5000"
    echo "  --min-total-count N        Default: 10"
    echo "  --n-pcs N                  Default: 10"
    echo "  --permutations N           Default: 199; use 0 para desativar p-values"
    echo "  --dry-run                  Mostra comando sem executar"
    exit 1
}

if [ $# -eq 0 ]; then
    usage
fi

while [ $# -gt 0 ]; do
    case "$1" in
        --all)
            PROJECT=""
            shift
            ;;
        --counts)
            COUNTS=$2
            shift 2
            ;;
        --samples)
            SAMPLES=$2
            shift 2
            ;;
        --corrected-counts)
            CORRECTED_COUNTS=$2
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR=$2
            shift 2
            ;;
        --batch-column)
            BATCH_COLUMN=$2
            shift 2
            ;;
        --covariates)
            COVARIATES=$2
            shift 2
            ;;
        --top-variable-genes)
            TOP_VARIABLE_GENES=$2
            shift 2
            ;;
        --min-total-count)
            MIN_TOTAL_COUNT=$2
            shift 2
            ;;
        --n-pcs)
            N_PCS=$2
            shift 2
            ;;
        --permutations)
            PERMUTATIONS=$2
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            ;;
        --*)
            echo "[ERRO] Opcao desconhecida: $1"
            exit 1
            ;;
        *)
            if [ -n "$PROJECT" ]; then
                echo "[ERRO] Projeto informado mais de uma vez: $PROJECT e $1"
                exit 1
            fi
            PROJECT=$1
            shift
            ;;
    esac
done

if [ -z "$COUNTS" ]; then
    if [ -n "$PROJECT" ]; then
        COUNTS="${QUANTIFICATION_DIR}/${PROJECT}_counts_matrix.tsv"
    else
        COUNTS="${QUANTIFICATION_DIR}/counts_matrix.tsv"
    fi
fi

if [ -z "$SAMPLES" ]; then
    if [ -n "$PROJECT" ]; then
        SAMPLES="${QUANTIFICATION_DIR}/${PROJECT}_quant_samples.tsv"
    else
        SAMPLES="${QUANTIFICATION_DIR}/quant_samples.tsv"
    fi
fi

DEFAULT_RUN_DIR="${BATCH_DIR}/all_projects"
if [ -n "$PROJECT" ]; then
    DEFAULT_RUN_DIR="${BATCH_DIR}/${PROJECT}"
fi

if [ -z "$CORRECTED_COUNTS" ] && [ -f "${DEFAULT_RUN_DIR}/counts_batch_corrected.tsv" ]; then
    CORRECTED_COUNTS="${DEFAULT_RUN_DIR}/counts_batch_corrected.tsv"
fi

if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="${DEFAULT_RUN_DIR}/assessment"
fi

if [ ! -f "$COUNTS" ]; then
    echo "[ERRO] Matriz de counts nao encontrada: $COUNTS"
    exit 1
fi

if [ ! -f "$SAMPLES" ]; then
    echo "[ERRO] Tabela de amostras nao encontrada: $SAMPLES"
    exit 1
fi

if [ -n "$CORRECTED_COUNTS" ] && [ ! -f "$CORRECTED_COUNTS" ]; then
    echo "[ERRO] Matriz corrigida nao encontrada: $CORRECTED_COUNTS"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

CMD=(
    python "${SCRIPT_DIR}/assess_batch_effect.py"
    --counts "$COUNTS"
    --samples "$SAMPLES"
    --output-dir "$OUTPUT_DIR"
    --batch-column "$BATCH_COLUMN"
    --top-variable-genes "$TOP_VARIABLE_GENES"
    --min-total-count "$MIN_TOTAL_COUNT"
    --n-pcs "$N_PCS"
    --permutations "$PERMUTATIONS"
)

if [ -n "$COVARIATES" ]; then
    CMD+=(--covariates "$COVARIATES")
fi

if [ -n "$CORRECTED_COUNTS" ]; then
    CMD+=(--corrected-counts "$CORRECTED_COUNTS")
fi

echo "[INFO] Projeto: ${PROJECT:-TODOS}"
echo "[INFO] Counts: $COUNTS"
echo "[INFO] Samples: $SAMPLES"
echo "[INFO] Corrected counts: ${CORRECTED_COUNTS:-nenhuma}"
echo "[INFO] Batch column: $BATCH_COLUMN"
echo "[INFO] Covariates: ${COVARIATES:-nenhuma}"
echo "[INFO] Output dir: $OUTPUT_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY-RUN] Comando:"
    printf ' %q' "${CMD[@]}"
    echo
    exit 0
fi

activate_batch_correction
check_command python

echo "+ ${CMD[*]}"
"${CMD[@]}"
