#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "${REPO_ROOT}/scripts/lib/common.sh"

CONFIG_FILE="${REPO_ROOT}/config/pipeline_config.sh"
DRY_RUN="false"
RUN_ALL="false"
EXECUTOR_OVERRIDE=""
declare -a REQUESTED_STEPS=()

usage() {
  cat <<'USAGE'
Usage: bash rnaseq_pipeline.sh [options]

Options:
  --config FILE          Configuration file (default: config/pipeline_config.sh)
  --all                  Run the complete RNA-seq workflow
  --step STEP            Run one step. Can be repeated.
                         Steps: reference, download, metadata, qc, salmon/star,
                                tximport, batch, deg, report
  --executor MODE        Execution backend: slurm or local
  --local                Shortcut for --executor local
  --dry-run              Print commands without executing jobs
  -h, --help             Show this help

Examples:
  bash rnaseq_pipeline.sh --all
  bash rnaseq_pipeline.sh --all --dry-run
  bash rnaseq_pipeline.sh --all --local
  bash rnaseq_pipeline.sh --step metadata --step qc
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
    --executor)
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

load_rnaseq_config "${CONFIG_FILE}"
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
create_rnaseq_output_tree

if [[ "${DRY_RUN}" == "true" || "${PIPELINE_EXECUTOR}" == "local" ]]; then
  export SKIP_SLURM_CHECK="true"
fi

bash "${REPO_ROOT}/scripts/validate_config.sh" "${CONFIG_FILE}"

declare -A STEP_ALIASES=(
  [reference]="reference"
  [ref]="reference"
  [download]="download"
  [metadata]="metadata"
  [parse]="metadata"
  [qc]="qc"
  [salmon]="salmon"
  [star]="salmon"
  [alignment]="salmon"
  [quant]="salmon"
  [tximport]="tximport"
  [import]="tximport"
  [batch]="batch"
  [deg]="deg"
  [report]="report"
)

declare -A SELECTED=()
if [[ "${RUN_ALL}" == "true" ]]; then
  for step in reference download metadata qc salmon tximport deg; do
    SELECTED["${step}"]=1
  done
  [[ "${RUN_BATCH_CORRECTION}" == "1" ]] && SELECTED["batch"]=1
  [[ "${RUN_GENE_REPORT}" == "1" ]] && SELECTED["report"]=1
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

submit_or_print() {
  if [[ "${PIPELINE_EXECUTOR}" == "local" ]]; then
    run_local_or_print "$@"
    return 0
  fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
    SUBMITTED_JOB_ID="dryrun"
  else
    SUBMITTED_JOB_ID="$(submit_sbatch "$@")"
  fi
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
  local deps
  deps="$(join_deps "$@")"
  [[ -n "${deps}" ]] && printf '%s\n' "--dependency=afterok:${deps}"
  return 0
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
      --dependency=*|--array=*|--parsable)
        shift
        ;;
      --dependency|--array)
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
    export SLURM_CPUS_PER_TASK="${SLURM_CPUS_PER_TASK:-$LOCAL_CPUS_PER_TASK}"
    bash "${command_args[@]}"
  )
  SUBMITTED_JOB_ID="local"
}

config_export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${CONFIG_FILE},PIPELINE_EXECUTOR=${PIPELINE_EXECUTOR}"

log "Pipeline: ${PIPELINE_NAME}"
log "Organism: ${ORGANISM_NAME}"
log "Executor: ${PIPELINE_EXECUTOR}"
log "Quantification method: ${QUANT_METHOD}"
log "Projects: $(pipeline_projects | tr '\n' ' ')"

declare -a REF_JOBS DOWNLOAD_JOBS PARSE_JOBS QC_JOBS ALIGNMENT_JOBS
META_MERGE_JOB=""
TXIMPORT_JOB=""
BATCH_JOB=""
DEG_JOB=""

