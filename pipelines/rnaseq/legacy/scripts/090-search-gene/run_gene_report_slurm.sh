#!/bin/bash
#
# Submit step 090 gene/group report to SLURM.
#
# Usage:
#   bash run_gene_report_slurm.sh
#   bash run_gene_report_slurm.sh --genes genes.txt --title "Candidate genes"
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
source "${PROJECT_DIR}/config/pipeline_config.sh"
RESULT_DIR="$GENE_REPORT_DIR"
mkdir -p "$RESULT_DIR"
cd "$RESULT_DIR"

DEFAULT_METADATA="${METADATA_FINAL_NEW:-}"
if [ -z "$DEFAULT_METADATA" ] || [ ! -f "$DEFAULT_METADATA" ]; then
    DEFAULT_METADATA="$METADATA_FINAL"
fi

GENES="${GENE_REPORT_DIR}/genes.txt"
TPM="${EXPRESSION_MATRIX_FILE}"
EXPRESSION_UNIT="${EXPRESSION_UNIT:-TPM}"
SAMPLES="${QUANTIFICATION_DIR}/quant_samples.tsv"
METADATA="$DEFAULT_METADATA"
DEG_ROOT="$DEG_DIR"
GFF="${GENE_REPORT_ANNOTATION_FILE:-${REF_GFF3}}"
OUTPUT_DIR="${GENE_REPORT_DIR}/results"
TITLE="$GENE_REPORT_TITLE"
SBATCH_DRY_RUN=0
EXECUTOR="$PIPELINE_EXECUTOR"
EXTRA_ARGS=()

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
        --genes)
            GENES=$2
            shift 2
            ;;
        --tpm)
            TPM=$2
            shift 2
            ;;
        --expression-unit)
            EXPRESSION_UNIT=$2
            shift 2
            ;;
        --samples)
            SAMPLES=$2
            shift 2
            ;;
        --metadata)
            METADATA=$2
            shift 2
            ;;
        --deg-root)
            DEG_ROOT=$2
            shift 2
            ;;
        --gff)
            GFF=$2
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR=$2
            shift 2
            ;;
        --title)
            TITLE=$2
            shift 2
            ;;
        --sbatch-dry-run)
            SBATCH_DRY_RUN=1
            shift
            ;;
        -h|--help)
            echo "Uso: $0 [--genes genes.txt] [--title TITULO] [--sbatch-dry-run]"
            exit 0
            ;;
        *)
            EXTRA_ARGS+=("$1")
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

mkdir -p logs

if [ "$EXECUTOR" = "local" ]; then
    CMD=(
        env
        "PROJECT_DIR=${PROJECT_DIR}"
        "PIPELINE_CONFIG=${PROJECT_DIR}/config/pipeline_config.sh"
        "PIPELINE_EXECUTOR=local"
        "STEP_DIR=${SCRIPT_DIR}"
        bash "${SCRIPT_DIR}/gene_report_job.sh"
        --genes "$GENES"
        --tpm "$TPM"
        --expression-unit "$EXPRESSION_UNIT"
        --samples "$SAMPLES"
        --metadata "$METADATA"
        --deg-root "$DEG_ROOT"
        --gff "$GFF"
        --output-dir "$OUTPUT_DIR"
        --title "$TITLE"
        "${EXTRA_ARGS[@]}"
    )
else
    CMD=(
        sbatch --parsable
        --export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${PROJECT_DIR}/config/pipeline_config.sh,PIPELINE_EXECUTOR=${EXECUTOR},STEP_DIR=${SCRIPT_DIR}"
        "${SCRIPT_DIR}/gene_report_job.sh"
        --genes "$GENES"
        --tpm "$TPM"
        --expression-unit "$EXPRESSION_UNIT"
        --samples "$SAMPLES"
        --metadata "$METADATA"
        --deg-root "$DEG_ROOT"
        --gff "$GFF"
        --output-dir "$OUTPUT_DIR"
        --title "$TITLE"
        "${EXTRA_ARGS[@]}"
    )
fi

echo "[INFO] Executor: $EXECUTOR"
echo "[INFO] Genes: $GENES"
echo "[INFO] Expression matrix: $TPM"
echo "[INFO] Expression unit: $EXPRESSION_UNIT"
echo "[INFO] Samples: $SAMPLES"
echo "[INFO] Output: $OUTPUT_DIR"

if [ "$SBATCH_DRY_RUN" -eq 1 ]; then
    echo "[DRY-RUN] Comando:"
    printf ' %q' "${CMD[@]}"
    echo
    exit 0
fi

if [ "$EXECUTOR" = "local" ]; then
    "${CMD[@]}"
    echo "[OK] Relatorio de genes concluido localmente."
else
    JOB_ID=$("${CMD[@]}" | tail -n 1 | cut -d';' -f1)
    echo "[OK] Job gene report submetido: $JOB_ID"
fi
