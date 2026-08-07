#!/usr/bin/env bash
#SBATCH --job-name=star_index_gtf
#SBATCH --output=logs/star_index_gtf_%j.out
#SBATCH --error=logs/star_index_gtf_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=180G
#SBATCH --time=08:00:00

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck disable=SC1091
source "${PIPELINE_CONFIG:-${PROJECT_DIR}/config/pipeline_config.sh}"

mkdir -p "$REF_DATA_DIR" "$STAR_INDEX_GTF_DIR" "$REF_LOG_DIR"

activate_rna_tools
check_command STAR

if [[ -n "$(find "$STAR_INDEX_GTF_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    echo "[SKIP] Indice STAR+GTF ja existe em $STAR_INDEX_GTF_DIR"
    exit 0
fi

if [[ ! -s "$REF_GENOME_FA" ]]; then
    if [[ -n "$GENOME_URL" && -n "$GENOME_FA_GZ" ]]; then
        download_if_needed "$GENOME_URL" "${REF_DATA_DIR}/${GENOME_FA_GZ}"
        decompress_gzip_if_needed "${REF_DATA_DIR}/${GENOME_FA_GZ}" "$REF_GENOME_FA"
    else
        echo "[ERRO] Configure GENOME_URL ou REF_GENOME_FA em config/pipeline_config.sh." >&2
        exit 1
    fi
fi

if [[ ! -s "$REF_GTF" ]]; then
    if [[ -n "$GTF_URL" && -n "$GTF_GZ" ]]; then
        download_if_needed "$GTF_URL" "${REF_DATA_DIR}/${GTF_GZ}"
        decompress_gzip_if_needed "${REF_DATA_DIR}/${GTF_GZ}" "$REF_GTF"
    elif [[ -s "$REF_GFF3" ]]; then
        check_command gffread
        echo "[INFO] Convertendo GFF3 para GTF: $REF_GFF3"
        gffread "$REF_GFF3" -T -o "$REF_GTF"
    elif [[ -n "$GFF3_URL" && -n "$GFF3_GZ" ]]; then
        download_if_needed "$GFF3_URL" "${REF_DATA_DIR}/${GFF3_GZ}"
        decompress_gzip_if_needed "${REF_DATA_DIR}/${GFF3_GZ}" "$REF_GFF3"
        check_command gffread
        gffread "$REF_GFF3" -T -o "$REF_GTF"
    else
        echo "[ERRO] Configure REF_GTF/GTF_URL ou REF_GFF3/GFF3_URL em config/pipeline_config.sh." >&2
        exit 1
    fi
fi

echo "[INFO] Criando indice STAR com GTF para ${ORGANISM_NAME}"
STAR --runMode genomeGenerate \
  --runThreadN "${SLURM_CPUS_PER_TASK:-$THREADS}" \
  --genomeDir "$STAR_INDEX_GTF_DIR" \
  --genomeFastaFiles "$REF_GENOME_FA" \
  --sjdbGTFfile "$REF_GTF" \
  --genomeSAindexNbases "$STAR_GTF_GENOME_SA_INDEX_NBASES" \
  --limitGenomeGenerateRAM "$STAR_LIMIT_GENOME_GENERATE_RAM"

echo "[OK] Indice STAR+GTF criado em $STAR_INDEX_GTF_DIR"
