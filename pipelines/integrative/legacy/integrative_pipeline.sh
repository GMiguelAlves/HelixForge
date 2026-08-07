#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "${REPO_ROOT}/scripts/lib/common.sh"

CONFIG_FILE="${REPO_ROOT}/config/pipeline_config.sh"
DRY_RUN="false"
RUN_ALL="false"
FORCE="false"
RUN_MODE_OVERRIDE=""
declare -a REQUESTED_STEPS=()

usage() {
  cat <<'USAGE'
Usage: bash integrative_pipeline.sh [options]

Options:
  --config FILE          Configuration file (default: config/pipeline_config.sh)
  --all                  Run the complete integration workflow
  --step STEP            Run one step. Can be repeated.
                         Steps: validate, prepare, harmonize, map-peaks,
                                summarize-rna, summarize-chip, integrate,
                                score, visualize, functional, report
  --dry-run              Print shell commands or Slurm submissions
  --resume               Skip steps with .done files (default)
  --force                Re-run steps even when .done files exist
  --mode MODE            Override RUN_MODE: slurm or local
  --slurm                Shortcut for --mode slurm
  -h, --help             Show this help

Examples:
  bash integrative_pipeline.sh --all --dry-run
  bash integrative_pipeline.sh --step validate --step harmonize
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
    --mode)
      RUN_MODE_OVERRIDE="$2"
      shift 2
      ;;
    --slurm)
      RUN_MODE_OVERRIDE="slurm"
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

load_config "${CONFIG_FILE}"
if [[ -n "${RUN_MODE_OVERRIDE}" ]]; then
  export RUN_MODE="${RUN_MODE_OVERRIDE}"
fi
if [[ "${FORCE}" == "true" ]]; then
  export OVERWRITE="true"
fi
case "${RUN_MODE}" in
  slurm|local) ;;
  *) die "Invalid RUN_MODE '${RUN_MODE}'. Use slurm or local." ;;
esac

create_output_tree

declare -A STEP_ALIASES=(
  [validate]="validate"
  [validation]="validate"
  [prepare]="prepare"
  [prep]="prepare"
  [harmonize]="harmonize"
  [ids]="harmonize"
  [map-peaks]="map-peaks"
  [map_peaks]="map-peaks"
  [peaks]="map-peaks"
  [summarize-rna]="summarize-rna"
  [summarize_rna]="summarize-rna"
  [rna]="summarize-rna"
  [summarize-chip]="summarize-chip"
  [summarize_chip]="summarize-chip"
  [chip]="summarize-chip"
  [integrate]="integrate"
  [integration]="integrate"
  [score]="score"
  [scoring]="score"
  [visualize]="visualize"
  [plots]="visualize"
  [functional]="functional"
  [function]="functional"
  [report]="report"
)

ORDER=(validate prepare harmonize map-peaks summarize-rna summarize-chip integrate score visualize functional report)
declare -A SELECTED=()
if [[ "${RUN_ALL}" == "true" ]]; then
  for step in "${ORDER[@]}"; do
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

join_deps() {
  local dep joined=""
  for dep in "$@"; do
    [[ -n "${dep}" && "${dep}" != "local" ]] || continue
    if [[ -z "${joined}" ]]; then
      joined="${dep}"
    else
      joined="${joined}:${dep}"
    fi
  done
  printf '%s\n' "${joined}"
}

STEP_SCRIPT() {
  case "$1" in
    validate) printf '%s\n' "${REPO_ROOT}/scripts/00_validate_inputs.sh" ;;
    prepare) printf '%s\n' "${REPO_ROOT}/scripts/01_prepare_inputs.sh" ;;
    harmonize) printf '%s\n' "${REPO_ROOT}/scripts/02_harmonize_ids.sh" ;;
    map-peaks) printf '%s\n' "${REPO_ROOT}/scripts/03_map_peaks.sh" ;;
    summarize-rna) printf '%s\n' "${REPO_ROOT}/scripts/04_summarize_rna.sh" ;;
    summarize-chip) printf '%s\n' "${REPO_ROOT}/scripts/05_summarize_chip.sh" ;;
    integrate) printf '%s\n' "${REPO_ROOT}/scripts/06_integrate.sh" ;;
    score) printf '%s\n' "${REPO_ROOT}/scripts/07_score_candidates.sh" ;;
    visualize) printf '%s\n' "${REPO_ROOT}/scripts/08_visualize.sh" ;;
    functional) printf '%s\n' "${REPO_ROOT}/scripts/09_functional_analysis.sh" ;;
    report) printf '%s\n' "${REPO_ROOT}/scripts/10_render_report.sh" ;;
    *) die "Unknown script for step $1" ;;
  esac
}

