#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: call_peaks.sh CONFIG sample_id}"
SAMPLE_ID="${2:?Usage: call_peaks.sh CONFIG sample_id}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="080-peak-calling"
STEP_DIR="${PEAK_DIR:-${OUTPUT_DIR}/${STEP}}/${SAMPLE_ID}"
ensure_dir "${STEP_DIR}"

if is_done "${STEP}" "${SAMPLE_ID}"; then
  log "Peak calling already completed for ${SAMPLE_ID}; skipping"
  exit 0
fi

IS_CONTROL="$(metadata_value "${SAMPLE_ID}" "is_control")"
if bool_true "${IS_CONTROL}"; then
  log "${SAMPLE_ID} is a control sample; no peaks will be called"
  mark_done "${STEP}" "${SAMPLE_ID}"
  exit 0
fi

require_cmd "${PEAK_CALLER}"

TREAT_BAM="$(filtered_bam_for_sample "${SAMPLE_ID}")"
[[ -s "${TREAT_BAM}" ]] || die "${SAMPLE_ID}: treatment BAM not found: ${TREAT_BAM}"

CONTROL_ID="$(metadata_value "${SAMPLE_ID}" "control_id")"
CONTROL_BAM=""
if [[ -n "${CONTROL_ID}" ]]; then
  CONTROL_BAM="$(filtered_bam_for_sample "${CONTROL_ID}")"
  [[ -s "${CONTROL_BAM}" ]] || die "${SAMPLE_ID}: control BAM not found for ${CONTROL_ID}: ${CONTROL_BAM}"
fi

CHROM_SIZES="${REF_DIR:-${OUTPUT_DIR}/010-reference}/chrom.sizes"
[[ -s "${CHROM_SIZES}" ]] || die "chrom.sizes not found; run reference step first"

if [[ "${MACS_GENOME_SIZE}" == "auto" ]]; then
  GENOME_SIZE="$(awk '{s+=$2} END {print s}' "${CHROM_SIZES}")"
else
  GENOME_SIZE="${MACS_GENOME_SIZE}"
fi

LAYOUT="$(sample_layout "${SAMPLE_ID}")"
FORMAT="BAM"
if [[ "${LAYOUT}" == "paired" ]]; then
  FORMAT="BAMPE"
fi

MARK="$(metadata_value "${SAMPLE_ID}" "mark_or_factor")"
CALL_TYPE="${PEAK_TYPE}"
if [[ "${CALL_TYPE}" == "auto" ]]; then
  if [[ "${MARK}" =~ ${BROAD_MARK_REGEX} ]]; then
    CALL_TYPE="broad"
  else
    CALL_TYPE="narrow"
  fi
fi

CONTROL_ARGS=""
if [[ -n "${CONTROL_BAM}" ]]; then
  CONTROL_ARGS="-c '${CONTROL_BAM}'"
else
  log "${SAMPLE_ID}: no control_id/control BAM provided; running ${PEAK_CALLER} without matched input/control"
fi

BROAD_ARGS=""
PEAK_FILE="${STEP_DIR}/${SAMPLE_ID}_peaks.narrowPeak"
if [[ "${CALL_TYPE}" == "broad" ]]; then
  BROAD_ARGS="--broad"
  PEAK_FILE="${STEP_DIR}/${SAMPLE_ID}_peaks.broadPeak"
fi

run_cmd "${PEAK_CALLER} callpeak -t '${TREAT_BAM}' ${CONTROL_ARGS} -f ${FORMAT} -g ${GENOME_SIZE} -n '${SAMPLE_ID}' --outdir '${STEP_DIR}' -q ${MACS_QVALUE} ${BROAD_ARGS} ${MACS_EXTRA_OPTS}"

[[ -s "${PEAK_FILE}" ]] || die "${SAMPLE_ID}: expected peak file was not created: ${PEAK_FILE}"
awk -v sample="${SAMPLE_ID}" 'BEGIN{OFS="\t"} END{print sample, NR}' "${PEAK_FILE}" > "${STEP_DIR}/${SAMPLE_ID}.peak_counts.tsv"

mark_done "${STEP}" "${SAMPLE_ID}"
log "Peak calling completed for ${SAMPLE_ID}"
