#!/usr/bin/env bash
#SBATCH --job-name=salmon_index
#SBATCH --output=logs/salmon_index_%j.out
#SBATCH --error=logs/salmon_index_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck disable=SC1091
source "${PIPELINE_CONFIG:-${PROJECT_DIR}/config/pipeline_config.sh}"

mkdir -p "$REF_DATA_DIR" "$SALMON_INDEX_DIR" "$REF_LOG_DIR"

activate_rna_tools
check_command salmon

if [[ ! -s "$REF_TRANSCRIPTS_FA" ]]; then
    if [[ -n "$TRANSCRIPTS_URL" && -n "$TRANSCRIPTS_FA_GZ" ]]; then
        download_if_needed "$TRANSCRIPTS_URL" "${REF_DATA_DIR}/${TRANSCRIPTS_FA_GZ}"
        decompress_gzip_if_needed "${REF_DATA_DIR}/${TRANSCRIPTS_FA_GZ}" "$REF_TRANSCRIPTS_FA"
    else
        echo "[ERRO] Configure TRANSCRIPTS_URL ou REF_TRANSCRIPTS_FA em config/pipeline_config.sh." >&2
        exit 1
    fi
fi

echo "[INFO] Criando indice Salmon para ${ORGANISM_NAME}"
echo "[INFO] Transcritos: $REF_TRANSCRIPTS_FA"
echo "[INFO] Saida: $SALMON_INDEX_DIR"

salmon index \
    -t "$REF_TRANSCRIPTS_FA" \
    -i "$SALMON_INDEX_DIR" \
    -p "${SLURM_CPUS_PER_TASK:-$THREADS}" \
    -k "$SALMON_KMER_SIZE"

echo "[OK] Indice Salmon criado em $SALMON_INDEX_DIR"
