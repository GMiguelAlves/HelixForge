#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "${REPO_ROOT}/scripts/lib/common.sh"

CONFIG_FILE="${REPO_ROOT}/config/pipeline_config.sh"
DRY_RUN="false"
FORCE="false"
RUN_ALL="false"
EXECUTOR_OVERRIDE=""
declare -a REQUESTED_STEPS=()

usage() {
  cat <<'USAGE'
Usage: bash chipseq_pipeline.sh [options]

Options:
  --config FILE          Configuration file (default: config/pipeline_config.sh)
  --all                  Run the complete ChIP-seq workflow
  --step STEP            Run one step. Can be repeated.
                         Steps: reference, qc, trim, align, filter, bam_qc,
                                peaks, consensus, differential, annotate,
                                tracks, report
  --executor MODE        Execution backend: slurm or local
  --local                Shortcut for --executor local
  --slurm                Shortcut for --executor slurm
  --mode MODE            Backward-compatible alias for --executor
  --dry-run              Print commands without executing jobs
  --resume               Skip steps with .done files (default)
  --force                Re-run steps even when .done files exist
  --step cleanup         Run storage cleanup using PIPELINE_STORAGE_MODE rules
  -h, --help             Show this help

Examples:
  bash chipseq_pipeline.sh --all
  bash chipseq_pipeline.sh --all --dry-run
  bash chipseq_pipeline.sh --all --local
  bash chipseq_pipeline.sh --step reference
  bash chipseq_pipeline.sh --step peaks --step annotate
USAGE
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --all)
      RUN_ALL="true"
      shift
      ;;
    --step)
      REQUESTED_STEPS+=("$2")
      shift 2
      ;;
    --executor|--mode)
      EXECUTOR_OVERRIDE="$2"
      shift 2
      ;;
    --local)
      EXECUTOR_OVERRIDE="local"
      shift
      ;;
    --slurm)
      EXECUTOR_OVERRIDE="slurm"
      shift
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --resume)
      FORCE="false"
      shift
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

if [[ "${RUN_ALL}" != "true" && "${#REQUESTED_STEPS[@]}" -eq 0 ]]; then
  RUN_ALL="true"
fi

