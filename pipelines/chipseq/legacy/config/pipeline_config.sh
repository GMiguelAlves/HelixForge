#!/usr/bin/env bash
# Central configuration engine for the generic ChIP-seq pipeline.
#
# Most users should NOT edit the advanced defaults below. Instead:
#
#   cp config/user_settings_template.sh config/user_settings.sh
#   edit config/user_settings.sh
#   bash chipseq_pipeline.sh --all --dry-run

set -o pipefail

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  export PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
else
  export PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
fi

path_is_absolute() {
  local path="$1"
  [[ "$path" == /* || "$path" =~ ^[A-Za-z]:[\\/].* ]]
}

resolve_path_from_dir() {
  local base_dir="$1"
  local path="$2"
  local parent name

  [[ -n "$path" ]] || return 0
  case "$path" in
    "~")
      printf '%s\n' "$HOME"
      return 0
      ;;
    "~/"*)
      printf '%s/%s\n' "$HOME" "${path#~/}"
      return 0
      ;;
  esac
  if path_is_absolute "$path"; then
    printf '%s\n' "$path"
    return 0
  fi

  parent="${path%/*}"
  name="${path##*/}"
  [[ "$parent" != "$path" ]] || parent="."
  if [[ -d "${base_dir}/${parent}" ]]; then
    printf '%s/%s\n' "$(cd "${base_dir}/${parent}" && pwd)" "$name"
  else
    printf '%s/%s\n' "$base_dir" "$path"
  fi
}

normalize_project_path_var() {
  local var_name="$1"
  local value="${!var_name:-}"
  [[ -n "$value" ]] || return 0
  export "${var_name}=$(resolve_path_from_dir "$PROJECT_DIR" "$value")"
}

source_optional_settings() {
  local settings_file="$1"
  local had_nounset=0
  [[ -f "${settings_file}" ]] || return 0
  case "$-" in
    *u*)
      had_nounset=1
      set +u
      ;;
  esac
  # shellcheck source=/dev/null
  source "${settings_file}"
  if [[ "${had_nounset}" -eq 1 ]]; then
    set -u
  fi
}

# Simple user settings. This optional file is the only file most users edit.
export USER_SETTINGS_FILE="${USER_SETTINGS_FILE:-${PROJECT_DIR}/config/user_settings.sh}"
if ! path_is_absolute "$USER_SETTINGS_FILE"; then
  export USER_SETTINGS_FILE="${PROJECT_DIR}/${USER_SETTINGS_FILE}"
fi
export USER_SETTINGS_DIR="$(cd "$(dirname "$USER_SETTINGS_FILE")" 2>/dev/null && pwd || echo "${PROJECT_DIR}/config")"
if [[ -f "$USER_SETTINGS_FILE" ]]; then
  source_optional_settings "$USER_SETTINGS_FILE"
fi

# Backward-compatible local config name from earlier versions.
export LOCAL_CONFIG="${LOCAL_CONFIG:-${PROJECT_DIR}/config/pipeline_config.local.sh}"
if [[ ! -f "$USER_SETTINGS_FILE" && -f "$LOCAL_CONFIG" ]]; then
  source_optional_settings "$LOCAL_CONFIG"
fi

if [[ -n "${CONDA_BASE:-}" ]]; then
  export CONDA_BASE="$(resolve_path_from_dir "$USER_SETTINGS_DIR" "$CONDA_BASE")"
fi

# Advanced defaults: project metadata and directory layout.
export PIPELINE_NAME="${PIPELINE_NAME:-chipseq_pipeline}"
export ORGANISM_NAME="${ORGANISM_NAME:-custom_organism}"
export PIPELINE_COMPRESS_RESULTS="${PIPELINE_COMPRESS_RESULTS:-1}"
case "${PIPELINE_COMPRESS_RESULTS,,}" in
  1|true|yes|y)
    export PIPELINE_TABLE_SUFFIX="${PIPELINE_TABLE_SUFFIX:-.gz}"
    ;;
  *)
    export PIPELINE_TABLE_SUFFIX="${PIPELINE_TABLE_SUFFIX:-}"
    ;;
esac

export FASTQ_DIR="${FASTQ_DIR:-${PROJECT_DIR}/data/fastq}"
export REFERENCE_DIR="${REFERENCE_DIR:-${PROJECT_DIR}/reference}"
export OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_DIR}}"
export WORK_ROOT="${WORK_ROOT:-${OUTPUT_DIR}}"
export METADATA_FILE="${METADATA_FILE:-${PROJECT_DIR}/config/metadata.tsv}"
export ENVS_DIR="${ENVS_DIR:-${PROJECT_DIR}/envs}"
export SCRIPTS_DIR="${SCRIPTS_DIR:-${PROJECT_DIR}/scripts}"

