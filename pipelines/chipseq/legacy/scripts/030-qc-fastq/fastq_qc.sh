#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: fastq_qc.sh CONFIG sample_id|raw_multiqc|post_trim_multiqc|multiqc}"
TARGET="${2:?Usage: fastq_qc.sh CONFIG sample_id|raw_multiqc|post_trim_multiqc|multiqc}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="030-qc-fastq"
STEP_DIR="${QC_DIR:-${OUTPUT_DIR}/${STEP}}"
ensure_dir "${STEP_DIR}"

if [[ "${TARGET}" == "multiqc" || "${TARGET}" == "raw_multiqc" || "${TARGET}" == "post_trim_multiqc" ]]; then
  DONE_NAME="${TARGET}"
  SEARCH_DIR="${STEP_DIR}"
  REPORT_NAME="fastq_multiqc.html"
  if [[ "${TARGET}" == "raw_multiqc" ]]; then
    SEARCH_DIR="${STEP_DIR}"
    REPORT_NAME="raw_fastq_multiqc.html"
  elif [[ "${TARGET}" == "post_trim_multiqc" ]]; then
    SEARCH_DIR="${STEP_DIR}/post_trim"
    REPORT_NAME="post_trim_fastq_multiqc.html"
  fi
  if is_done "${STEP}" "${DONE_NAME}"; then
    log "FASTQ MultiQC already completed for ${TARGET}; skipping"
    exit 0
  fi
  require_cmd multiqc
  ensure_dir "${STEP_DIR}/multiqc"
  run_cmd "multiqc '${SEARCH_DIR}' -o '${STEP_DIR}/multiqc' -n '${REPORT_NAME}'"
  mark_done "${STEP}" "${DONE_NAME}"
  exit 0
fi

if is_done "${STEP}" "${TARGET}"; then
  log "Raw FASTQ QC already completed for ${TARGET}; skipping"
  exit 0
fi

require_cmd fastqc
IFS=$'\t' read -r FQ1 FQ2 < <(raw_fastqs_for_sample "${TARGET}")
[[ -f "${FQ1}" ]] || die "${TARGET}: FASTQ R1 not found: ${FQ1}"

OUTDIR="${STEP_DIR}/${TARGET}"
ensure_dir "${OUTDIR}"

LAYOUT="$(sample_layout "${TARGET}")"
if [[ "${LAYOUT}" == "paired" ]]; then
  [[ -f "${FQ2}" ]] || die "${TARGET}: FASTQ R2 not found: ${FQ2}"
  run_cmd "fastqc -t ${THREADS} -o '${OUTDIR}' '${FQ1}' '${FQ2}'"
else
  run_cmd "fastqc -t ${THREADS} -o '${OUTDIR}' '${FQ1}'"
fi

mark_done "${STEP}" "${TARGET}"
log "Raw FASTQ QC completed for ${TARGET}"
