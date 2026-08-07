#!/usr/bin/env bash
#SBATCH --job-name=fastq_download
#SBATCH --output=logs/fastq_download_%j.log
#SBATCH --error=logs/fastq_download_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=05:00:00

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Uso: sbatch $0 <PROJECT_ID>"
    exit 1
fi

PROJECT_ID="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck disable=SC1091
source "${PIPELINE_CONFIG:-${PROJECT_DIR}/config/pipeline_config.sh}"

BASE_DIR="$DOWNLOAD_DIR"
DATASET_DIR="${DATASET_CONFIG_DIR}/${PROJECT_ID}"
CONFIG="${DATASET_DIR}/config.yaml"
OUTDIR="${SCRATCH_ROOT}/${PROJECT_ID}/fastq_ftp"

mkdir -p "$OUTDIR" "${BASE_DIR}/logs"

if [[ ! -f "$CONFIG" ]]; then
    echo "[ERRO] Config do dataset nao encontrado: $CONFIG"
    exit 1
fi

THREADS_FROM_CONFIG=$(awk -F: '/^[[:space:]]*threads:/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "$CONFIG")
LINK_FILE=$(awk -F: '/^[[:space:]]*link_file:/ {gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}' "$CONFIG")

THREADS_FROM_CONFIG="${THREADS_FROM_CONFIG:-$DOWNLOAD_THREADS}"
if [[ -z "$LINK_FILE" ]]; then
    echo "[ERRO] Campo download.link_file ausente em $CONFIG"
    exit 1
fi

LINK_PATH="${DATASET_DIR}/${LINK_FILE}"
if [[ ! -f "$LINK_PATH" ]]; then
    echo "[ERRO] Arquivo de links nao encontrado: $LINK_PATH"
    exit 1
fi

activate_rna_tools
check_command wget

TMP_LINKS=$(mktemp)
grep -Eo "(ftp|https)://[^ \"'()]+" "$LINK_PATH" > "$TMP_LINKS" || true

if [[ ! -s "$TMP_LINKS" ]]; then
    rm -f "$TMP_LINKS"
    echo "[ERRO] Nenhuma URL ftp/https encontrada em $LINK_PATH"
    exit 1
fi

echo "[INFO] Projeto: $PROJECT_ID"
echo "[INFO] Organismo: $ORGANISM_NAME"
echo "[INFO] Saida FASTQ: $OUTDIR"
echo "[INFO] Threads download: $THREADS_FROM_CONFIG"

(
    cd "$OUTDIR"
    xargs -n 1 -P "$THREADS_FROM_CONFIG" wget -c < "$TMP_LINKS"
)

rm -f "$TMP_LINKS"
echo "[OK] Download concluido: $PROJECT_ID"
