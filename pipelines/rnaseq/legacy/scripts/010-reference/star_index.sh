#!/usr/bin/env bash
#SBATCH --job-name=star_index
#SBATCH --output=logs/star_index_%j.out
#SBATCH --error=logs/star_index_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck disable=SC1091
source "${PIPELINE_CONFIG:-${PROJECT_DIR}/config/pipeline_config.sh}"

mkdir -p "$REF_DATA_DIR" "$STAR_INDEX_DIR" "$REF_LOG_DIR"

activate_rna_tools
check_command STAR

if [[ ! -s "$REF_GENOME_FA" ]]; then
    if [[ -n "$GENOME_URL" && -n "$GENOME_FA_GZ" ]]; then
        download_if_needed "$GENOME_URL" "${REF_DATA_DIR}/${GENOME_FA_GZ}"
        decompress_gzip_if_needed "${REF_DATA_DIR}/${GENOME_FA_GZ}" "$REF_GENOME_FA"
    else
        echo "[ERRO] Configure GENOME_URL ou REF_GENOME_FA em config/pipeline_config.sh." >&2
        exit 1
    fi
fi

if [[ -n "$(find "$STAR_INDEX_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    echo "[SKIP] Indice STAR ja existe em $STAR_INDEX_DIR"
    exit 0
fi

echo "[INFO] Criando indice STAR para ${ORGANISM_NAME}"
STAR --runMode genomeGenerate \
     --genomeDir "$STAR_INDEX_DIR" \
     --genomeFastaFiles "$REF_GENOME_FA" \
     --runThreadN "${SLURM_CPUS_PER_TASK:-$THREADS}" \
     --genomeSAindexNbases "$STAR_GENOME_SA_INDEX_NBASES"

echo "[OK] Indice STAR criado em $STAR_INDEX_DIR"
