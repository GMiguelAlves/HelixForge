#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: bam_qc.sh CONFIG sample_id|multiqc|fingerprint}"
TARGET="${2:?Usage: bam_qc.sh CONFIG sample_id|multiqc|fingerprint}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="070-qc-alignment"
STEP_DIR="${BAM_QC_DIR:-${OUTPUT_DIR}/${STEP}}"
ensure_dir "${STEP_DIR}"

if [[ "${TARGET}" == "multiqc" ]]; then
  if is_done "${STEP}" "multiqc"; then
    log "BAM MultiQC already completed; skipping"
    exit 0
  fi
  require_cmd multiqc
  run_cmd "multiqc '${ALIGN_DIR:-${OUTPUT_DIR}/050-alignment}' '${FILTER_DIR:-${OUTPUT_DIR}/060-filtering}' '${STEP_DIR}' -o '${STEP_DIR}/multiqc' -n alignment_multiqc.html"
  mark_done "${STEP}" "multiqc"
  exit 0
fi

if [[ "${TARGET}" == "fingerprint" ]]; then
  if is_done "${STEP}" "fingerprint"; then
    log "Fingerprint QC already completed; skipping"
    exit 0
  fi
  if command -v plotFingerprint >/dev/null 2>&1; then
    mapfile -t BAMS < <(find "${FILTER_DIR:-${OUTPUT_DIR}/060-filtering}" -name "*.filtered.bam" -type f | sort)
    if [[ "${#BAMS[@]}" -ge 2 ]]; then
      run_cmd "plotFingerprint -b ${BAMS[*]} --labels $(basename -a "${BAMS[@]}" | tr '\n' ' ') -p ${THREADS} --plotFile '${STEP_DIR}/fingerprint.pdf' --outRawCounts '${STEP_DIR}/fingerprint_counts.tsv'"
      gzip_file_if_requested "${STEP_DIR}/fingerprint_counts.tsv"
    else
      warn "Need at least two BAMs for plotFingerprint; skipping"
    fi
  else
    warn "plotFingerprint not found; skipping fingerprint QC"
  fi
  mark_done "${STEP}" "fingerprint"
  exit 0
fi

if is_done "${STEP}" "${TARGET}"; then
  log "BAM QC already completed for ${TARGET}; skipping"
  exit 0
fi

BAM="$(filtered_bam_for_sample "${TARGET}")"
[[ -s "${BAM}" ]] || die "${TARGET}: filtered BAM not found: ${BAM}"
OUTDIR="${STEP_DIR}/${TARGET}"
ensure_dir "${OUTDIR}"

require_cmd samtools
samtools flagstat -@ "${THREADS}" "${BAM}" > "${OUTDIR}/${TARGET}.flagstat.txt"
samtools idxstats -@ "${THREADS}" "${BAM}" > "${OUTDIR}/${TARGET}.idxstats.txt"
samtools stats -@ "${THREADS}" "${BAM}" > "${OUTDIR}/${TARGET}.stats.txt"

if [[ "$(sample_layout "${TARGET}")" == "paired" ]] && command -v bamPEFragmentSize >/dev/null 2>&1; then
  run_cmd "bamPEFragmentSize --bamfiles '${BAM}' --histogram '${OUTDIR}/${TARGET}.fragment_size.pdf' --outRawFragmentLengths '${OUTDIR}/${TARGET}.fragment_size.tsv' --numberOfProcessors ${THREADS}"
  gzip_file_if_requested "${OUTDIR}/${TARGET}.fragment_size.tsv"
fi

mark_done "${STEP}" "${TARGET}"
log "BAM QC completed for ${TARGET}"