if has_step reference; then
  if [[ "${RUN_SALMON_INDEX}" == "1" ]]; then
    submit_or_print --chdir="${REF_DIR}" --export="${config_export}" "${REF_SCRIPTS_DIR}/salmon_index.sh"
    REF_JOBS+=("${SUBMITTED_JOB_ID}")
  fi
  if [[ "${RUN_STAR_INDEX}" == "1" ]]; then
    submit_or_print --chdir="${REF_DIR}" --export="${config_export}" "${REF_SCRIPTS_DIR}/star_index.sh"
    REF_JOBS+=("${SUBMITTED_JOB_ID}")
  fi
  if [[ "${RUN_STAR_GTF_INDEX}" == "1" ]]; then
    submit_or_print --chdir="${REF_DIR}" --export="${config_export}" "${REF_SCRIPTS_DIR}/star_index_gtf.sh"
    REF_JOBS+=("${SUBMITTED_JOB_ID}")
  fi
fi

if has_step download; then
  while read -r project; do
    submit_or_print --chdir="${DOWNLOAD_DIR}" --export="${config_export}" "${DOWNLOAD_SCRIPTS_DIR}/download_final.sh" "${project}"
    DOWNLOAD_JOBS+=("${project}:${SUBMITTED_JOB_ID}")
  done < <(pipeline_projects)
fi

if has_step metadata; then
  while read -r project; do
    submit_or_print --chdir="${PARSE_DIR}" --export="${config_export}" "${PARSE_SCRIPTS_DIR}/run_metaqc.sh" "${project}"
    metaqc_job="${SUBMITTED_JOB_ID}"
    parse_args=(--chdir="${PARSE_DIR}" --export="${config_export}")
    dep_arg="$(dependency_arg "${metaqc_job}")"
    [[ -n "${dep_arg}" ]] && parse_args+=("${dep_arg}")
    submit_or_print "${parse_args[@]}" "${PARSE_SCRIPTS_DIR}/run_parse.sh" "${project}"
    PARSE_JOBS+=("${SUBMITTED_JOB_ID}")
  done < <(pipeline_projects)

  merge_args=(--chdir="${PARSE_DIR}" --export="${config_export}")
  dep_arg="$(dependency_arg "${PARSE_JOBS[@]}")"
  [[ -n "${dep_arg}" ]] && merge_args+=("${dep_arg}")
  submit_or_print "${merge_args[@]}" "${PARSE_SCRIPTS_DIR}/run_merge.sh"
  META_MERGE_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step qc; then
  index=0
  while read -r project; do
    qc_args=(--chdir="${QC_DIR}" --export="${config_export}")
    deps=()
    [[ "${RUN_ALL}" == "true" && -n "${META_MERGE_JOB}" ]] && deps+=("${META_MERGE_JOB}")
    if [[ "${RUN_ALL}" == "true" && "${#DOWNLOAD_JOBS[@]}" -gt "${index}" ]]; then
      deps+=("${DOWNLOAD_JOBS[$index]#*:}")
    fi
    dep_arg="$(dependency_arg "${deps[@]:-}")"
    [[ -n "${dep_arg}" ]] && qc_args+=("${dep_arg}")
    submit_or_print "${qc_args[@]}" "${QC_SCRIPTS_DIR}/run_qc_project.sh" "${project}"
    QC_JOBS+=("${SUBMITTED_JOB_ID}")
    index=$((index + 1))
  done < <(pipeline_projects)
fi

if has_step salmon; then
  if [[ "${QUANT_METHOD}" == "star" ]]; then
    alignment_runner="${ALIGN_SCRIPTS_DIR}/run_star_quant_project.sh"
    alignment_label="STAR"
  else
    alignment_runner="${ALIGN_SCRIPTS_DIR}/run_alignment_project.sh"
    alignment_label="Salmon"
  fi
  log "Step 040 quant/alignment: ${alignment_label}"
  index=0
  while read -r project; do
    salmon_args=(--chdir="${ALIGN_DIR}" --export="${config_export}")
    deps=()
    [[ "${RUN_ALL}" == "true" && "${#QC_JOBS[@]}" -gt "${index}" ]] && deps+=("${QC_JOBS[$index]}")
    [[ "${RUN_ALL}" == "true" && "${#REF_JOBS[@]}" -gt 0 ]] && deps+=("${REF_JOBS[@]}")
    dep_arg="$(dependency_arg "${deps[@]:-}")"
    [[ -n "${dep_arg}" ]] && salmon_args+=("${dep_arg}")
    submit_or_print "${salmon_args[@]}" "${alignment_runner}" "${project}" "${QC_DIR}/work/${project}_qc_plan.csv"
    ALIGNMENT_JOBS+=("${SUBMITTED_JOB_ID}")
    index=$((index + 1))
  done < <(pipeline_projects)