for path_var in FASTQ_DIR REFERENCE_DIR OUTPUT_DIR WORK_ROOT METADATA_FILE ENVS_DIR SCRIPTS_DIR; do
  normalize_project_path_var "$path_var"
done
unset path_var

export LOG_DIR="${LOG_DIR:-${OUTPUT_DIR}/000-logs}"
export METADATA_DIR="${METADATA_DIR:-${OUTPUT_DIR}/020-metadata}"
export REPORT_DIR="${REPORT_DIR:-${OUTPUT_DIR}/130-reports}"

# Heavy work/result directories. Set WORK_ROOT to scratch to keep large files
# away from the cloned repository while preserving logs/reports in OUTPUT_DIR.
export REF_DIR="${REF_DIR:-${WORK_ROOT}/010-reference}"
export QC_DIR="${QC_DIR:-${WORK_ROOT}/030-qc-fastq}"
export TRIM_DIR="${TRIM_DIR:-${WORK_ROOT}/040-trimming}"
export ALIGN_DIR="${ALIGN_DIR:-${WORK_ROOT}/050-alignment}"
export FILTER_DIR="${FILTER_DIR:-${WORK_ROOT}/060-filtering}"
export BAM_QC_DIR="${BAM_QC_DIR:-${WORK_ROOT}/070-qc-alignment}"
export PEAK_DIR="${PEAK_DIR:-${WORK_ROOT}/080-peak-calling}"
export ANNOTATION_DIR="${ANNOTATION_DIR:-${WORK_ROOT}/090-peak-annotation}"
export TRACK_DIR="${TRACK_DIR:-${WORK_ROOT}/100-tracks}"
export CONSENSUS_DIR="${CONSENSUS_DIR:-${WORK_ROOT}/110-consensus-peaks}"
export DIFF_DIR="${DIFF_DIR:-${WORK_ROOT}/120-differential-binding}"
export REF_DATA_DIR="${REF_DATA_DIR:-${REF_DIR}/data}"

for path_var in LOG_DIR REF_DIR METADATA_DIR QC_DIR TRIM_DIR ALIGN_DIR FILTER_DIR BAM_QC_DIR PEAK_DIR ANNOTATION_DIR TRACK_DIR CONSENSUS_DIR DIFF_DIR REPORT_DIR REF_DATA_DIR; do
  normalize_project_path_var "$path_var"
done
unset path_var

# Active executables live in scripts/. The numbered directories mirror the
# user-facing work/result areas, following the RNA-seq pipeline layout.
export REF_SCRIPTS_DIR="${REF_SCRIPTS_DIR:-${SCRIPTS_DIR}/010-reference}"
export QC_SCRIPTS_DIR="${QC_SCRIPTS_DIR:-${SCRIPTS_DIR}/030-qc-fastq}"
export TRIM_SCRIPTS_DIR="${TRIM_SCRIPTS_DIR:-${SCRIPTS_DIR}/040-trimming}"
export ALIGN_SCRIPTS_DIR="${ALIGN_SCRIPTS_DIR:-${SCRIPTS_DIR}/050-alignment}"
export FILTER_SCRIPTS_DIR="${FILTER_SCRIPTS_DIR:-${SCRIPTS_DIR}/060-filtering}"
export BAM_QC_SCRIPTS_DIR="${BAM_QC_SCRIPTS_DIR:-${SCRIPTS_DIR}/070-qc-alignment}"
export PEAK_SCRIPTS_DIR="${PEAK_SCRIPTS_DIR:-${SCRIPTS_DIR}/080-peak-calling}"
export ANNOTATION_SCRIPTS_DIR="${ANNOTATION_SCRIPTS_DIR:-${SCRIPTS_DIR}/090-peak-annotation}"
export TRACK_SCRIPTS_DIR="${TRACK_SCRIPTS_DIR:-${SCRIPTS_DIR}/100-tracks}"
export CONSENSUS_SCRIPTS_DIR="${CONSENSUS_SCRIPTS_DIR:-${SCRIPTS_DIR}/110-consensus-peaks}"
export DIFF_SCRIPTS_DIR="${DIFF_SCRIPTS_DIR:-${SCRIPTS_DIR}/120-differential-binding}"
export REPORT_SCRIPTS_DIR="${REPORT_SCRIPTS_DIR:-${SCRIPTS_DIR}/130-reports}"

