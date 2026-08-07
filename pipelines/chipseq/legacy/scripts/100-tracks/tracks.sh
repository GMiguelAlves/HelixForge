#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: tracks.sh CONFIG sample_id|aggregate}"
TARGET="${2:?Usage: tracks.sh CONFIG sample_id|aggregate}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="100-tracks"
STEP_DIR="${TRACK_DIR:-${OUTPUT_DIR}/${STEP}}"
ensure_dir "${STEP_DIR}"

if [[ "${TARGET}" == "aggregate" ]]; then
  if is_done "${STEP}" "aggregate"; then
    log "Aggregate tracks already completed; skipping"
    exit 0
  fi
  require_cmd samtools
  if command -v bamCoverage >/dev/null 2>&1; then
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
        if (v!="true" && v!="1" && v!="yes") print $c"__"$m, $s
      }' "${METADATA_FILE}" | sort > "${STEP_DIR}/track_groups.tsv"
    cut -f1 "${STEP_DIR}/track_groups.tsv" | sort -u | while read -r GROUP_ID; do
      [[ -n "${GROUP_ID}" ]] || continue
      mapfile -t GROUP_BAMS < <(awk -F '\t' -v g="${GROUP_ID}" '$1==g {print $2}' "${STEP_DIR}/track_groups.tsv" | while read -r SAMPLE_ID; do filtered_bam_for_sample "${SAMPLE_ID}"; done)
      [[ "${#GROUP_BAMS[@]}" -gt 0 ]] || continue
      MERGED="${STEP_DIR}/${GROUP_ID}.merged.bam"
      run_cmd "samtools merge -@ ${THREADS} -f '${MERGED}' ${GROUP_BAMS[*]}"
      samtools index -@ "${THREADS}" "${MERGED}"
      NORM_ARGS="--normalizeUsing ${BIGWIG_NORMALIZATION}"
      if [[ "${BIGWIG_NORMALIZATION}" == "RPGC" ]]; then
        if [[ "${EFFECTIVE_GENOME_SIZE}" == "auto" ]]; then
          EFFECTIVE_SIZE="$(awk '{s+=$2} END {print s}' "${REF_DIR:-${OUTPUT_DIR}/010-reference}/chrom.sizes")"
        else
          EFFECTIVE_SIZE="${EFFECTIVE_GENOME_SIZE}"
        fi
        NORM_ARGS="${NORM_ARGS} --effectiveGenomeSize ${EFFECTIVE_SIZE}"
      fi
      run_cmd "bamCoverage -b '${MERGED}' -o '${STEP_DIR}/${GROUP_ID}.bw' -p ${THREADS} --binSize ${BIN_SIZE} ${NORM_ARGS}"
    done
  else
    warn "bamCoverage not found; aggregate tracks skipped"
  fi
  mark_done "${STEP}" "aggregate"
  exit 0
fi

if is_done "${STEP}" "${TARGET}"; then
  log "Track already completed for ${TARGET}; skipping"
  exit 0
fi

if command -v bamCoverage >/dev/null 2>&1; then
  BAM="$(filtered_bam_for_sample "${TARGET}")"
  [[ -s "${BAM}" ]] || die "${TARGET}: filtered BAM not found: ${BAM}"
  NORM_ARGS="--normalizeUsing ${BIGWIG_NORMALIZATION}"
  if [[ "${BIGWIG_NORMALIZATION}" == "RPGC" ]]; then
    if [[ "${EFFECTIVE_GENOME_SIZE}" == "auto" ]]; then
      EFFECTIVE_SIZE="$(awk '{s+=$2} END {print s}' "${REF_DIR:-${OUTPUT_DIR}/010-reference}/chrom.sizes")"
    else
      EFFECTIVE_SIZE="${EFFECTIVE_GENOME_SIZE}"
    fi
    NORM_ARGS="${NORM_ARGS} --effectiveGenomeSize ${EFFECTIVE_SIZE}"
  fi
  run_cmd "bamCoverage -b '${BAM}' -o '${STEP_DIR}/${TARGET}.bw' -p ${THREADS} --binSize ${BIN_SIZE} ${NORM_ARGS}"
else
  warn "bamCoverage not found; sample track skipped for ${TARGET}"
fi

mark_done "${STEP}" "${TARGET}"
log "Track completed for ${TARGET}"