if [[ "${CONFIG_FILE}" != /* && ! "${CONFIG_FILE}" =~ ^[A-Za-z]:[\\/].* ]]; then
  CONFIG_FILE="${REPO_ROOT}/${CONFIG_FILE}"
fi

load_chipseq_config "${CONFIG_FILE}"
if [[ -n "${EXECUTOR_OVERRIDE}" ]]; then
  export PIPELINE_EXECUTOR="${EXECUTOR_OVERRIDE}"
fi
case "${PIPELINE_EXECUTOR:-slurm}" in
  slurm|local)
    ;;
  *)
    die "Invalid executor '${PIPELINE_EXECUTOR}'. Use slurm or local."
    ;;
esac
export RUN_MODE="${PIPELINE_EXECUTOR}"
if [[ "${FORCE}" == "true" ]]; then
  export OVERWRITE="true"
fi

create_chipseq_output_tree
cp "${CONFIG_FILE}" "${METADATA_DIR}/pipeline_config.used.sh"
if [[ -f "${USER_SETTINGS_FILE:-}" ]]; then
  cp "${USER_SETTINGS_FILE}" "${METADATA_DIR}/user_settings.used.sh"
fi
if [[ -f "${METADATA_FILE}" ]]; then
  cp "${METADATA_FILE}" "${METADATA_DIR}/metadata.used.tsv"
fi

if [[ "${DRY_RUN}" == "true" || "${PIPELINE_EXECUTOR}" == "local" ]]; then
  export SKIP_SLURM_CHECK="true"
fi

bash "${REPO_ROOT}/scripts/validate_config.sh" "${CONFIG_FILE}"
VALIDATE_METADATA_ARGS=(
  "${PYTHON_BIN}" "${REPO_ROOT}/scripts/validate_metadata.py"
  --metadata "${METADATA_FILE}"
  --fastq-dir "${FASTQ_DIR}"
  --min-replicates "${MIN_REPLICATES_DIFF}"
)
if bool_true "${REQUIRE_DIFF_REPLICATES}"; then
  VALIDATE_METADATA_ARGS+=(--require-diff-replicates)
fi
if bool_true "${ALLOW_MISSING_CONTROLS:-false}"; then
  VALIDATE_METADATA_ARGS+=(--allow-missing-controls)
fi
"${VALIDATE_METADATA_ARGS[@]}"

declare -A STEP_ALIASES=(
  [reference]="reference"
  [ref]="reference"
  [qc]="qc"
  [fastq_qc]="qc"
  [trim]="trim"
  [trimming]="trim"
  [align]="align"
  [alignment]="align"
  [filter]="filter"
  [filtering]="filter"
  [bam_qc]="bam_qc"
  [qcbam]="bam_qc"
  [peaks]="peaks"
  [peak]="peaks"
  [consensus]="consensus"
  [differential]="differential"
  [diff]="differential"
  [annotate]="annotate"
  [annotation]="annotate"
  [tracks]="tracks"
  [report]="report"
  [cleanup]="cleanup"
)

declare -A SELECTED=()
if [[ "${RUN_ALL}" == "true" ]]; then
  for step in reference qc trim align filter bam_qc peaks consensus differential annotate tracks report; do
    SELECTED["${step}"]=1
  done
else
  for raw_step in "${REQUESTED_STEPS[@]}"; do
    key="${raw_step,,}"
    [[ -n "${STEP_ALIASES[${key}]:-}" ]] || die "Unknown step: ${raw_step}"
    SELECTED["${STEP_ALIASES[${key}]}"]=1
  done
fi

has_step() {
  [[ -n "${SELECTED[$1]:-}" ]]
}

safe_name() {
  printf '%s\n' "$1" | tr '/: ' '___'
}

step_dir() {
  case "$1" in
    reference) printf '%s\n' "${REF_DIR}" ;;
    qc) printf '%s\n' "${QC_DIR}" ;;
    trim) printf '%s\n' "${TRIM_DIR}" ;;
    align) printf '%s\n' "${ALIGN_DIR}" ;;
    filter) printf '%s\n' "${FILTER_DIR}" ;;
    bam_qc) printf '%s\n' "${BAM_QC_DIR}" ;;
    peaks) printf '%s\n' "${PEAK_DIR}" ;;
    consensus) printf '%s\n' "${CONSENSUS_DIR}" ;;
    differential) printf '%s\n' "${DIFF_DIR}" ;;
    annotate) printf '%s\n' "${ANNOTATION_DIR}" ;;
    tracks) printf '%s\n' "${TRACK_DIR}" ;;
    report) printf '%s\n' "${REPORT_DIR}" ;;
    cleanup) printf '%s\n' "${REPORT_DIR}" ;;
    *) printf '%s\n' "${PROJECT_DIR}" ;;
  esac
}

join_deps() {
  local joined=""
  local dep
  for dep in "$@"; do
    [[ -n "${dep}" && "${dep}" != "dryrun" && "${dep}" != "local" ]] || continue
    if [[ -z "${joined}" ]]; then
      joined="${dep}"
    else
      joined="${joined}:${dep}"
    fi
  done
  printf '%s\n' "${joined}"
}

dependency_arg() {
  local deps dep spec afterok_deps afterany_deps
  local -a dep_tokens=()
  deps="$(join_deps "$@")"
  [[ -n "${deps}" ]] || return 0

  afterok_deps=""
  afterany_deps=""
  IFS=':' read -r -a dep_tokens <<< "${deps}"
  for dep in "${dep_tokens[@]}"; do
    [[ -n "${dep}" && "${dep}" != "dryrun" && "${dep}" != "local" ]] || continue
    if [[ "${dep}" == afterany__* ]]; then
      dep="${dep#afterany__}"
      [[ -n "${dep}" ]] || continue
      if [[ -z "${afterany_deps}" ]]; then
        afterany_deps="${dep}"
      else
        afterany_deps="${afterany_deps}:${dep}"
      fi
    else
      if [[ -z "${afterok_deps}" ]]; then
        afterok_deps="${dep}"
      else
        afterok_deps="${afterok_deps}:${dep}"
      fi
    fi
  done

  spec=""
  [[ -z "${afterok_deps}" ]] || spec="afterok:${afterok_deps}"
  if [[ -n "${afterany_deps}" ]]; then
    if [[ -n "${spec}" ]]; then
      spec="${spec},afterany:${afterany_deps}"
    else
      spec="afterany:${afterany_deps}"
    fi
  fi
  [[ -n "${spec}" ]] && printf '%s\n' "--dependency=${spec}"
  return 0
}

throttle_dep() {
  local -n submitted_ids="$1"
  local index="$2"
  local concurrency="$3"
  local previous_index

  if (( concurrency > 0 && index >= concurrency )); then
    previous_index=$((index - concurrency))
    if [[ -n "${submitted_ids[${previous_index}]:-}" ]]; then
      printf 'afterany__%s\n' "${submitted_ids[${previous_index}]}"
    fi
  fi
}

export_from_sbatch_spec() {
  local spec="$1"
  local token key value
  local -a tokens=()
  IFS=',' read -r -a tokens <<< "${spec}"
  for token in "${tokens[@]}"; do
    [[ -n "${token}" && "${token}" != "ALL" ]] || continue
    key="${token%%=*}"
    value="${token#*=}"
    [[ -n "${key}" && "${key}" != "${value}" ]] || continue
    export "${key}=${value}"
  done
}

run_local_or_print() {
  local chdir="${PROJECT_DIR}"
  local export_spec=""
  local -a command_args=()

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --chdir=*)
        chdir="${1#--chdir=}"
        shift
        ;;
      --chdir)
        chdir="$2"
        shift 2
        ;;
      --export=*)
        export_spec="${1#--export=}"
        shift
        ;;
      --export)
        export_spec="$2"
        shift 2
        ;;
      --dependency=*|--array=*|--parsable|--job-name=*|--cpus-per-task=*|--mem=*|--time=*|--partition=*|--account=*|--qos=*|--output=*|--error=*)
        shift
        ;;
      --dependency|--array|--job-name|--cpus-per-task|--mem|--time|--partition|--account|--qos|--output|--error)
        shift 2
        ;;
      *)
        command_args+=("$1")
        shift
        ;;
    esac
  done

  [[ "${#command_args[@]}" -gt 0 ]] || die "No command found for local execution."

  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '[local-dry-run] cd %q &&' "${chdir}"
    printf ' %q' bash "${command_args[@]}"
    printf '\n'
    SUBMITTED_JOB_ID="dryrun"
    return 0
  fi

  log "Local run: ${command_args[*]}"
  (
    cd "${chdir}"
    [[ -z "${export_spec}" ]] || export_from_sbatch_spec "${export_spec}"
    export PIPELINE_EXECUTOR="local"
    export RUN_MODE="local"
    export SLURM_CPUS_PER_TASK="${SLURM_CPUS_PER_TASK:-$LOCAL_CPUS_PER_TASK}"
    bash "${command_args[@]}"
  )
  SUBMITTED_JOB_ID="local"
}

submit_or_print() {
  if [[ "${PIPELINE_EXECUTOR}" == "local" ]]; then
    run_local_or_print "$@"
    return 0
  fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '[dry-run] sbatch'
    printf ' %q' "$@"
    printf '\n'
    SUBMITTED_JOB_ID="dryrun"
  else
    SUBMITTED_JOB_ID="$(submit_sbatch "$@")"
  fi
}

config_export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${CONFIG_FILE},PIPELINE_EXECUTOR=${PIPELINE_EXECUTOR},RUN_MODE=${RUN_MODE},OVERWRITE=${OVERWRITE:-false}"

SUBMITTED_JOB_ID=""
submit_job() {
  local step="$1"
  local target="$2"
  local deps="$3"
  local script="$4"
  shift 4
  local safe_target log_dir dep_arg work_dir
  safe_target="$(safe_name "${target}")"
  log_dir="${LOG_DIR}/${step}"
  work_dir="$(step_dir "${step}")"
  ensure_dir "${log_dir}" "${work_dir}"

  local -a args=(
    --parsable
    --chdir="${work_dir}"
    --export="${config_export}"
    --job-name="chipseq_${step}_${safe_target}"
    --cpus-per-task="${THREADS}"
    --output="${log_dir}/${safe_target}.out"
    --error="${log_dir}/${safe_target}.err"
  )
  [[ -z "${MEMORY}" ]] || args+=(--mem="${MEMORY}")
  [[ -z "${SLURM_TIME}" ]] || args+=(--time="${SLURM_TIME}")
  [[ -z "${SLURM_PARTITION}" ]] || args+=(--partition="${SLURM_PARTITION}")
  [[ -z "${SLURM_ACCOUNT}" ]] || args+=(--account="${SLURM_ACCOUNT}")
  [[ -z "${SLURM_QOS}" ]] || args+=(--qos="${SLURM_QOS}")
  dep_arg="$(dependency_arg "${deps}")"
  [[ -z "${dep_arg}" ]] || args+=("${dep_arg}")

  submit_or_print "${args[@]}" "${script}" "${CONFIG_FILE}" "$@"
  if [[ "${DRY_RUN}" == "true" && "${PIPELINE_EXECUTOR}" == "slurm" ]]; then
    SUBMITTED_JOB_ID="dryrun_${step}_${safe_target}"
  fi
  log "Step ${step}/${target}: ${SUBMITTED_JOB_ID}"
}

submit_sample_array() {
  local step="$1"
  local deps="$2"
  local concurrency="$3"
  local script="$4"
  shift 4
  local log_dir work_dir target_dir target_file target_count dep_arg array_spec safe_step

  target_count="$#"
  if (( target_count == 0 )); then
    log "Step ${step}: no sample targets; skipping array submission"
    SUBMITTED_JOB_ID=""
    return 0
  fi

  safe_step="$(safe_name "${step}")"
  log_dir="${LOG_DIR}/${step}"
  work_dir="$(step_dir "${step}")"
  target_dir="${METADATA_DIR}/slurm-arrays"
  target_file="${target_dir}/${safe_step}.targets.txt"
  ensure_dir "${log_dir}" "${work_dir}" "${target_dir}"
  printf '%s\n' "$@" > "${target_file}"

  array_spec="1-${target_count}"
  if (( concurrency > 0 )); then
    array_spec="${array_spec}%${concurrency}"
  fi

  local -a args=(
    --parsable
    --chdir="${work_dir}"
    --export="${config_export}"
    --job-name="chipseq_${step}_array"
    --cpus-per-task="${THREADS}"
    --array="${array_spec}"
    --output="${log_dir}/array_%A_%a.out"
    --error="${log_dir}/array_%A_%a.err"
  )
  [[ -z "${MEMORY}" ]] || args+=(--mem="${MEMORY}")
  [[ -z "${SLURM_TIME}" ]] || args+=(--time="${SLURM_TIME}")
  [[ -z "${SLURM_PARTITION}" ]] || args+=(--partition="${SLURM_PARTITION}")
  [[ -z "${SLURM_ACCOUNT}" ]] || args+=(--account="${SLURM_ACCOUNT}")
  [[ -z "${SLURM_QOS}" ]] || args+=(--qos="${SLURM_QOS}")
  dep_arg="$(dependency_arg "${deps}")"
  [[ -z "${dep_arg}" ]] || args+=("${dep_arg}")

  submit_or_print "${args[@]}" "${REPO_ROOT}/scripts/lib/slurm_array_task.sh" "${CONFIG_FILE}" "${target_file}" "${step}" "${script}"
  if [[ "${DRY_RUN}" == "true" && "${PIPELINE_EXECUTOR}" == "slurm" ]]; then
    SUBMITTED_JOB_ID="dryrun_${step}_array"
  fi
  log "Step ${step}/array: ${SUBMITTED_JOB_ID} (${target_count} tasks, concurrency ${concurrency})"
}

log "Pipeline: ${PIPELINE_NAME}"
log "Organism: ${ORGANISM_NAME}"
log "Executor: ${PIPELINE_EXECUTOR}"
log "Samples: $(metadata_samples | tr '\n' ' ')"
USE_SLURM_ARRAYS="false"
if [[ "${PIPELINE_EXECUTOR}" == "slurm" && "${SLURM_SAMPLE_SUBMISSION_MODE:-array}" == "array" ]]; then
  USE_SLURM_ARRAYS="true"
fi
log "Sample submission mode: ${SLURM_SAMPLE_SUBMISSION_MODE:-array}"
log "Sample job concurrency: qc=${QC_CONCURRENCY}, trim=${TRIM_CONCURRENCY}, align=${ALIGN_CONCURRENCY}, filter=${FILTER_CONCURRENCY}, bam_qc=${BAM_QC_CONCURRENCY}, peaks=${PEAKS_CONCURRENCY}, tracks=${TRACKS_CONCURRENCY}"

mapfile -t SAMPLES < <(metadata_samples)
mapfile -t IP_SAMPLES < <(metadata_ip_samples)

declare -A JOB_QC JOB_TRIM JOB_ALIGN JOB_FILTER JOB_BAMQC JOB_PEAK JOB_TRACK
REF_JOB=""
QC_ARRAY_JOB=""
TRIM_ARRAY_JOB=""
ALIGN_ARRAY_JOB=""
FILTER_ARRAY_JOB=""
BAM_QC_ARRAY_JOB=""
PEAK_ARRAY_JOB=""
TRACK_ARRAY_JOB=""
QC_MULTIQC_JOB=""
TRIM_MULTIQC_JOB=""
BAM_MULTIQC_JOB=""
FINGERPRINT_JOB=""
CONSENSUS_JOB=""
DIFF_JOB=""
ANNOTATE_JOB=""
TRACK_AGG_JOB=""
REPORT_JOB=""
CLEANUP_JOB=""

if has_step reference; then
  submit_job "reference" "reference" "" "${REF_SCRIPTS_DIR}/prepare_reference.sh"
  REF_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step qc; then
  if [[ "${USE_SLURM_ARRAYS}" == "true" ]]; then
    submit_sample_array "qc" "" "${QC_CONCURRENCY}" "${QC_SCRIPTS_DIR}/fastq_qc.sh" "${SAMPLES[@]}"
    QC_ARRAY_JOB="${SUBMITTED_JOB_ID}"
    submit_job "qc" "raw_multiqc" "${QC_ARRAY_JOB}" "${QC_SCRIPTS_DIR}/fastq_qc.sh" "raw_multiqc"
  else
    declare -a QC_ORDER=()
    idx=0
    for sample in "${SAMPLES[@]}"; do
      dep="$(throttle_dep QC_ORDER "${idx}" "${QC_CONCURRENCY}")"
      submit_job "qc" "${sample}" "${dep}" "${QC_SCRIPTS_DIR}/fastq_qc.sh" "${sample}"
      JOB_QC["${sample}"]="${SUBMITTED_JOB_ID}"
      QC_ORDER+=("${SUBMITTED_JOB_ID}")
      idx=$((idx + 1))
    done
    submit_job "qc" "raw_multiqc" "$(join_deps "${JOB_QC[@]}")" "${QC_SCRIPTS_DIR}/fastq_qc.sh" "raw_multiqc"
  fi
  QC_MULTIQC_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step trim; then
  if [[ "${USE_SLURM_ARRAYS}" == "true" ]]; then
    dep=""
    [[ "${RUN_ALL}" == "true" ]] && dep="${QC_ARRAY_JOB}"
    submit_sample_array "trim" "${dep}" "${TRIM_CONCURRENCY}" "${TRIM_SCRIPTS_DIR}/trim.sh" "${SAMPLES[@]}"
    TRIM_ARRAY_JOB="${SUBMITTED_JOB_ID}"
    submit_job "trim" "post_trim_multiqc" "${TRIM_ARRAY_JOB}" "${QC_SCRIPTS_DIR}/fastq_qc.sh" "post_trim_multiqc"
  else
    declare -a TRIM_ORDER=()
    idx=0
    for sample in "${SAMPLES[@]}"; do
      dep=""
      [[ "${RUN_ALL}" == "true" ]] && dep="${JOB_QC[${sample}]:-}"
      dep="$(join_deps "${dep}" "$(throttle_dep TRIM_ORDER "${idx}" "${TRIM_CONCURRENCY}")")"
      submit_job "trim" "${sample}" "${dep}" "${TRIM_SCRIPTS_DIR}/trim.sh" "${sample}"
      JOB_TRIM["${sample}"]="${SUBMITTED_JOB_ID}"
      TRIM_ORDER+=("${SUBMITTED_JOB_ID}")
      idx=$((idx + 1))
    done
    submit_job "trim" "post_trim_multiqc" "$(join_deps "${JOB_TRIM[@]}")" "${QC_SCRIPTS_DIR}/fastq_qc.sh" "post_trim_multiqc"
  fi
  TRIM_MULTIQC_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step align; then
  if [[ "${USE_SLURM_ARRAYS}" == "true" ]]; then
    dep=""
    [[ "${RUN_ALL}" == "true" ]] && dep="$(join_deps "${TRIM_ARRAY_JOB}" "${REF_JOB}")"
    submit_sample_array "align" "${dep}" "${ALIGN_CONCURRENCY}" "${ALIGN_SCRIPTS_DIR}/align.sh" "${SAMPLES[@]}"
    ALIGN_ARRAY_JOB="${SUBMITTED_JOB_ID}"
  else
    declare -a ALIGN_ORDER=()
    idx=0
    for sample in "${SAMPLES[@]}"; do
      dep=""
      [[ "${RUN_ALL}" == "true" ]] && dep="$(join_deps "${JOB_TRIM[${sample}]:-}" "${REF_JOB}")"
      dep="$(join_deps "${dep}" "$(throttle_dep ALIGN_ORDER "${idx}" "${ALIGN_CONCURRENCY}")")"
      submit_job "align" "${sample}" "${dep}" "${ALIGN_SCRIPTS_DIR}/align.sh" "${sample}"
      JOB_ALIGN["${sample}"]="${SUBMITTED_JOB_ID}"
      ALIGN_ORDER+=("${SUBMITTED_JOB_ID}")
      idx=$((idx + 1))
    done
  fi
fi

if has_step filter; then
  if [[ "${USE_SLURM_ARRAYS}" == "true" ]]; then
    dep=""
    [[ "${RUN_ALL}" == "true" ]] && dep="${ALIGN_ARRAY_JOB}"
    submit_sample_array "filter" "${dep}" "${FILTER_CONCURRENCY}" "${FILTER_SCRIPTS_DIR}/filter.sh" "${SAMPLES[@]}"
    FILTER_ARRAY_JOB="${SUBMITTED_JOB_ID}"
  else
    declare -a FILTER_ORDER=()
    idx=0
    for sample in "${SAMPLES[@]}"; do
      dep=""
      [[ "${RUN_ALL}" == "true" ]] && dep="${JOB_ALIGN[${sample}]:-}"
      dep="$(join_deps "${dep}" "$(throttle_dep FILTER_ORDER "${idx}" "${FILTER_CONCURRENCY}")")"
      submit_job "filter" "${sample}" "${dep}" "${FILTER_SCRIPTS_DIR}/filter.sh" "${sample}"
      JOB_FILTER["${sample}"]="${SUBMITTED_JOB_ID}"
      FILTER_ORDER+=("${SUBMITTED_JOB_ID}")
      idx=$((idx + 1))
    done
  fi
fi

if has_step bam_qc; then
  if [[ "${USE_SLURM_ARRAYS}" == "true" ]]; then
    dep=""
    [[ "${RUN_ALL}" == "true" ]] && dep="${FILTER_ARRAY_JOB}"
    submit_sample_array "bam_qc" "${dep}" "${BAM_QC_CONCURRENCY}" "${BAM_QC_SCRIPTS_DIR}/bam_qc.sh" "${SAMPLES[@]}"
    BAM_QC_ARRAY_JOB="${SUBMITTED_JOB_ID}"
    dep="${BAM_QC_ARRAY_JOB}"
  else
    declare -a BAM_QC_ORDER=()
    idx=0
    for sample in "${SAMPLES[@]}"; do
      dep=""
      [[ "${RUN_ALL}" == "true" ]] && dep="${JOB_FILTER[${sample}]:-}"
      dep="$(join_deps "${dep}" "$(throttle_dep BAM_QC_ORDER "${idx}" "${BAM_QC_CONCURRENCY}")")"
      submit_job "bam_qc" "${sample}" "${dep}" "${BAM_QC_SCRIPTS_DIR}/bam_qc.sh" "${sample}"
      JOB_BAMQC["${sample}"]="${SUBMITTED_JOB_ID}"
      BAM_QC_ORDER+=("${SUBMITTED_JOB_ID}")
      idx=$((idx + 1))
    done
    dep="$(join_deps "${JOB_BAMQC[@]}")"
  fi
  submit_job "bam_qc" "fingerprint" "${dep}" "${BAM_QC_SCRIPTS_DIR}/bam_qc.sh" "fingerprint"
  FINGERPRINT_JOB="${SUBMITTED_JOB_ID}"
  submit_job "bam_qc" "multiqc" "${dep}" "${BAM_QC_SCRIPTS_DIR}/bam_qc.sh" "multiqc"
  BAM_MULTIQC_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step peaks; then
  if [[ "${USE_SLURM_ARRAYS}" == "true" ]]; then
    dep=""
    [[ "${RUN_ALL}" == "true" ]] && dep="${FILTER_ARRAY_JOB}"
    submit_sample_array "peaks" "${dep}" "${PEAKS_CONCURRENCY}" "${PEAK_SCRIPTS_DIR}/call_peaks.sh" "${IP_SAMPLES[@]}"
    PEAK_ARRAY_JOB="${SUBMITTED_JOB_ID}"
  else
    declare -a PEAK_ORDER=()
    idx=0
    for sample in "${IP_SAMPLES[@]}"; do
      dep=""
      if [[ "${RUN_ALL}" == "true" ]]; then
        control_id="$(metadata_value "${sample}" "control_id")"
        if [[ -n "${control_id}" ]]; then
          dep="$(join_deps "${JOB_FILTER[${sample}]:-}" "${JOB_FILTER[${control_id}]:-}")"
        else
          dep="$(join_deps "${JOB_FILTER[${sample}]:-}")"
        fi
      fi
      dep="$(join_deps "${dep}" "$(throttle_dep PEAK_ORDER "${idx}" "${PEAKS_CONCURRENCY}")")"
      submit_job "peaks" "${sample}" "${dep}" "${PEAK_SCRIPTS_DIR}/call_peaks.sh" "${sample}"
      JOB_PEAK["${sample}"]="${SUBMITTED_JOB_ID}"
      PEAK_ORDER+=("${SUBMITTED_JOB_ID}")
      idx=$((idx + 1))
    done
  fi
fi

if has_step consensus; then
  dep=""
  if [[ "${RUN_ALL}" == "true" ]]; then
    if [[ "${USE_SLURM_ARRAYS}" == "true" ]]; then
      dep="${PEAK_ARRAY_JOB}"
    else
      dep="$(join_deps "${JOB_PEAK[@]}")"
    fi
  fi
  submit_job "consensus" "consensus" "${dep}" "${CONSENSUS_SCRIPTS_DIR}/consensus_peaks.sh"
  CONSENSUS_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step differential; then
  dep=""
  [[ "${RUN_ALL}" == "true" ]] && dep="${CONSENSUS_JOB}"
  submit_job "differential" "differential" "${dep}" "${DIFF_SCRIPTS_DIR}/differential_binding.sh"
  DIFF_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step annotate; then
  dep=""
  [[ "${RUN_ALL}" == "true" ]] && dep="$(join_deps "${CONSENSUS_JOB}" "${REF_JOB}")"
  submit_job "annotate" "annotation" "${dep}" "${ANNOTATION_SCRIPTS_DIR}/annotate_peaks.sh"
  ANNOTATE_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step tracks; then
  if [[ "${USE_SLURM_ARRAYS}" == "true" ]]; then
    dep=""
    [[ "${RUN_ALL}" == "true" ]] && dep="${FILTER_ARRAY_JOB}"
    submit_sample_array "tracks" "${dep}" "${TRACKS_CONCURRENCY}" "${TRACK_SCRIPTS_DIR}/tracks.sh" "${SAMPLES[@]}"
    TRACK_ARRAY_JOB="${SUBMITTED_JOB_ID}"
    dep="${TRACK_ARRAY_JOB}"
  else
    declare -a TRACK_ORDER=()
    idx=0
    for sample in "${SAMPLES[@]}"; do
      dep=""
      [[ "${RUN_ALL}" == "true" ]] && dep="${JOB_FILTER[${sample}]:-}"
      dep="$(join_deps "${dep}" "$(throttle_dep TRACK_ORDER "${idx}" "${TRACKS_CONCURRENCY}")")"
      submit_job "tracks" "${sample}" "${dep}" "${TRACK_SCRIPTS_DIR}/tracks.sh" "${sample}"
      JOB_TRACK["${sample}"]="${SUBMITTED_JOB_ID}"
      TRACK_ORDER+=("${SUBMITTED_JOB_ID}")
      idx=$((idx + 1))
    done
    dep="$(join_deps "${JOB_TRACK[@]}")"
  fi
  submit_job "tracks" "aggregate" "${dep}" "${TRACK_SCRIPTS_DIR}/tracks.sh" "aggregate"
  TRACK_AGG_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step report; then
  dep=""
  if [[ "${RUN_ALL}" == "true" ]]; then
    dep="$(join_deps "${QC_MULTIQC_JOB}" "${TRIM_MULTIQC_JOB}" "${BAM_MULTIQC_JOB}" "${FINGERPRINT_JOB}" "${CONSENSUS_JOB}" "${DIFF_JOB}" "${ANNOTATE_JOB}" "${TRACK_AGG_JOB}")"
  fi
  submit_job "report" "final_report" "${dep}" "${REPORT_SCRIPTS_DIR}/report.sh"
  REPORT_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step cleanup || { [[ "${RUN_ALL}" == "true" ]] && truthy "${RUN_STORAGE_CLEANUP_AFTER_REPORT:-0}"; }; then
  dep=""
  [[ "${RUN_ALL}" == "true" ]] && dep="${REPORT_JOB}"
  submit_job "cleanup" "storage" "${dep}" "${REPORT_SCRIPTS_DIR}/cleanup_storage.sh"
  CLEANUP_JOB="${SUBMITTED_JOB_ID}"
fi

log "Pipeline orchestration completed"