# Organism-dependent reference files. These must be supplied by the user.
export GENOME_FASTA="${GENOME_FASTA:-${REFERENCE_DIR}/genome.fa}"
export ANNOTATION_FILE="${ANNOTATION_FILE:-${REFERENCE_DIR}/annotation.gtf}"
export BLACKLIST_BED="${BLACKLIST_BED:-}"
export EFFECTIVE_GENOME_SIZES="${EFFECTIVE_GENOME_SIZES:-}"
export FUNCTIONAL_ANNOTATION="${FUNCTIONAL_ANNOTATION:-}"

for path_var in GENOME_FASTA ANNOTATION_FILE BLACKLIST_BED EFFECTIVE_GENOME_SIZES FUNCTIONAL_ANNOTATION; do
  normalize_project_path_var "$path_var"
done
unset path_var

# Runtime
export PIPELINE_EXECUTOR="${PIPELINE_EXECUTOR:-${RUN_MODE:-slurm}}" # slurm or local
export RUN_MODE="${RUN_MODE:-${PIPELINE_EXECUTOR}}"
export THREADS="${SLURM_CPUS_PER_TASK:-${THREADS:-8}}"
export MEMORY="${SLURM_MEM:-${MEMORY:-${DEFAULT_MEM:-32G}}}"
export DEFAULT_MEM="${DEFAULT_MEM:-${MEMORY}}"
export SLURM_TIME="${SLURM_TIME:-12:00:00}"
export SLURM_PARTITION="${SLURM_PARTITION:-}"
export SLURM_ACCOUNT="${SLURM_ACCOUNT:-}"
export SLURM_QOS="${SLURM_QOS:-}"
export LOCAL_CPUS_PER_TASK="${LOCAL_CPUS_PER_TASK:-$THREADS}"
export PYTHON_BIN="${PYTHON_BIN:-python3}"
export RSCRIPT_BIN="${RSCRIPT_BIN:-Rscript}"

# Software environment. ENV_BACKEND can be none, conda, or apptainer.
export ENV_BACKEND="${ENV_BACKEND:-conda}"
export CONDA_ENV="${CONDA_ENV:-${CHIPSEQ_TOOLS_ENV:-chipseq}}"
export CHIPSEQ_TOOLS_ENV="${CHIPSEQ_TOOLS_ENV:-${CONDA_ENV}}"
export PYTHON_ENV="${PYTHON_ENV:-${CONDA_ENV}}"
export R_ANALYSIS_ENV="${R_ANALYSIS_ENV:-${CONDA_ENV}}"
export CONTAINER_IMAGE="${CONTAINER_IMAGE:-}"

# FASTQ and trimming
export READ_LAYOUT="${READ_LAYOUT:-metadata}"     # metadata, paired, or single
export TRIM_TOOL="${TRIM_TOOL:-fastp}"            # fastp or trim_galore
export FASTP_OPTS="${FASTP_OPTS:---detect_adapter_for_pe --qualified_quality_phred 20 --length_required 20}"
export TRIM_GALORE_OPTS="${TRIM_GALORE_OPTS:---quality 20 --length 20}"

# Alignment
export ALIGNER="${ALIGNER:-bowtie2}"              # bowtie2 or bwa
export BOWTIE2_INDEX_PREFIX="${BOWTIE2_INDEX_PREFIX:-${REF_DIR}/bowtie2/genome}"
export BWA_INDEX_PREFIX="${BWA_INDEX_PREFIX:-${GENOME_FASTA}}"
export BOWTIE2_BUILD_OPTS="${BOWTIE2_BUILD_OPTS:-}"
export BOWTIE2_OPTS="${BOWTIE2_OPTS:---very-sensitive}"
export BWA_OPTS="${BWA_OPTS:-}"

# BAM filtering
export MIN_MAPQ="${MIN_MAPQ:-30}"
export REMOVE_SECONDARY_SUPPLEMENTARY="${REMOVE_SECONDARY_SUPPLEMENTARY:-true}"
export REMOVE_DUPLICATES="${REMOVE_DUPLICATES:-true}"
export DEDUP_TOOL="${DEDUP_TOOL:-samtools}"       # samtools or picard
export PICARD_CMD="${PICARD_CMD:-picard}"

# Peak calling
export PEAK_CALLER="${PEAK_CALLER:-macs3}"        # macs3 or macs2
export PEAK_TYPE="${PEAK_TYPE:-auto}"             # auto, narrow, or broad
export BROAD_MARK_REGEX="${BROAD_MARK_REGEX:-H3K27me3|H3K36me3|H3K9me3|H3K79me2}"
export MACS_QVALUE="${MACS_QVALUE:-0.01}"
export MACS_EXTRA_OPTS="${MACS_EXTRA_OPTS:-}"
export MACS_GENOME_SIZE="${MACS_GENOME_SIZE:-auto}"
export ALLOW_MISSING_CONTROLS="${ALLOW_MISSING_CONTROLS:-false}"

