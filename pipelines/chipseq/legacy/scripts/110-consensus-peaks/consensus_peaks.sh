#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: consensus_peaks.sh CONFIG}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="110-consensus-peaks"
STEP_DIR="${CONSENSUS_DIR:-${OUTPUT_DIR}/${STEP}}"
ensure_dir "${STEP_DIR}/groups" "${STEP_DIR}/counts"

if is_done "${STEP}" "consensus"; then
  log "Consensus peak step already completed; skipping"
  exit 0
fi

require_cmd bedtools

GROUP_TABLE="${STEP_DIR}/groups.tsv"
awk -F '\t' 'BEGIN{OFS="\t"}
  NR==1 {
    for (i=1; i<=NF; i++) {
      if ($i=="sample_id") s=i
      if ($i=="condition") c=i
      if ($i=="mark_or_factor") m=i
      if ($i=="is_control") ctrl=i
    }
    next
  }
  NR>1 {
    v=tolower($ctrl)
    if (v!="true" && v!="1" && v!="yes") print $c"__"$m, $s, $c, $m
  }' "${METADATA_FILE}" > "${GROUP_TABLE}"

cut -f1 "${GROUP_TABLE}" | sort -u | while read -r GROUP_ID; do
  [[ -n "${GROUP_ID}" ]] || continue
  GROUP_BED="${STEP_DIR}/groups/${GROUP_ID}.consensus.bed"
  TMP_BED="${STEP_DIR}/groups/${GROUP_ID}.all_peaks.tmp.bed"
  : > "${TMP_BED}"
  awk -F '\t' -v group="${GROUP_ID}" '$1==group {print $2}' "${GROUP_TABLE}" | while read -r SAMPLE_ID; do
    PEAK_FILE="$(find "${PEAK_DIR:-${OUTPUT_DIR}/080-peak-calling}/${SAMPLE_ID}" -maxdepth 1 \( -name "*_peaks.narrowPeak" -o -name "*_peaks.broadPeak" \) -type f | head -n 1)"
    [[ -n "${PEAK_FILE}" && -s "${PEAK_FILE}" ]] || die "${SAMPLE_ID}: peak file not found for consensus"
    awk 'BEGIN{OFS="\t"} {print $1,$2,$3}' "${PEAK_FILE}" >> "${TMP_BED}"
  done
  sort -k1,1 -k2,2n "${TMP_BED}" | bedtools merge -i - > "${GROUP_BED}"
  rm -f "${TMP_BED}"
done

MARK_TABLE="${STEP_DIR}/groups_by_mark.tsv"
awk -F '\t' 'BEGIN{OFS="\t"}
  NR==1 {
    for (i=1; i<=NF; i++) {
      if ($i=="sample_id") s=i
      if ($i=="mark_or_factor") m=i
      if ($i=="is_control") ctrl=i
    }
    next
  }
  NR>1 {
    v=tolower($ctrl)
    if (v!="true" && v!="1" && v!="yes") print $m"__all", $s
  }' "${METADATA_FILE}" > "${MARK_TABLE}"

cut -f1 "${MARK_TABLE}" | sort -u | while read -r GROUP_ID; do
  [[ -n "${GROUP_ID}" ]] || continue
  GROUP_BED="${STEP_DIR}/groups/${GROUP_ID}.consensus.bed"
  TMP_BED="${STEP_DIR}/groups/${GROUP_ID}.all_peaks.tmp.bed"
  : > "${TMP_BED}"
  awk -F '\t' -v group="${GROUP_ID}" '$1==group {print $2}' "${MARK_TABLE}" | while read -r SAMPLE_ID; do
    PEAK_FILE="$(find "${PEAK_DIR:-${OUTPUT_DIR}/080-peak-calling}/${SAMPLE_ID}" -maxdepth 1 \( -name "*_peaks.narrowPeak" -o -name "*_peaks.broadPeak" \) -type f | head -n 1)"
    [[ -n "${PEAK_FILE}" && -s "${PEAK_FILE}" ]] || die "${SAMPLE_ID}: peak file not found for mark-level consensus"
    awk 'BEGIN{OFS="\t"} {print $1,$2,$3}' "${PEAK_FILE}" >> "${TMP_BED}"
  done
  sort -k1,1 -k2,2n "${TMP_BED}" | bedtools merge -i - > "${GROUP_BED}"
  rm -f "${TMP_BED}"
done

mapfile -t BAMS < <(metadata_ip_samples | while read -r SAMPLE_ID; do filtered_bam_for_sample "${SAMPLE_ID}"; done)
if [[ "${#BAMS[@]}" -gt 0 ]]; then
  find "${STEP_DIR}/groups" -name "*.consensus.bed" -type f | sort | while read -r BED; do
    NAME="$(basename "${BED}" .consensus.bed)"
    COUNT_OUT="${STEP_DIR}/counts/${NAME}.counts.tsv${PIPELINE_TABLE_SUFFIX:-}"
    if [[ "${COUNT_OUT}" == *.gz ]]; then
      require_cmd gzip
      bedtools multicov -bams "${BAMS[@]}" -bed "${BED}" | gzip -c > "${COUNT_OUT}"
    else
      bedtools multicov -bams "${BAMS[@]}" -bed "${BED}" > "${COUNT_OUT}"
    fi
  done
fi

mark_done "${STEP}" "consensus"
log "Consensus peaks completed"
