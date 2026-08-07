#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:-config/pipeline_config.sh}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP_DIR="${REF_DIR:-${OUTPUT_DIR}/010-reference}"
NAME="reference"

if is_done "010-reference" "${NAME}"; then
  log "Reference step already completed; skipping"
  exit 0
fi

create_output_tree
ensure_dir "${STEP_DIR}/bowtie2" "${STEP_DIR}/annotation" "${STEP_DIR}/qc"

[[ -f "${GENOME_FASTA}" ]] || die "GENOME_FASTA not found: ${GENOME_FASTA}"
[[ -f "${ANNOTATION_FILE}" ]] || die "ANNOTATION_FILE not found: ${ANNOTATION_FILE}"

require_cmd samtools
require_cmd "${PYTHON_BIN}"
if [[ "${GENOME_FASTA}" == *.gz || "${ANNOTATION_FILE}" == *.gz ]]; then
  require_cmd gzip
fi

WORK_GENOME_FASTA="$(prepare_reference_input "${GENOME_FASTA}" "${REF_DATA_DIR}")"
WORK_ANNOTATION_FILE="$(prepare_reference_input "${ANNOTATION_FILE}" "${REF_DATA_DIR}")"

if [[ ! -s "${WORK_GENOME_FASTA}.fai" || "${OVERWRITE}" == "true" ]]; then
  run_cmd "samtools faidx '${WORK_GENOME_FASTA}'"
fi

CHROM_SIZES="${STEP_DIR}/chrom.sizes"
cut -f1,2 "${WORK_GENOME_FASTA}.fai" > "${CHROM_SIZES}"

case "${ALIGNER}" in
  bowtie2)
    require_cmd bowtie2-build
    if [[ ! -s "${BOWTIE2_INDEX_PREFIX}.1.bt2" && ! -s "${BOWTIE2_INDEX_PREFIX}.1.bt2l" || "${OVERWRITE}" == "true" ]]; then
      ensure_dir "$(dirname "${BOWTIE2_INDEX_PREFIX}")"
      run_cmd "bowtie2-build ${BOWTIE2_BUILD_OPTS} '${WORK_GENOME_FASTA}' '${BOWTIE2_INDEX_PREFIX}'"
    fi
    ;;
  bwa)
    require_cmd bwa
    BWA_INDEX_PREFIX="${WORK_GENOME_FASTA}"
    if [[ ! -s "${WORK_GENOME_FASTA}.bwt" || "${OVERWRITE}" == "true" ]]; then
      run_cmd "bwa index '${WORK_GENOME_FASTA}'"
    fi
    ;;
esac

"${PYTHON_BIN}" "${SCRIPT_DIR}/create_annotation_beds.py" \
  --annotation "${WORK_ANNOTATION_FILE}" \
  --chrom-sizes "${CHROM_SIZES}" \
  --outdir "${STEP_DIR}/annotation" \
  --promoter-upstream "${PROMOTER_UPSTREAM}" \
  --promoter-downstream "${PROMOTER_DOWNSTREAM}"

[[ -s "${STEP_DIR}/annotation/genes.bed" ]] || die "genes.bed was not created"
[[ -s "${STEP_DIR}/annotation/promoters.bed" ]] || die "promoters.bed was not created"

mark_done "010-reference" "${NAME}"
log "Reference preparation completed"
