#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:-config/pipeline_config.sh}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${CONFIG_FILE}")/.." && pwd)}"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
# shellcheck source=../lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_chipseq_config "${CONFIG_FILE}"

remove_tree_contents() {
  local path="$1"
  local label="$2"
  [[ -d "${path}" ]] || return 0
  case "${path}" in
    "${PROJECT_DIR}"|"${OUTPUT_DIR}"|"/"|"" )
      die "Refusing to cleanup unsafe path for ${label}: ${path}"
      ;;
  esac
  log "Removing ${label}: ${path}"
  find "${path}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
}

remove_matching_files() {
  local root="$1"
  local label="$2"
  shift 2
  [[ -d "${root}" ]] || return 0
  log "Removing ${label} under ${root}"
  find "${root}" "$@" -type f -print -delete
}

log "Storage mode: ${PIPELINE_STORAGE_MODE}"

if truthy "${CLEANUP_FASTQC_DIRS:-0}"; then
  find "${QC_DIR}" -type d \( -name "*_fastqc" -o -name "fastqc" \) -print -exec rm -rf {} + 2>/dev/null || true
fi

if truthy "${CLEANUP_TRIMMED_FASTQ:-0}"; then
  remove_matching_files "${TRIM_DIR}" "trimmed FASTQs" \( -name "*.fastq.gz" -o -name "*.fq.gz" -o -name "*.fastq" -o -name "*.fq" \)
fi

if truthy "${CLEANUP_UNCOMPRESSED_REFERENCE:-0}"; then
  if [[ -d "${REF_DATA_DIR}" ]]; then
    if [[ "${GENOME_FASTA}" == *.gz ]]; then
      rm -f "${REF_DATA_DIR}/$(basename "${GENOME_FASTA%.gz}")" "${REF_DATA_DIR}/$(basename "${GENOME_FASTA%.gz}").fai"
    fi
    if [[ "${ANNOTATION_FILE}" == *.gz ]]; then
      rm -f "${REF_DATA_DIR}/$(basename "${ANNOTATION_FILE%.gz}")"
    fi
  fi
fi

log "Storage cleanup completed"