fi

if has_step tximport; then
  tximport_args=(--chdir="${QUANTIFICATION_DIR}" --export="${config_export},STEP_DIR=${QUANT_SCRIPTS_DIR}")
  dep_arg="$(dependency_arg "${ALIGNMENT_JOBS[@]:-}")"
  [[ "${RUN_ALL}" == "true" && -n "${dep_arg}" ]] && tximport_args+=("${dep_arg}")
  submit_or_print "${tximport_args[@]}" "${QUANT_SCRIPTS_DIR}/quantification_job.sh" --all --method "${QUANT_METHOD}"
  TXIMPORT_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step batch; then
  batch_args=(--chdir="${BATCH_DIR}" --export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${CONFIG_FILE},PIPELINE_EXECUTOR=${PIPELINE_EXECUTOR},STEP_DIR=${BATCH_SCRIPTS_DIR}")
  dep_arg="$(dependency_arg "${TXIMPORT_JOB}")"
  [[ "${RUN_ALL}" == "true" && -n "${dep_arg}" ]] && batch_args+=("${dep_arg}")
  submit_or_print "${batch_args[@]}" "${BATCH_SCRIPTS_DIR}/batch_correction_job.sh" --all --batch-column "${BATCH_COLUMN}" --covariates "${BATCH_COVARIATES}" --skip-if-single-batch
  BATCH_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step deg; then
  deg_args=(--chdir="${DEG_DIR}" --export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${CONFIG_FILE},PIPELINE_EXECUTOR=${PIPELINE_EXECUTOR},STEP_DIR=${DEG_SCRIPTS_DIR}")
  if [[ "${RUN_ALL}" == "true" ]]; then
    dep_arg="$(dependency_arg "${BATCH_JOB:-${TXIMPORT_JOB}}")"
    [[ -n "${dep_arg}" ]] && deg_args+=("${dep_arg}")
  fi
  submit_or_print "${deg_args[@]}" "${DEG_SCRIPTS_DIR}/run_deg_analysis_slurm.sh" --include-all
  DEG_JOB="${SUBMITTED_JOB_ID}"
fi

if has_step report; then
  report_args=(--chdir="${GENE_REPORT_DIR}" --export="ALL,PROJECT_DIR=${PROJECT_DIR},PIPELINE_CONFIG=${CONFIG_FILE},PIPELINE_EXECUTOR=${PIPELINE_EXECUTOR},STEP_DIR=${GENE_REPORT_SCRIPTS_DIR}")
  dep_arg="$(dependency_arg "${DEG_JOB}")"
  [[ "${RUN_ALL}" == "true" && -n "${dep_arg}" ]] && report_args+=("${dep_arg}")
  submit_or_print "${report_args[@]}" "${GENE_REPORT_SCRIPTS_DIR}/gene_report_job.sh" \
    --genes "${GENE_REPORT_DIR}/genes.txt" \
    --tpm "${EXPRESSION_MATRIX_FILE}" \
    --expression-unit "${EXPRESSION_UNIT}" \
    --samples "${QUANTIFICATION_DIR}/quant_samples.tsv" \
    --metadata "$(metadata_default)" \
    --deg-root "${DEG_DIR}" \
    --gff "${GENE_REPORT_ANNOTATION_FILE}" \
    --output-dir "${GENE_REPORT_DIR}/results" \
    --title "${GENE_REPORT_TITLE}"
fi

log "Pipeline orchestration completed"