STEP_DIR() {
  case "$1" in
    validate) printf '%s\n' "010-input-validation" ;;
    prepare) printf '%s\n' "020-prepared-inputs" ;;
    harmonize) printf '%s\n' "030-id-harmonization" ;;
    map-peaks) printf '%s\n' "040-peak-gene-mapping" ;;
    summarize-rna) printf '%s\n' "050-rnaseq-summary" ;;
    summarize-chip) printf '%s\n' "060-chipseq-summary" ;;
    integrate) printf '%s\n' "070-integrated-tables" ;;
    score) printf '%s\n' "080-candidate-scoring" ;;
    visualize) printf '%s\n' "090-visualizations" ;;
    functional) printf '%s\n' "100-functional-analysis" ;;
    report) printf '%s\n' "110-reports" ;;
    *) die "Unknown dir for step $1" ;;
  esac
}

SUBMITTED_JOB_ID=""
submit_step() {
  local step="$1"
  local deps="$2"
  local script
  script="$(STEP_SCRIPT "${step}")"
  local step_dir log_dir
  step_dir="$(STEP_DIR "${step}")"
  log_dir="${INTEGRATION_OUTPUT_DIR}/000-logs/${step}"
  ensure_dir "${log_dir}"

  if [[ "${DRY_RUN}" == "true" ]]; then
    if [[ "${RUN_MODE}" == "local" ]]; then
      printf '[local-dry-run] bash %q %q\n' "${script}" "${PIPELINE_CONFIG}"
    else
      printf '[dry-run] sbatch step=%s deps=%s bash %q %q\n' "${step}" "${deps:-none}" "${script}" "${PIPELINE_CONFIG}"
    fi
    SUBMITTED_JOB_ID="dryrun_${step}"
    return 0
  fi

  if [[ "${RUN_MODE}" == "local" ]]; then
    log "Running locally: ${step}"
    bash "${script}" "${PIPELINE_CONFIG}"
    SUBMITTED_JOB_ID="local"
    return 0
  fi

  command -v sbatch >/dev/null 2>&1 || die "sbatch not found; use --mode local or --dry-run on non-Slurm systems"
  local -a sbatch_args=(
    --parsable
    --job-name="integrateseq_${step}"
    --cpus-per-task="${THREADS}"
    --mem="${MEMORY}"
    --time="${SLURM_TIME}"
    --output="${log_dir}/${step}.out"
    --error="${log_dir}/${step}.err"
  )
  [[ -z "${SLURM_ACCOUNT}" ]] || sbatch_args+=(--account="${SLURM_ACCOUNT}")
  [[ -z "${deps}" ]] || sbatch_args+=(--dependency="afterok:${deps}")
  SUBMITTED_JOB_ID="$(sbatch "${sbatch_args[@]}" --wrap "$(printf '%q ' bash "${script}" "${PIPELINE_CONFIG}")")"
  log "Submitted ${step}: ${SUBMITTED_JOB_ID}"
}

declare -A JOBS=()
for step in "${ORDER[@]}"; do
  has_step "${step}" || continue
  deps=""
  case "${step}" in
    prepare) deps="$(join_deps "${JOBS[validate]:-}")" ;;
    harmonize) deps="$(join_deps "${JOBS[prepare]:-}")" ;;
    map-peaks) deps="$(join_deps "${JOBS[harmonize]:-}")" ;;
    summarize-rna) deps="$(join_deps "${JOBS[prepare]:-}" "${JOBS[harmonize]:-}")" ;;
    summarize-chip) deps="$(join_deps "${JOBS[map-peaks]:-}")" ;;
    integrate) deps="$(join_deps "${JOBS[summarize-rna]:-}" "${JOBS[summarize-chip]:-}")" ;;
    score) deps="$(join_deps "${JOBS[integrate]:-}")" ;;
    visualize) deps="$(join_deps "${JOBS[score]:-}")" ;;
    functional) deps="$(join_deps "${JOBS[score]:-}")" ;;
    report) deps="$(join_deps "${JOBS[visualize]:-}" "${JOBS[functional]:-}")" ;;
  esac
  submit_step "${step}" "${deps}"
  JOBS["${step}"]="${SUBMITTED_JOB_ID}"
done

log "Integration orchestration completed"
