#!/bin/bash
#
# Coordinate step 050: import quantification outputs into gene-level matrices.
# Supports Salmon quant.sf through tximport and STAR ReadsPerGene.out.tab.
#
# Usage:
#   bash run_quantification.sh PRJXXXX
#   bash run_quantification.sh --all
#   bash run_quantification.sh PRJXXXX --allow-missing --dry-run
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
source "${PROJECT_DIR}/config/pipeline_config.sh"
STEP_DIR="$QUANTIFICATION_DIR"
mkdir -p "$STEP_DIR"
cd "$STEP_DIR"

DEFAULT_METADATA="$(metadata_default)"
if [ ! -f "$DEFAULT_METADATA" ]; then
    DEFAULT_METADATA="$METADATA_FINAL"
fi

PROJECT=""
METADATA="$DEFAULT_METADATA"
METHOD="$QUANT_METHOD"
QUANT_ROOT=""
GTF="$REF_GTF"
OUTPUT_DIR="$QUANTIFICATION_DIR"
COUNTS_NAME=""
TPM_NAME=""
SAMPLE_TABLE_NAME=""
TX2GENE_OUT=""
STAR_COUNT_COLUMN="$STAR_GENECOUNT_COLUMN"
ALLOW_MISSING=0
DRY_RUN=0

usage() {
    echo "Uso: $0 [PROJECT|--all] [opcoes]"
    echo ""
    echo "Opcoes:"
    echo "  --method salmon|star    Default: QUANT_METHOD do config/pipeline_config.sh"
    echo "  --metadata PATH          Default: METADATA_FINAL_NEW, com fallback para METADATA_FINAL"
    echo "  --quant-root PATH        Default: QUANT_DIR (salmon) ou STAR_QUANT_DIR (star)"
    echo "  --gtf PATH               Default: REF_GTF; usado somente para Salmon/tximport"
    echo "  --output-dir PATH        Default: QUANTIFICATION_DIR do config/pipeline_config.sh"
    echo "  --counts-name NAME       Nome do arquivo de counts"
    echo "  --tpm-name NAME          Nome da matriz de expressao (TPM no Salmon; CPM no STAR)"
    echo "  --expression-name NAME   Alias de --tpm-name para STAR/relatorios genericos"
    echo "  --sample-table-name NAME Nome da tabela de amostras importadas"
    echo "  --tx2gene-out PATH       Default: <output-dir>/tx2gene.tsv"
    echo "  --star-count-column NAME unstranded, stranded_forward ou stranded_reverse"
    echo "  --allow-missing          Importa somente arquivos de quantificacao existentes"
    echo "  --dry-run                Mostra o comando sem executar"
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
        --method)
            METHOD=$2
            shift 2
            ;;
        --metadata)
            METADATA=$2
            shift 2
            ;;
        --quant-root)
            QUANT_ROOT=$2
            shift 2
            ;;
        --gtf)
            GTF=$2
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR=$2
            shift 2
            ;;
        --counts-name)
            COUNTS_NAME=$2
            shift 2
            ;;
        --tpm-name)
            TPM_NAME=$2
            shift 2
            ;;
        --expression-name)
            TPM_NAME=$2
            shift 2
            ;;
        --sample-table-name)
            SAMPLE_TABLE_NAME=$2
            shift 2
            ;;
        --tx2gene-out)
            TX2GENE_OUT=$2
            shift 2
            ;;
        --star-count-column)
            STAR_COUNT_COLUMN=$2
            shift 2
            ;;
        --allow-missing)
            ALLOW_MISSING=1
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

METHOD="${METHOD,,}"
STAR_COUNT_COLUMN="${STAR_COUNT_COLUMN,,}"

case "$METHOD" in
    salmon|star)
        ;;
    *)
        echo "[ERRO] Metodo invalido: $METHOD. Use salmon ou star."
        exit 1
        ;;
esac

if [ -z "$QUANT_ROOT" ]; then
    if [ "$METHOD" = "star" ]; then
        QUANT_ROOT="$STAR_QUANT_DIR"
    else
        QUANT_ROOT="$QUANT_DIR"
    fi
fi

if [ ! -f "$METADATA" ]; then
    echo "[ERRO] Metadata nao encontrado: $METADATA"
    exit 1
fi

if [ ! -d "$QUANT_ROOT" ]; then
    echo "[ERRO] Quant root nao encontrado: $QUANT_ROOT"
    exit 1
fi

if [ "$METHOD" = "salmon" ] && [ ! -f "$GTF" ]; then
    echo "[ERRO] GTF nao encontrado: $GTF"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

if [ "$METHOD" = "star" ]; then
    CMD=(
        python "${SCRIPT_DIR}/import_star_counts.py"
        --metadata "$METADATA"
        --quant-root "$QUANT_ROOT"
        --output-dir "$OUTPUT_DIR"
        --count-column "$STAR_COUNT_COLUMN"
    )
else
    CMD=(
        Rscript "${SCRIPT_DIR}/txtimport_quant.R"
        --metadata "$METADATA"
        --quant-root "$QUANT_ROOT"
        --gtf "$GTF"
        --output-dir "$OUTPUT_DIR"
    )
fi

if [ -n "$PROJECT" ]; then
    CMD+=(--project "$PROJECT")
fi

if [ -n "$COUNTS_NAME" ]; then
    CMD+=(--counts-name "$COUNTS_NAME")
fi

if [ -n "$TPM_NAME" ]; then
    if [ "$METHOD" = "star" ]; then
        CMD+=(--expression-name "$TPM_NAME")
    else
        CMD+=(--tpm-name "$TPM_NAME")
    fi
fi

if [ -n "$SAMPLE_TABLE_NAME" ]; then
    CMD+=(--sample-table-name "$SAMPLE_TABLE_NAME")
fi

if [ "$METHOD" = "salmon" ] && [ -n "$TX2GENE_OUT" ]; then
    CMD+=(--tx2gene-out "$TX2GENE_OUT")
fi

if [ "$ALLOW_MISSING" -eq 1 ]; then
    CMD+=(--allow-missing)
fi

echo "[INFO] Metodo: $METHOD"
echo "[INFO] Projeto: ${PROJECT:-TODOS}"
echo "[INFO] Metadata: $METADATA"
echo "[INFO] Quant root: $QUANT_ROOT"
[ "$METHOD" = "salmon" ] && echo "[INFO] GTF: $GTF"
[ "$METHOD" = "star" ] && echo "[INFO] STAR count column: $STAR_COUNT_COLUMN"
echo "[INFO] Output dir: $OUTPUT_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY-RUN] Comando:"
    printf ' %q' "${CMD[@]}"
    echo
    exit 0
fi

if [ "$METHOD" = "star" ]; then
    activate_python_env
    check_command python
else
    activate_r_analysis
    check_command Rscript
fi

echo "+ ${CMD[*]}"
"${CMD[@]}"
