#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:?Usage: filter.sh CONFIG sample_id}"
SAMPLE_ID="${2:?Usage: filter.sh CONFIG sample_id}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_config "${CONFIG_FILE}"
activate_runtime

STEP="060-filtering"
STEP_DIR="${FILTER_DIR:-${OUTPUT_DIR}/${STEP}}/${SAMPLE_ID}"
ensure_dir "${STEP_DIR}"

if is_done "${STEP}" "${SAMPLE_ID}"; then
  log "Filtering already completed for ${SAMPLE_ID}; skipping"
  exit 0
fi

require_cmd samtools
IN_BAM="${ALIGN_DIR:-${OUTPUT_DIR}/050-alignment}/${SAMPLE_ID}/${SAMPLE_ID}.sorted.bam"
[[ -s "${IN_BAM}" ]] || die "${SAMPLE_ID}: aligned BAM not found: ${IN_BAM}"

FLAG_FILTER="4"
if bool_true "${REMOVE_SECONDARY_SUPPLEMENTARY}"; then
  FLAG_FILTER="2308"
fi

MAPQ_BAM="${STEP_DIR}/${SAMPLE_ID}.mapq.bam"
DEDUP_BAM="${STEP_DIR}/${SAMPLE_ID}.dedup.bam"
FINAL_BAM="${STEP_DIR}/${SAMPLE_ID}.filtered.bam"

run_cmd "samtools view -@ ${THREADS} -b -q ${MIN_MAPQ} -F ${FLAG_FILTER} '${IN_BAM}' > '${MAPQ_BAM}'"
samtools flagstat -@ "${THREADS}" "${MAPQ_BAM}" > "${STEP_DIR}/${SAMPLE_ID}.mapq.flagstat.txt"

if bool_true "${REMOVE_DUPLICATES}"; then
  case "${DEDUP_TOOL}" in
    samtools)
      LAYOUT="$(sample_layout "${SAMPLE_ID}")"
      if [[ "${LAYOUT}" == "paired" ]]; then
        run_cmd "samtools sort -@ ${THREADS} -n -o '${STEP_DIR}/${SAMPLE_ID}.namesort.bam' '${MAPQ_BAM}'"
        run_cmd "samtools fixmate -@ ${THREADS} -m '${STEP_DIR}/${SAMPLE_ID}.namesort.bam' '${STEP_DIR}/${SAMPLE_ID}.fixmate.bam'"
        run_cmd "samtools sort -@ ${THREADS} -o '${STEP_DIR}/${SAMPLE_ID}.positionsort.bam' '${STEP_DIR}/${SAMPLE_ID}.fixmate.bam'"
        run_cmd "samtools markdup -@ ${THREADS} -r '${STEP_DIR}/${SAMPLE_ID}.positionsort.bam' '${DEDUP_BAM}'"
      else
        run_cmd "samtools markdup -@ ${THREADS} -s -r '${MAPQ_BAM}' '${DEDUP_BAM}'"
      fi
      ;;
    picard)
      require_cmd "${PICARD_CMD}"
      run_cmd "${PICARD_CMD} MarkDuplicates I='${MAPQ_BAM}' O='${DEDUP_BAM}' M='${STEP_DIR}/${SAMPLE_ID}.markdup_metrics.txt' REMOVE_DUPLICATES=true VALIDATION_STRINGENCY=SILENT"
      ;;
    *) die "Unsupported DEDUP_TOOL: ${DEDUP_TOOL}" ;;
  esac
else
  cp "${MAPQ_BAM}" "${DEDUP_BAM}"
fi
samtools flagstat -@ "${THREADS}" "${DEDUP_BAM}" > "${STEP_DIR}/${SAMPLE_ID}.dedup.flagstat.txt"

if [[ -n "${BLACKLIST_BED}" ]]; then
  require_cmd bedtools
  [[ -f "${BLACKLIST_BED}" ]] || die "BLACKLIST_BED not found: ${BLACKLIST_BED}"
  run_cmd "bedtools intersect -v -abam '${DEDUP_BAM}' -b '${BLACKLIST_BED}' > '${FINAL_BAM}'"
else
  cp "${DEDUP_BAM}" "${FINAL_BAM}"
fi

samtools index -@ "${THREADS}" "${FINAL_BAM}"
samtools quickcheck "${FINAL_BAM}" || die "${SAMPLE_ID}: filtered BAM failed samtools quickcheck"
samtools flagstat -@ "${THREADS}" "${FINAL_BAM}" > "${STEP_DIR}/${SAMPLE_ID}.flagstat.txt"
samtools idxstats -@ "${THREADS}" "${FINAL_BAM}" > "${STEP_DIR}/${SAMPLE_ID}.idxstats.txt"
samtools stats -@ "${THREADS}" "${FINAL_BAM}" > "${STEP_DIR}/${SAMPLE_ID}.stats.txt"

mark_done "${STEP}" "${SAMPLE_ID}"
log "Filtering completed for ${SAMPLE_ID}"