# Annotation
export PROMOTER_UPSTREAM="${PROMOTER_UPSTREAM:-2000}"
export PROMOTER_DOWNSTREAM="${PROMOTER_DOWNSTREAM:-500}"

# Tracks
export BIGWIG_NORMALIZATION="${BIGWIG_NORMALIZATION:-CPM}"  # CPM or RPGC
export EFFECTIVE_GENOME_SIZE="${EFFECTIVE_GENOME_SIZE:-auto}"
export BIN_SIZE="${BIN_SIZE:-10}"

# Differential binding
export GROUP_COLUMNS="${GROUP_COLUMNS:-condition,mark_or_factor}"
export DIFF_CONTRASTS="${DIFF_CONTRASTS:-}"        # Example: treated:control,drug:vehicle
export MIN_REPLICATES_DIFF="${MIN_REPLICATES_DIFF:-2}"
export REQUIRE_DIFF_REPLICATES="${REQUIRE_DIFF_REPLICATES:-false}"
export DIFF_PEAK_SET_SCOPE="${DIFF_PEAK_SET_SCOPE:-mark_all}" # mark_all or all

# Slurm submission mode for sample-level steps.
# array: submit one Slurm array per step, using --array=1-N%CONCURRENCY.
# individual: submit one sbatch job per sample, with dependency throttling.
export SLURM_SAMPLE_SUBMISSION_MODE="${SLURM_SAMPLE_SUBMISSION_MODE:-array}"

# Slurm concurrency for sample-level steps.
export QC_CONCURRENCY="${QC_CONCURRENCY:-8}"
export TRIM_CONCURRENCY="${TRIM_CONCURRENCY:-4}"
export ALIGN_CONCURRENCY="${ALIGN_CONCURRENCY:-2}"
export FILTER_CONCURRENCY="${FILTER_CONCURRENCY:-2}"
export BAM_QC_CONCURRENCY="${BAM_QC_CONCURRENCY:-4}"
export PEAKS_CONCURRENCY="${PEAKS_CONCURRENCY:-4}"
export TRACKS_CONCURRENCY="${TRACKS_CONCURRENCY:-4}"

# Storage policy for generated intermediates.
#
# full: keep every generated file, best for debugging/restarts.
# balanced: after final report succeeds, remove individual FastQC folders and
#           temporary uncompressed reference copies made from .gz inputs.
# minimal: also remove trimmed FASTQs after downstream BAMs/reports exist.
export PIPELINE_STORAGE_MODE="${PIPELINE_STORAGE_MODE:-full}"
export PIPELINE_STORAGE_MODE="${PIPELINE_STORAGE_MODE,,}"
case "$PIPELINE_STORAGE_MODE" in
  full)
    default_cleanup_after_report=0
    default_cleanup_fastqc_dirs=0
    default_cleanup_uncompressed_reference=0
    default_cleanup_trimmed_fastq=0
    ;;
  balanced)
    default_cleanup_after_report=1
    default_cleanup_fastqc_dirs=1
    default_cleanup_uncompressed_reference=1
    default_cleanup_trimmed_fastq=0
    ;;
  minimal)
    default_cleanup_after_report=1
    default_cleanup_fastqc_dirs=1
    default_cleanup_uncompressed_reference=1
    default_cleanup_trimmed_fastq=1
    ;;
  *)
    echo "[ERRO] PIPELINE_STORAGE_MODE invalido: ${PIPELINE_STORAGE_MODE}. Use full, balanced ou minimal." >&2
    exit 1
    ;;
esac
export RUN_STORAGE_CLEANUP_AFTER_REPORT="${RUN_STORAGE_CLEANUP_AFTER_REPORT:-$default_cleanup_after_report}"
export CLEANUP_FASTQC_DIRS="${CLEANUP_FASTQC_DIRS:-$default_cleanup_fastqc_dirs}"
export CLEANUP_UNCOMPRESSED_REFERENCE="${CLEANUP_UNCOMPRESSED_REFERENCE:-$default_cleanup_uncompressed_reference}"
export CLEANUP_TRIMMED_FASTQ="${CLEANUP_TRIMMED_FASTQ:-$default_cleanup_trimmed_fastq}"
unset default_cleanup_after_report default_cleanup_fastqc_dirs
unset default_cleanup_uncompressed_reference default_cleanup_trimmed_fastq

# Output safety
export OVERWRITE="${OVERWRITE:-false}"
export CREATE_DONE_FILES="${CREATE_DONE_FILES:-true}"
