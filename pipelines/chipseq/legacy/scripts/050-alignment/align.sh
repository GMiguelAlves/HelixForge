#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: align.sh CONFIG sample_id}"
SAMPLE_ID="${2:?Usage: align.sh CONFIG sample_id}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="050-alignment"
STEP_DIR="${ALIGN_DIR:-${OUTPUT_DIR}/${STEP}}/${SAMPLE_ID}"
ensure_dir "${STEP_DIR}"

if is_done "${STEP}" "${SAMPLE_ID}"; then
  log "Alignment already completed for ${SAMPLE_ID}; skipping"
  exit 0
fi

require_cmd samtools
LAYOUT="$(sample_layout "${SAMPLE_ID}")"
IFS=$'\t' read -r TRIM1 TRIM2 < <(trimmed_fastqs_for_sample "${SAMPLE_ID}")
IFS=$'\t' read -r RAW1 RAW2 < <(raw_fastqs_for_sample "${SAMPLE_ID}")

FQ1="${TRIM1}"
FQ2="${TRIM2}"
if [[ ! -s "${FQ1}" ]]; then
  warn "${SAMPLE_ID}: trimmed FASTQ not found; using raw FASTQ"
  FQ1="${RAW1}"
  FQ2="${RAW2}"
fi

[[ -s "${FQ1}" ]] || die "${SAMPLE_ID}: FASTQ R1 not found: ${FQ1}"
if [[ "${LAYOUT}" == "paired" ]]; then
  [[ -s "${FQ2}" ]] || die "${SAMPLE_ID}: FASTQ R2 not found: ${FQ2}"
fi

BAM="${STEP_DIR}/${SAMPLE_ID}.sorted.bam"
LOG="${STEP_DIR}/${SAMPLE_ID}.${ALIGNER}.log"

run_alignment_cmd() {
  local cmd="$1"
  if ! run_cmd "${cmd}"; then
    warn "${SAMPLE_ID}: ${ALIGNER} alignment failed. Last lines from ${LOG}:"
    if [[ -s "${LOG}" ]]; then
      tail -n 80 "${LOG}" >&2 || true
    else
      warn "${SAMPLE_ID}: aligner log is empty or missing: ${LOG}"
    fi
    return 1
  fi
}

case "${ALIGNER}" in
  bowtie2)
    require_cmd bowtie2
    if [[ "${LAYOUT}" == "paired" ]]; then
      run_alignment_cmd "bowtie2 -p ${THREADS} ${BOWTIE2_OPTS} -x '${BOWTIE2_INDEX_PREFIX}' -1 '${FQ1}' -2 '${FQ2}' 2> '${LOG}' | samtools sort -@ ${THREADS} -o '${BAM}' -"
    else
      run_alignment_cmd "bowtie2 -p ${THREADS} ${BOWTIE2_OPTS} -x '${BOWTIE2_INDEX_PREFIX}' -U '${FQ1}' 2> '${LOG}' | samtools sort -@ ${THREADS} -o '${BAM}' -"
    fi
    ;;
  bwa)
    require_cmd bwa
    if [[ "${GENOME_FASTA:-}" == *.gz && "${BWA_INDEX_PREFIX}" == "${GENOME_FASTA}" ]]; then
      BWA_INDEX_PREFIX="${REF_DATA_DIR:-${REF_DIR}/data}/$(basename "${GENOME_FASTA%.gz}")"
    fi
    if [[ "${LAYOUT}" == "paired" ]]; then
      run_alignment_cmd "bwa mem -t ${THREADS} ${BWA_OPTS} '${BWA_INDEX_PREFIX}' '${FQ1}' '${FQ2}' 2> '${LOG}' | samtools sort -@ ${THREADS} -o '${BAM}' -"
    else
      run_alignment_cmd "bwa mem -t ${THREADS} ${BWA_OPTS} '${BWA_INDEX_PREFIX}' '${FQ1}' 2> '${LOG}' | samtools sort -@ ${THREADS} -o '${BAM}' -"
    fi
    ;;
esac

samtools index -@ "${THREADS}" "${BAM}"
samtools quickcheck "${BAM}" || die "${SAMPLE_ID}: BAM failed samtools quickcheck"
samtools flagstat -@ "${THREADS}" "${BAM}" > "${STEP_DIR}/${SAMPLE_ID}.aligned.flagstat.txt"
samtools idxstats -@ "${THREADS}" "${BAM}" > "${STEP_DIR}/${SAMPLE_ID}.aligned.idxstats.txt"
samtools stats -@ "${THREADS}" "${BAM}" > "${STEP_DIR}/${SAMPLE_ID}.aligned.stats.txt"

mark_done "${STEP}" "${SAMPLE_ID}"
log "Alignment completed for ${SAMPLE_ID}"
