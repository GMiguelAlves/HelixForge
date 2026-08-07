#!/bin/bash
#
# Coordinate step 055: batch-effect assessment/correction with pyComBat-Seq.
#
# Usage:
#   bash run_batch_correction.sh --all
#   bash run_batch_correction.sh PRJXXXX --batch-column sequencing_batch --skip-if-single-batch
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
OUTPUT_DIR=""
ALLOW_CONFOUNDED=0
SKIP_SINGLE_BATCH=0
DRY_RUN=0

usage() {
    echo "Uso: $0 [PROJECT|--all] [opcoes]"
    echo ""
    echo "Opcoes:"
    echo "  --counts PATH              Matriz de counts da etapa 050"
    echo "  --samples PATH             Tabela de amostras da etapa 050"
    echo "  --output-dir PATH          Default: BATCH_DIR do config/pipeline_config.sh"
    echo "  --batch-column COL         Default: dataset"
    echo "  --covariates A,B,C         Covariaveis biologicas categoricas a preservar"
    echo "  --allow-confounded         Permite batch/covariavel fortemente confundidos"
    echo "  --skip-if-single-batch     Escreve copia sem correcao se houver um unico batch"
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
        --allow-confounded)
            ALLOW_CONFOUNDED=1
            shift
            ;;
        --skip-if-single-batch)
            SKIP_SINGLE_BATCH=1
            shift
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

if [ -z "$OUTPUT_DIR" ]; then
    if [ -n "$PROJECT" ]; then
        OUTPUT_DIR="${BATCH_DIR}/${PROJECT}"
    else
        OUTPUT_DIR="${BATCH_DIR}/all_projects"
    fi
fi

if [ ! -f "$COUNTS" ]; then
    echo "[ERRO] Matriz de counts nao encontrada: $COUNTS"
    exit 1
fi

if [ ! -f "$SAMPLES" ]; then
    echo "[ERRO] Tabela de amostras nao encontrada: $SAMPLES"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

CMD=(
    python "${SCRIPT_DIR}/apply_batch_correction.py"
    --counts "$COUNTS"
    --samples "$SAMPLES"
    --output-dir "$OUTPUT_DIR"
    --batch-column "$BATCH_COLUMN"
)

if [ -n "$COVARIATES" ]; then
    CMD+=(--covariates "$COVARIATES")
fi

if [ "$ALLOW_CONFOUNDED" -eq 1 ]; then
    CMD+=(--allow-confounded)
fi

if [ "$SKIP_SINGLE_BATCH" -eq 1 ]; then
    CMD+=(--skip-if-single-batch)
fi

echo "[INFO] Projeto: ${PROJECT:-TODOS}"
echo "[INFO] Counts: $COUNTS"
echo "[INFO] Samples: $SAMPLES"
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
