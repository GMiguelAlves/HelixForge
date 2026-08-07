#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

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

load_config() {
  local config_file="${1:-${REPO_DIR}/config/pipeline_config.sh}"
  [[ -f "${config_file}" ]] || die "Config file not found: ${config_file}"
  # shellcheck source=/dev/null
  source "${config_file}"
}

load_chipseq_config() {
  load_config "$@"
}

bool_true() {
  case "${1,,}" in
    true|yes|y|1) return 0 ;;
    *) return 1 ;;
  esac
}

truthy() {
  bool_true "${1:-0}"
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || die "Required command not found in PATH: ${cmd}"
}

require_file() {
  local path="$1"
  local label="${2:-file}"
  [[ -f "${path}" ]] || die "${label} not found: ${path}"
}

decompress_gzip_if_needed() {
  local gz_path="$1"
  local out_path="${2:-${gz_path%.gz}}"
  if [[ -s "${out_path}" && "${OVERWRITE:-false}" != "true" ]]; then
    log "Already exists: ${out_path}"
    printf '%s\n' "${out_path}"
    return 0
  fi
  require_file "${gz_path}" "gzip file"
  ensure_dir "$(dirname "${out_path}")"
  log "Decompressing ${gz_path} -> ${out_path}"
  gzip -dc "${gz_path}" > "${out_path}"
  printf '%s\n' "${out_path}"
}

prepare_reference_input() {
  local input="$1"
  local out_dir="${2:-${REF_DATA_DIR:-${REF_DIR:-${OUTPUT_DIR}/010-reference}/data}}"
  local base out
  require_file "${input}" "reference input"
  if [[ "${input}" == *.gz ]]; then
    base="$(basename "${input%.gz}")"
    out="${out_dir}/${base}"
    decompress_gzip_if_needed "${input}" "${out}"
  else
    printf '%s\n' "${input}"
  fi
}

first_existing_table() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    printf '%s\n' "${path}"
  elif [[ "${path}" != *.gz && -f "${path}.gz" ]]; then
    printf '%s\n' "${path}.gz"
  elif [[ "${path}" == *.gz && -f "${path%.gz}" ]]; then
    printf '%s\n' "${path%.gz}"
  else
    printf '%s\n' "${path}"
  fi
}

table_name() {
  local stem="$1"
  local ext="${2:-.tsv}"
  printf '%s%s%s\n' "${stem}" "${ext}" "${PIPELINE_TABLE_SUFFIX:-}"
}

gzip_file_if_requested() {
  local path="$1"
  [[ -s "${path}" ]] || return 0
  [[ "${PIPELINE_TABLE_SUFFIX:-}" == ".gz" ]] || return 0
  [[ "${path}" != *.gz ]] || return 0
  require_cmd gzip
  gzip -f "${path}"
}

ensure_dir() {
  mkdir -p "$@"
}

safe_name() {
  printf '%s\n' "$1" | tr '/: ' '___'
}

