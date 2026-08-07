#!/usr/bin/env bash

set -euo pipefail

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_LIB_DIR}/../.." && pwd)"

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

path_is_absolute() {
  local path="$1"
  [[ "$path" == /* || "$path" =~ ^[A-Za-z]:[\\/].* ]]
}

load_config() {
  local config_file="${1:-${REPO_ROOT}/config/pipeline_config.sh}"
  if ! path_is_absolute "${config_file}"; then
    config_file="${REPO_ROOT}/${config_file}"
  fi
  [[ -f "${config_file}" ]] || die "Config file not found: ${config_file}"
  # shellcheck source=/dev/null
  source "${config_file}"
  export PIPELINE_CONFIG="${config_file}"
}

bool_true() {
  case "${1,,}" in
    true|yes|y|1) return 0 ;;
    *) return 1 ;;
  esac
}

ensure_dir() {
  mkdir -p "$@"
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || die "Required command not found in PATH: ${cmd}"
}

activate_runtime() {
  case "${ENV_BACKEND:-none}" in
    none)
      ;;
    conda)
      local conda_base="${CONDA_BASE:-}"
      if [[ -z "${conda_base}" && -n "${HOME:-}" && -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]]; then
        conda_base="${HOME}/miniconda3"
      fi
      if [[ -n "${conda_base}" && -f "${conda_base}/etc/profile.d/conda.sh" ]]; then
        # shellcheck disable=SC1090
        source "${conda_base}/etc/profile.d/conda.sh"
        conda activate "${CONDA_ENV}"
      elif command -v conda >/dev/null 2>&1; then
        # shellcheck disable=SC1091
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate "${CONDA_ENV}"
      else
        warn "conda not found; continuing with current PATH"
      fi
      ;;
    apptainer|singularity)
      [[ -n "${CONTAINER_IMAGE:-}" ]] || die "CONTAINER_IMAGE must be set for ${ENV_BACKEND}"
      require_cmd "${ENV_BACKEND}"
      ;;
    *)
      die "Unsupported ENV_BACKEND: ${ENV_BACKEND}"
      ;;
  esac
}

pipeline_dirs() {
  cat <<'DIRS'
000-logs
010-input-validation
020-prepared-inputs
030-id-harmonization
040-peak-gene-mapping
050-rnaseq-summary
060-chipseq-summary
070-integrated-tables
080-candidate-scoring
090-visualizations
100-functional-analysis
110-reports
DIRS
}

create_output_tree() {
  local dir
  while read -r dir; do
    [[ -n "${dir}" ]] || continue
    ensure_dir "${INTEGRATION_OUTPUT_DIR}/${dir}"
  done < <(pipeline_dirs)
}

done_file() {
  local step_dir="$1"
  local name="$2"
  printf '%s/.done/%s.done\n' "${INTEGRATION_OUTPUT_DIR}/${step_dir}" "${name}"
}

is_done() {
  local step_dir="$1"
  local name="$2"
  [[ "${OVERWRITE:-false}" != "true" && -s "$(done_file "${step_dir}" "${name}")" ]]
}

mark_done() {
  local step_dir="$1"
  local name="$2"
  [[ "${CREATE_DONE_FILES:-true}" == "true" ]] || return 0
  ensure_dir "${INTEGRATION_OUTPUT_DIR}/${step_dir}/.done"
  date '+%Y-%m-%d %H:%M:%S' > "$(done_file "${step_dir}" "${name}")"
}

run_python_step() {
  local command="$1"
  shift || true
  require_cmd "${PYTHON_BIN}"
  activate_runtime
  "${PYTHON_BIN}" "${REPO_ROOT}/scripts/integrative_core.py" "${command}" "$@"
}
