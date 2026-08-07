#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:-config/pipeline_config.sh}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_rnaseq_config "${CONFIG_FILE}"

create_rnaseq_output_tree

[[ -d "${PROJECT_DIR}" ]] || die "PROJECT_DIR does not exist: ${PROJECT_DIR}"

if [[ ! -f "${USER_SETTINGS_FILE:-}" ]]; then
  warn "User settings file not found: ${USER_SETTINGS_FILE:-config/user_settings.sh}"
  warn "For simple setup, run: cp config/user_settings_template.sh config/user_settings.sh"
fi

if [[ -z "${PIPELINE_PROJECTS//,/ }" ]]; then
  die "PIPELINE_PROJECTS is empty. Add at least one project accession."
fi

case "${PIPELINE_PROJECTS}" in
  *PRJXXXX*|*PRJYYYY*)
    die "PIPELINE_PROJECTS still contains template values. Edit config/user_settings.sh."
    ;;
esac

if [[ "${ORGANISM_NAME}" == "My organism" || "${ORGANISM_NAME}" == "custom_organism" ]]; then
  die "ORGANISM_NAME still contains a template value. Edit config/user_settings.sh."
fi

for value in "${SCRATCH_ROOT:-}" "${CONDA_BASE:-}" "${GENOME_URL:-}" "${TRANSCRIPTS_URL:-}" "${GFF3_URL:-}" "${REF_GENOME_FA:-}" "${REF_TRANSCRIPTS_FA:-}" "${REF_GFF3:-}" "${REF_GTF:-}"; do
  case "${value}" in
    *example.org*|/path/to/*|*/path/to/*|*/my_user/*)
      die "Configuration still contains a template path or URL: ${value}"
      ;;
  esac
done

if [[ -z "${CONDA_BASE:-}" ]]; then
  warn "CONDA_BASE is empty. Jobs will fail unless conda is available in the Slurm environment."
fi

case "${QUANT_METHOD:-salmon}" in
  salmon|star)
    ;;
  *)
    die "QUANT_METHOD must be 'salmon' or 'star'. Current value: ${QUANT_METHOD}"
    ;;
esac

case "${STAR_GENECOUNT_COLUMN:-unstranded}" in
  unstranded|stranded_forward|stranded_reverse|2|3|4)
    ;;
  *)
    die "STAR_GENECOUNT_COLUMN must be unstranded, stranded_forward, stranded_reverse, 2, 3, or 4."
    ;;
esac

if [[ "${RUN_SALMON_INDEX}" == "1" && -z "${REF_TRANSCRIPTS_FA}" && -z "${TRANSCRIPTS_URL}" ]]; then
  die "Salmon index requested, but REF_TRANSCRIPTS_FA and TRANSCRIPTS_URL are empty."
fi

if [[ "${RUN_STAR_INDEX}" == "1" && -z "${REF_GENOME_FA}" && -z "${GENOME_URL}" ]]; then
  die "STAR index requested, but REF_GENOME_FA and GENOME_URL are empty."
fi

if [[ "${RUN_STAR_GTF_INDEX}" == "1" ]]; then
  if [[ -z "${REF_GENOME_FA}" && -z "${GENOME_URL}" ]]; then
    die "STAR+GTF index requested, but REF_GENOME_FA and GENOME_URL are empty."
  fi
  if [[ -z "${REF_GTF}" && -z "${GTF_URL}" && -z "${REF_GFF3}" && -z "${GFF3_URL}" ]]; then
    die "STAR+GTF index requested, but no GTF/GFF3 input was configured."
  fi
fi

if [[ "${QUANT_METHOD}" == "star" ]]; then
  if [[ "${RUN_STAR_GTF_INDEX}" != "1" && ! -d "${STAR_QUANT_INDEX_DIR}" ]]; then
    warn "QUANT_METHOD=star but STAR_QUANT_INDEX_DIR does not exist yet: ${STAR_QUANT_INDEX_DIR}"
    warn "Set RUN_STAR_GTF_INDEX=1 to build it, or point STAR_QUANT_INDEX_DIR to an existing STAR index built with a GTF/GFF annotation."
  fi
  if [[ "${RUN_STAR_GTF_INDEX}" == "1" && -z "${REF_GTF}" && -z "${GTF_URL}" && -z "${REF_GFF3}" && -z "${GFF3_URL}" ]]; then
    die "QUANT_METHOD=star needs REF_GTF/GTF_URL or REF_GFF3/GFF3_URL so STAR can produce gene counts."
  fi
fi

case "${PIPELINE_EXECUTOR:-slurm}" in
  slurm|local)
    ;;
  *)
    die "PIPELINE_EXECUTOR must be 'slurm' or 'local'. Current value: ${PIPELINE_EXECUTOR}"
    ;;
esac

while read -r project; do
  [[ -n "${project}" ]] || continue
  if [[ ! -f "${DATASET_CONFIG_DIR}/${project}/config.yaml" ]]; then
    warn "Download config missing for ${project}: ${DATASET_CONFIG_DIR}/${project}/config.yaml"
  fi
  if [[ ! -f "${METADATA_PARSER_DIR}/${project}/configs/${project}.yaml" ]]; then
    warn "Metadata parser YAML missing for ${project}: ${METADATA_PARSER_DIR}/${project}/configs/${project}.yaml"
  fi
done < <(pipeline_projects)

if [[ "${PIPELINE_EXECUTOR:-slurm}" == "slurm" && "${SKIP_SLURM_CHECK:-false}" != "true" ]]; then
  require_cmd sbatch
fi

log "Configuration validation passed"