resolve_path() {
  local path="$1"
  local base="${2:-${FASTQ_DIR:-.}}"
  if [[ -z "${path}" ]]; then
    printf ''
  elif [[ "${path}" = /* || "${path}" =~ ^[A-Za-z]:[\\/].* ]]; then
    printf '%s\n' "${path}"
  else
    printf '%s\n' "${base}/${path}"
  fi
}

done_file() {
  local step="$1"
  local name="$2"
  local dir="${OUTPUT_DIR}/${step}"
  case "${step}" in
    010-reference) dir="${REF_DIR:-${dir}}" ;;
    030-qc-fastq) dir="${QC_DIR:-${dir}}" ;;
    040-trimming) dir="${TRIM_DIR:-${dir}}" ;;
    050-alignment) dir="${ALIGN_DIR:-${dir}}" ;;
    060-filtering) dir="${FILTER_DIR:-${dir}}" ;;
    070-qc-alignment) dir="${BAM_QC_DIR:-${dir}}" ;;
    080-peak-calling) dir="${PEAK_DIR:-${dir}}" ;;
    090-peak-annotation) dir="${ANNOTATION_DIR:-${dir}}" ;;
    100-tracks) dir="${TRACK_DIR:-${dir}}" ;;
    110-consensus-peaks) dir="${CONSENSUS_DIR:-${dir}}" ;;
    120-differential-binding) dir="${DIFF_DIR:-${dir}}" ;;
    130-reports) dir="${REPORT_DIR:-${dir}}" ;;
  esac
  printf '%s/.done/%s.done\n' "${dir}" "${name}"
}

is_done() {
  local step="$1"
  local name="$2"
  [[ "${OVERWRITE:-false}" != "true" && -s "$(done_file "${step}" "${name}")" ]]
}

mark_done() {
  local step="$1"
  local name="$2"
  [[ "${CREATE_DONE_FILES:-true}" == "true" ]] || return 0
  ensure_dir "$(dirname "$(done_file "${step}" "${name}")")"
  date '+%Y-%m-%d %H:%M:%S' > "$(done_file "${step}" "${name}")"
}

metadata_header_index() {
  local column="$1"
  awk -F '\t' -v col="${column}" 'NR==1 { for (i=1; i<=NF; i++) if ($i==col) { print i; exit } }' "${METADATA_FILE}"
}

metadata_value() {
  local sample_id="$1"
  local column="$2"
  awk -F '\t' -v sample="${sample_id}" -v col="${column}" '
    NR==1 { for (i=1; i<=NF; i++) if ($i==col) c=i; next }
    $1==sample { print $c; exit }
  ' "${METADATA_FILE}"
}

metadata_samples() {
  awk -F '\t' 'NR>1 && $1!="" { print $1 }' "${METADATA_FILE}"
}

metadata_ip_samples() {
  awk -F '\t' '
    NR==1 {
      for (i=1; i<=NF; i++) {
        if ($i=="sample_id") s=i
        if ($i=="is_control") c=i
      }
      next
    }
    NR>1 && $s!="" {
      v=tolower($c)
      if (v!="true" && v!="1" && v!="yes") print $s
    }
  ' "${METADATA_FILE}"
}

metadata_control_samples() {
  awk -F '\t' '
    NR==1 {
      for (i=1; i<=NF; i++) {
        if ($i=="sample_id") s=i
        if ($i=="is_control") c=i
      }
      next
    }
    NR>1 && $s!="" {
      v=tolower($c)
      if (v=="true" || v=="1" || v=="yes") print $s
    }
  ' "${METADATA_FILE}"
}

sample_layout() {
  local sample_id="$1"
  local layout
  layout="$(metadata_value "${sample_id}" "layout")"
  if [[ "${READ_LAYOUT:-metadata}" == "paired" || "${READ_LAYOUT:-metadata}" == "single" ]]; then
    layout="${READ_LAYOUT}"
  fi
  printf '%s\n' "${layout,,}"
}

raw_fastqs_for_sample() {
  local sample_id="$1"
  local fq1 fq2
  fq1="$(resolve_path "$(metadata_value "${sample_id}" "fastq_1")" "${FASTQ_DIR}")"
  fq2="$(resolve_path "$(metadata_value "${sample_id}" "fastq_2")" "${FASTQ_DIR}")"
  printf '%s\t%s\n' "${fq1}" "${fq2}"
}

trimmed_fastqs_for_sample() {
  local sample_id="$1"
  local layout
  layout="$(sample_layout "${sample_id}")"
  if [[ "${layout}" == "paired" ]]; then
    printf '%s\t%s\n' \
      "${TRIM_DIR:-${OUTPUT_DIR}/040-trimming}/${sample_id}/${sample_id}_R1.trimmed.fastq.gz" \
      "${TRIM_DIR:-${OUTPUT_DIR}/040-trimming}/${sample_id}/${sample_id}_R2.trimmed.fastq.gz"
  else
    printf '%s\t\n' "${TRIM_DIR:-${OUTPUT_DIR}/040-trimming}/${sample_id}/${sample_id}.trimmed.fastq.gz"
  fi
}

filtered_bam_for_sample() {
  local sample_id="$1"
  printf '%s\n' "${FILTER_DIR:-${OUTPUT_DIR}/060-filtering}/${sample_id}/${sample_id}.filtered.bam"
}

activate_runtime() {
  case "${ENV_BACKEND:-none}" in
    none) ;;
    conda)
      if [[ -n "${CONDA_BASE:-}" && -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]]; then
        # shellcheck disable=SC1090
        source "${CONDA_BASE}/etc/profile.d/conda.sh"
        conda activate "${CONDA_ENV}"
        log "Activated Conda environment: ${CONDA_DEFAULT_ENV:-${CONDA_ENV}}"
      elif command -v conda >/dev/null 2>&1; then
        # shellcheck disable=SC1091
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate "${CONDA_ENV}"
        log "Activated Conda environment: ${CONDA_DEFAULT_ENV:-${CONDA_ENV}}"
      else
        die "Conda not found. Set CONDA_BASE in config/user_settings.sh or use ENV_BACKEND=none."
      fi
      ;;
    apptainer|singularity)
      [[ -n "${CONTAINER_IMAGE:-}" ]] || die "CONTAINER_IMAGE must be set when ENV_BACKEND=${ENV_BACKEND}"
      require_cmd "${ENV_BACKEND}"
      ;;
    *) die "Unsupported ENV_BACKEND: ${ENV_BACKEND}" ;;
  esac
}

run_cmd() {
  local cmd="$*"
  log "${cmd}"
  case "${ENV_BACKEND:-none}" in
    apptainer|singularity)
      "${ENV_BACKEND}" exec "${CONTAINER_IMAGE}" bash -lc "${cmd}"
      ;;
    *)
      bash -o pipefail -c "${cmd}"
      ;;
  esac
}

activate_conda_env() {
  local env_name="$1"
  if [[ -z "${CONDA_BASE:-}" || ! -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]]; then
    die "Conda not found in CONDA_BASE='${CONDA_BASE:-}'. Adjust CONDA_BASE in ${USER_SETTINGS_FILE:-config/user_settings.sh}."
  fi
  # shellcheck disable=SC1090
  source "${CONDA_BASE}/etc/profile.d/conda.sh"
  conda activate "$env_name"
}

activate_chipseq_tools() {
  activate_conda_env "${CHIPSEQ_TOOLS_ENV:-${CONDA_ENV:-chipseq}}"
}

activate_python_env() {
  activate_conda_env "${PYTHON_ENV:-${CONDA_ENV:-chipseq}}"
}

activate_r_analysis() {
  activate_conda_env "${R_ANALYSIS_ENV:-${CONDA_ENV:-chipseq}}"
}

submit_sbatch() {
  local output job_id
  echo "+ sbatch $*" >&2
  output="$(sbatch "$@")"
  echo "$output" >&2
  job_id="$(echo "$output" | tail -n 1 | awk '{print $NF}' | cut -d';' -f1)"
  if [[ ! "$job_id" =~ ^[0-9]+([._][0-9]+)?$ ]]; then
    die "Could not extract Slurm job id from: $output"
  fi
  echo "$job_id"
}

create_output_tree() {
  ensure_dir \
    "${LOG_DIR:-${OUTPUT_DIR}/000-logs}" \
    "${REF_DIR:-${OUTPUT_DIR}/010-reference}" \
    "${METADATA_DIR:-${OUTPUT_DIR}/020-metadata}" \
    "${QC_DIR:-${OUTPUT_DIR}/030-qc-fastq}" \
    "${TRIM_DIR:-${OUTPUT_DIR}/040-trimming}" \
    "${ALIGN_DIR:-${OUTPUT_DIR}/050-alignment}" \
    "${FILTER_DIR:-${OUTPUT_DIR}/060-filtering}" \
    "${BAM_QC_DIR:-${OUTPUT_DIR}/070-qc-alignment}" \
    "${PEAK_DIR:-${OUTPUT_DIR}/080-peak-calling}" \
    "${ANNOTATION_DIR:-${OUTPUT_DIR}/090-peak-annotation}" \
    "${TRACK_DIR:-${OUTPUT_DIR}/100-tracks}" \
    "${CONSENSUS_DIR:-${OUTPUT_DIR}/110-consensus-peaks}" \
    "${DIFF_DIR:-${OUTPUT_DIR}/120-differential-binding}" \
    "${REPORT_DIR:-${OUTPUT_DIR}/130-reports}"
}

create_chipseq_output_tree() {
  create_output_tree "$@"
}
