#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:-config/pipeline_config.sh}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_chipseq_config "${CONFIG_FILE}"

create_chipseq_output_tree

[[ -d "${PROJECT_DIR}" ]] || die "PROJECT_DIR does not exist: ${PROJECT_DIR}"

if [[ ! -f "${USER_SETTINGS_FILE:-}" ]]; then
  warn "User settings file not found: ${USER_SETTINGS_FILE:-config/user_settings.sh}"
  warn "For simple setup, run: cp config/user_settings_template.sh config/user_settings.sh"
fi

if [[ -f "${USER_SETTINGS_FILE:-}" ]]; then
  if [[ "${ORGANISM_NAME}" == "My organism" || "${ORGANISM_NAME}" == "custom_organism" ]]; then
    die "ORGANISM_NAME still contains a template value. Edit config/user_settings.sh."
  fi
  for value in "${FASTQ_DIR:-}" "${REFERENCE_DIR:-}" "${GENOME_FASTA:-}" "${ANNOTATION_FILE:-}" "${CONDA_BASE:-}"; do
    case "${value}" in
      /path/to/*|*/path/to/*)
        die "Configuration still contains a template path: ${value}"
        ;;
    esac
  done
fi

[[ -d "${FASTQ_DIR}" ]] || die "FASTQ_DIR does not exist: ${FASTQ_DIR}"
[[ -f "${GENOME_FASTA}" ]] || die "GENOME_FASTA does not exist: ${GENOME_FASTA}"
[[ -f "${ANNOTATION_FILE}" ]] || die "ANNOTATION_FILE does not exist: ${ANNOTATION_FILE}"
[[ -f "${METADATA_FILE}" ]] || die "METADATA_FILE does not exist: ${METADATA_FILE}"

if [[ -n "${BLACKLIST_BED}" && ! -f "${BLACKLIST_BED}" ]]; then
  die "BLACKLIST_BED was set but does not exist: ${BLACKLIST_BED}"
fi

if [[ -n "${EFFECTIVE_GENOME_SIZES}" && ! -f "${EFFECTIVE_GENOME_SIZES}" ]]; then
  die "EFFECTIVE_GENOME_SIZES was set but does not exist: ${EFFECTIVE_GENOME_SIZES}"
fi

case "${PIPELINE_EXECUTOR:-${RUN_MODE:-slurm}}" in
  slurm|local) ;;
  *) die "PIPELINE_EXECUTOR must be slurm or local, got: ${PIPELINE_EXECUTOR:-${RUN_MODE:-}}" ;;
esac

case "${ALIGNER}" in
  bowtie2|bwa) ;;
  *) die "ALIGNER must be bowtie2 or bwa, got: ${ALIGNER}" ;;
esac

case "${TRIM_TOOL}" in
  fastp|trim_galore) ;;
  *) die "TRIM_TOOL must be fastp or trim_galore, got: ${TRIM_TOOL}" ;;
esac

case "${PEAK_CALLER}" in
  macs2|macs3) ;;
  *) die "PEAK_CALLER must be macs2 or macs3, got: ${PEAK_CALLER}" ;;
esac

case "${SLURM_SAMPLE_SUBMISSION_MODE:-array}" in
  array|individual) ;;
  *) die "SLURM_SAMPLE_SUBMISSION_MODE must be array or individual, got: ${SLURM_SAMPLE_SUBMISSION_MODE}" ;;
esac

case "${PEAK_TYPE}" in
  auto|narrow|broad) ;;
  *) die "PEAK_TYPE must be auto, narrow, or broad, got: ${PEAK_TYPE}" ;;
esac

case "${ENV_BACKEND}" in
  none|conda|apptainer|singularity) ;;
  *) die "ENV_BACKEND must be none, conda, apptainer, or singularity. Current value: ${ENV_BACKEND}" ;;
esac

case "${PIPELINE_STORAGE_MODE:-full}" in
  full|balanced|minimal) ;;
  *) die "PIPELINE_STORAGE_MODE must be 'full', 'balanced', or 'minimal'. Current value: ${PIPELINE_STORAGE_MODE}" ;;
esac

for flag in PIPELINE_COMPRESS_RESULTS RUN_STORAGE_CLEANUP_AFTER_REPORT CLEANUP_FASTQC_DIRS CLEANUP_UNCOMPRESSED_REFERENCE CLEANUP_TRIMMED_FASTQ; do
  case "${!flag:-0}" in
    0|1|true|TRUE|yes|YES|false|FALSE|no|NO|y|Y|n|N) ;;
    *) die "${flag} must be 0/1 or yes/no. Current value: ${!flag}" ;;
  esac
done

for value_name in QC_CONCURRENCY TRIM_CONCURRENCY ALIGN_CONCURRENCY FILTER_CONCURRENCY BAM_QC_CONCURRENCY PEAKS_CONCURRENCY TRACKS_CONCURRENCY; do
  value="${!value_name:-}"
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || die "${value_name} must be a positive integer. Current value: ${value}"
done
unset value_name value

if [[ "${ENV_BACKEND}" == "conda" && -z "${CONDA_BASE:-}" ]]; then
  warn "CONDA_BASE is empty. Jobs will try to use conda from PATH."
fi

if [[ "${PIPELINE_EXECUTOR:-${RUN_MODE:-slurm}}" == "slurm" && "${SKIP_SLURM_CHECK:-false}" != "true" ]]; then
  require_cmd sbatch
fi

log "Configuration validation passed"
