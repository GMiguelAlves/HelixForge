#!/usr/bin/env bash

set -euo pipefail

COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${COMMON_DIR}/../.." && pwd)"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

warn() {
  echo "WARNING: $*" >&2
}

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

ensure_dir() {
  mkdir -p "$@"
}

bool_true() {
  case "${1,,}" in
    true|yes|y|1) return 0 ;;
    *) return 1 ;;
  esac
}

load_rnaseq_config() {
  local config_file="${1:-${REPO_ROOT}/config/pipeline_config.sh}"
  if [[ "${config_file}" != /* && ! "${config_file}" =~ ^[A-Za-z]:[\\/].* ]]; then
    config_file="${REPO_ROOT}/${config_file}"
  fi
  [[ -f "${config_file}" ]] || die "Config file not found: ${config_file}"
  # shellcheck source=/dev/null
  source "${config_file}"
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || die "Required command not found in PATH: ${cmd}"
}

create_rnaseq_output_tree() {
  ensure_dir \
    "${PROJECT_DIR}/000-logs" \
    "${PROJECT_DIR}/000-logs/reference" \
    "${PROJECT_DIR}/000-logs/download" \
    "${PROJECT_DIR}/000-logs/metadata" \
    "${PROJECT_DIR}/000-logs/qc" \
    "${PROJECT_DIR}/000-logs/salmon" \
    "${PROJECT_DIR}/000-logs/star" \
    "${PROJECT_DIR}/000-logs/tximport" \
    "${PROJECT_DIR}/000-logs/batch" \
    "${PROJECT_DIR}/000-logs/deg" \
    "${PROJECT_DIR}/000-logs/report" \
    "${PROJECT_DIR}/logs" \
    "${PROJECT_DIR}/logs/err" \
    "${PROJECT_DIR}/logs/parse" \
    "${PROJECT_DIR}/logs/quantification" \
    "${PROJECT_DIR}/logs/batch" \
    "${PROJECT_DIR}/logs/deg" \
    "${REF_DIR}" \
    "${REF_DIR}/logs" \
    "${DOWNLOAD_DIR}" \
    "${DOWNLOAD_DIR}/logs" \
    "${PARSE_DIR}" \
    "${PARSE_DIR}/logs" \
    "${PARSE_DIR}/logs/err" \
    "${PARSE_DIR}/logs/parse" \
    "${QC_DIR}" \
    "${QC_DIR}/logs" \
    "${QC_DIR}/logs/qc_raw" \
    "${QC_DIR}/logs/trim_runs" \
    "${QC_DIR}/logs/qc_trimmed_runs" \
    "${QC_DIR}/logs/merge_samples" \
    "${QC_DIR}/logs/qc_merged" \
    "${QC_DIR}/logs/multiqc" \
    "${ALIGN_DIR}" \
    "${ALIGN_DIR}/logs" \
    "${ALIGN_DIR}/logs/salmon" \
    "${ALIGN_DIR}/logs/star" \
    "${STAR_QUANT_DIR:-${ALIGN_DIR}/star_quant}" \
    "${QUANTIFICATION_DIR}" \
    "${QUANTIFICATION_DIR}/logs" \
    "${QUANTIFICATION_DIR}/logs/quantification" \
    "${BATCH_DIR}" \
    "${BATCH_DIR}/logs" \
    "${BATCH_DIR}/logs/batch" \
    "${DEG_DIR}" \
    "${DEG_DIR}/logs" \
    "${DEG_DIR}/logs/deg" \
    "${GENE_REPORT_DIR}" \
    "${GENE_REPORT_DIR}/logs" \
    "${SCRIPTS_DIR}" \
    "${REF_SCRIPTS_DIR}" \
    "${DOWNLOAD_SCRIPTS_DIR}" \
    "${PARSE_SCRIPTS_DIR}" \
    "${QC_SCRIPTS_DIR}" \
    "${ALIGN_SCRIPTS_DIR}" \
    "${QUANT_SCRIPTS_DIR}" \
    "${BATCH_SCRIPTS_DIR}" \
    "${DEG_SCRIPTS_DIR}" \
    "${GENE_REPORT_SCRIPTS_DIR}"
}
