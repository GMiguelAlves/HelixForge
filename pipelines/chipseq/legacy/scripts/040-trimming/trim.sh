#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: trim.sh CONFIG sample_id}"
SAMPLE_ID="${2:?Usage: trim.sh CONFIG sample_id}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="040-trimming"
STEP_DIR="${TRIM_DIR:-${OUTPUT_DIR}/${STEP}}/${SAMPLE_ID}"
POST_TRIM_QC_DIR="${QC_DIR:-${OUTPUT_DIR}/030-qc-fastq}/post_trim/${SAMPLE_ID}"
ensure_dir "${STEP_DIR}" "${POST_TRIM_QC_DIR}"

if is_done "${STEP}" "${SAMPLE_ID}"; then
  log "Trimming already completed for ${SAMPLE_ID}; skipping"
  exit 0
fi

IFS=$'\t' read -r FQ1 FQ2 < <(raw_fastqs_for_sample "${SAMPLE_ID}")
IFS=$'\t' read -r TRIM1 TRIM2 < <(trimmed_fastqs_for_sample "${SAMPLE_ID}")
LAYOUT="$(sample_layout "${SAMPLE_ID}")"

[[ -f "${FQ1}" ]] || die "${SAMPLE_ID}: FASTQ R1 not found: ${FQ1}"
if [[ "${LAYOUT}" == "paired" ]]; then
  [[ -f "${FQ2}" ]] || die "${SAMPLE_ID}: FASTQ R2 not found: ${FQ2}"
fi

case "${TRIM_TOOL}" in
  fastp)
    require_cmd fastp
    if [[ "${LAYOUT}" == "paired" ]]; then
      run_cmd "fastp -w ${THREADS} ${FASTP_OPTS} -i '${FQ1}' -I '${FQ2}' -o '${TRIM1}' -O '${TRIM2}' --html '${STEP_DIR}/${SAMPLE_ID}.fastp.html' --json '${STEP_DIR}/${SAMPLE_ID}.fastp.json'"
    else
      run_cmd "fastp -w ${THREADS} ${FASTP_OPTS} -i '${FQ1}' -o '${TRIM1}' --html '${STEP_DIR}/${SAMPLE_ID}.fastp.html' --json '${STEP_DIR}/${SAMPLE_ID}.fastp.json'"
    fi
    ;;
  trim_galore)
    require_cmd trim_galore
    if [[ "${LAYOUT}" == "paired" ]]; then
      run_cmd "trim_galore --cores ${THREADS} --paired ${TRIM_GALORE_OPTS} -o '${STEP_DIR}' '${FQ1}' '${FQ2}'"
      mv "${STEP_DIR}"/*_val_1.fq.gz "${TRIM1}"
      mv "${STEP_DIR}"/*_val_2.fq.gz "${TRIM2}"
    else
      run_cmd "trim_galore --cores ${THREADS} ${TRIM_GALORE_OPTS} -o '${STEP_DIR}' '${FQ1}'"
      mv "${STEP_DIR}"/*_trimmed.fq.gz "${TRIM1}"
    fi
    ;;
esac

[[ -s "${TRIM1}" ]] || die "${SAMPLE_ID}: trimmed R1 was not created"
if [[ "${LAYOUT}" == "paired" ]]; then
  [[ -s "${TRIM2}" ]] || die "${SAMPLE_ID}: trimmed R2 was not created"
fi

if command -v fastqc >/dev/null 2>&1; then
  if [[ "${LAYOUT}" == "paired" ]]; then
    run_cmd "fastqc -t ${THREADS} -o '${POST_TRIM_QC_DIR}' '${TRIM1}' '${TRIM2}'"
  else
    run_cmd "fastqc -t ${THREADS} -o '${POST_TRIM_QC_DIR}' '${TRIM1}'"
  fi
else
  warn "fastqc not found; skipping post-trim FastQC for ${SAMPLE_ID}"
fi

mark_done "${STEP}" "${SAMPLE_ID}"
log "Trimming completed for ${SAMPLE_ID}"
