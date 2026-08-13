#!/usr/bin/env bash

# Central configuration engine for the RNA-seq pipeline.
#
# Most users should NOT edit the advanced defaults below.
# Instead:
#
#   cp config/user_settings_template.sh config/user_settings.sh
#   edit config/user_settings.sh
#   bash rnaseq_pipeline.sh --all --dry-run
#
# Keep project-specific metadata rules in:
#   025-parse/020-metadata_parsers/<PROJECT>/configs/<PROJECT>.yaml

set -o pipefail

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    export PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
else
    export PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
fi

# ---------------------------------------------------------------------------
# Simple user settings
# ---------------------------------------------------------------------------
# This optional file is the only file non-bioinformatics users should edit.
# Values in user_settings.sh override the advanced defaults below.
export USER_SETTINGS_FILE="${USER_SETTINGS_FILE:-${PROJECT_DIR}/config/user_settings.sh}"
if [[ -f "$USER_SETTINGS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$USER_SETTINGS_FILE"
fi

# ---------------------------------------------------------------------------
# Advanced defaults: project and organism metadata
# ---------------------------------------------------------------------------
export PIPELINE_NAME="${PIPELINE_NAME:-rnaseq_pipeline}"
export ORGANISM_NAME="${ORGANISM_NAME:-custom_organism}"

# Space- or comma-separated ENA/SRA project accessions, for example:
#   export PIPELINE_PROJECTS="PRJNA000001 PRJEB000002"
export PIPELINE_PROJECTS="${PIPELINE_PROJECTS:-}"

# ENA metadata columns downloaded by step 025.
export ENA_FIELDS="${ENA_FIELDS:-study_accession,sample_accession,run_accession,tax_id,scientific_name,library_name,center_name,study_title,fastq_ftp,submitted_ftp,sample_alias}"
export ENA_RESULT="${ENA_RESULT:-read_run}"
export METADATA_SCHEMA_FILE="${METADATA_SCHEMA_FILE:-}"
export METAQC_KEEP_COLUMNS="${METAQC_KEEP_COLUMNS:-sample_id,run_accession,study_accession}"

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
export REF_DIR="${REF_DIR:-${PROJECT_DIR}/010-reference}"
export DOWNLOAD_DIR="${DOWNLOAD_DIR:-${PROJECT_DIR}/020-data-download}"
export PARSE_DIR="${PARSE_DIR:-${PROJECT_DIR}/025-parse}"
export QC_DIR="${QC_DIR:-${PROJECT_DIR}/030-qc-fastq}"
export ALIGN_DIR="${ALIGN_DIR:-${PROJECT_DIR}/040-alignment}"
export QUANTIFICATION_DIR="${QUANTIFICATION_DIR:-${PROJECT_DIR}/050-quantification}"
export BATCH_DIR="${BATCH_DIR:-${PROJECT_DIR}/055-batch-correction}"
export DEG_DIR="${DEG_DIR:-${PROJECT_DIR}/060-deg-analysis}"
export GENE_REPORT_DIR="${GENE_REPORT_DIR:-${PROJECT_DIR}/090-search-gene}"
export ENVS_DIR="${ENVS_DIR:-${PROJECT_DIR}/envs}"

# Active executables live in scripts/. The numbered directories above remain
# the user-facing work/result areas for each step.
export SCRIPTS_DIR="${SCRIPTS_DIR:-${PROJECT_DIR}/scripts}"
export REF_SCRIPTS_DIR="${REF_SCRIPTS_DIR:-${SCRIPTS_DIR}/010-reference}"
export DOWNLOAD_SCRIPTS_DIR="${DOWNLOAD_SCRIPTS_DIR:-${SCRIPTS_DIR}/020-data-download}"
export PARSE_SCRIPTS_DIR="${PARSE_SCRIPTS_DIR:-${SCRIPTS_DIR}/025-parse}"
export QC_SCRIPTS_DIR="${QC_SCRIPTS_DIR:-${SCRIPTS_DIR}/030-qc-fastq}"
export ALIGN_SCRIPTS_DIR="${ALIGN_SCRIPTS_DIR:-${SCRIPTS_DIR}/040-alignment}"
export QUANT_SCRIPTS_DIR="${QUANT_SCRIPTS_DIR:-${SCRIPTS_DIR}/050-quantification}"
export BATCH_SCRIPTS_DIR="${BATCH_SCRIPTS_DIR:-${SCRIPTS_DIR}/055-batch-correction}"
export DEG_SCRIPTS_DIR="${DEG_SCRIPTS_DIR:-${SCRIPTS_DIR}/060-deg-analysis}"
export GENE_REPORT_SCRIPTS_DIR="${GENE_REPORT_SCRIPTS_DIR:-${SCRIPTS_DIR}/090-search-gene}"

export REF_DATA_DIR="${REF_DATA_DIR:-${REF_DIR}/data}"
export REF_LOG_DIR="${REF_LOG_DIR:-${REF_DIR}/logs}"
export DATASET_CONFIG_DIR="${DATASET_CONFIG_DIR:-${DOWNLOAD_DIR}/datasets}"

# Scratch/work area on the remote Slurm server. FASTQs are expected under
#   <SCRATCH_ROOT>/<PROJECT>/fastq_ftp
export SCRATCH_ROOT="${SCRATCH_ROOT:-${PROJECT_DIR}/work/scratch}"

export METADATA_INTERMEDIATE_DIR="${METADATA_INTERMEDIATE_DIR:-${PARSE_DIR}/015-intermediate_folder}"
export METADATA_PARSER_DIR="${METADATA_PARSER_DIR:-${PARSE_DIR}/020-metadata_parsers}"
export METADATA_PARSED_DIR="${METADATA_PARSED_DIR:-${METADATA_PARSER_DIR}/Allprojects}"
export METADATA_FINAL_DIR="${METADATA_FINAL_DIR:-${PARSE_DIR}/030-metadata_final}"
export METADATA_FINAL="${METADATA_FINAL:-${METADATA_FINAL_DIR}/AllProjects_metadata.csv}"
export METADATA_FINAL_NEW="${METADATA_FINAL_NEW:-${METADATA_FINAL_DIR}/AllProjects_metadata_new.csv}"

export QUANT_DIR="${QUANT_DIR:-${ALIGN_DIR}/quants}"
export QUANT_METHOD="${QUANT_METHOD:-salmon}"
export QUANT_METHOD="${QUANT_METHOD,,}"
export STAR_QUANT_DIR="${STAR_QUANT_DIR:-${ALIGN_DIR}/star_quant}"

# ---------------------------------------------------------------------------
# Reference inputs
# ---------------------------------------------------------------------------
# Either provide URLs, local files, or both. URL downloads are skipped when the
# corresponding local uncompressed file already exists.
export GENOME_URL="${GENOME_URL:-}"
export TRANSCRIPTS_URL="${TRANSCRIPTS_URL:-}"
export GFF3_URL="${GFF3_URL:-}"
export GTF_URL="${GTF_URL:-}"

export GENOME_FA_GZ="${GENOME_FA_GZ:-${GENOME_URL##*/}}"
export TRANSCRIPTS_FA_GZ="${TRANSCRIPTS_FA_GZ:-${TRANSCRIPTS_URL##*/}}"
export GFF3_GZ="${GFF3_GZ:-${GFF3_URL##*/}}"
export GTF_GZ="${GTF_GZ:-${GTF_URL##*/}}"

export GENOME_FA="${GENOME_FA:-${GENOME_FA_GZ%.gz}}"
export TRANSCRIPTS_FA="${TRANSCRIPTS_FA:-${TRANSCRIPTS_FA_GZ%.gz}}"
export GFF3="${GFF3:-${GFF3_GZ%.gz}}"
export GTF="${GTF:-${GTF_GZ%.gz}}"

if [[ -n "$GENOME_FA" ]]; then
    export REF_GENOME_FA="${REF_GENOME_FA:-${REF_DATA_DIR}/${GENOME_FA}}"
else
    export REF_GENOME_FA="${REF_GENOME_FA:-}"
fi
if [[ -n "$TRANSCRIPTS_FA" ]]; then
    export REF_TRANSCRIPTS_FA="${REF_TRANSCRIPTS_FA:-${REF_DATA_DIR}/${TRANSCRIPTS_FA}}"
else
    export REF_TRANSCRIPTS_FA="${REF_TRANSCRIPTS_FA:-}"
fi
if [[ -n "$GFF3" ]]; then
    export REF_GFF3="${REF_GFF3:-${REF_DATA_DIR}/${GFF3}}"
else
    export REF_GFF3="${REF_GFF3:-}"
fi
if [[ -n "$GTF" ]]; then
    export REF_GTF="${REF_GTF:-${REF_DATA_DIR}/${GTF}}"
else
    export REF_GTF="${REF_GTF:-}"
fi
if [[ -n "${REF_GFF3}" ]]; then
    export GENE_REPORT_ANNOTATION_FILE="${GENE_REPORT_ANNOTATION_FILE:-${REF_GFF3}}"
else
    export GENE_REPORT_ANNOTATION_FILE="${GENE_REPORT_ANNOTATION_FILE:-${REF_GTF}}"
fi

export SALMON_INDEX_DIR="${SALMON_INDEX_DIR:-${REF_DIR}/salmon_index}"
export STAR_INDEX_DIR="${STAR_INDEX_DIR:-${REF_DIR}/star_index}"
export STAR_INDEX_GTF_DIR="${STAR_INDEX_GTF_DIR:-${REF_DIR}/star_index_gtf}"
export STAR_QUANT_INDEX_DIR="${STAR_QUANT_INDEX_DIR:-${STAR_INDEX_GTF_DIR}}"

export SALMON_KMER_SIZE="${SALMON_KMER_SIZE:-31}"
export STAR_GENOME_SA_INDEX_NBASES="${STAR_GENOME_SA_INDEX_NBASES:-12}"
export STAR_GTF_GENOME_SA_INDEX_NBASES="${STAR_GTF_GENOME_SA_INDEX_NBASES:-10}"
export STAR_LIMIT_GENOME_GENERATE_RAM="${STAR_LIMIT_GENOME_GENERATE_RAM:-170000000000}"
export STAR_GENECOUNT_COLUMN="${STAR_GENECOUNT_COLUMN:-unstranded}"
export STAR_GENECOUNT_COLUMN="${STAR_GENECOUNT_COLUMN,,}"
export STAR_READ_FILES_COMMAND="${STAR_READ_FILES_COMMAND:-zcat}"
export STAR_EXTRA_ARGS="${STAR_EXTRA_ARGS:-}"

if [[ "${QUANT_METHOD}" == "star" ]]; then
    export EXPRESSION_MATRIX_FILE="${EXPRESSION_MATRIX_FILE:-${QUANTIFICATION_DIR}/star_cpm_matrix.tsv}"
    export EXPRESSION_UNIT="${EXPRESSION_UNIT:-CPM}"
else
    export EXPRESSION_MATRIX_FILE="${EXPRESSION_MATRIX_FILE:-${QUANTIFICATION_DIR}/tpm_matrix.tsv}"
    export EXPRESSION_UNIT="${EXPRESSION_UNIT:-TPM}"
fi

# ---------------------------------------------------------------------------
# Resources and pipeline defaults
# ---------------------------------------------------------------------------
export THREADS="${SLURM_CPUS_PER_TASK:-${THREADS:-8}}"
export MEMORY="${SLURM_MEM:-${MEMORY:-32G}}"
export DOWNLOAD_THREADS="${DOWNLOAD_THREADS:-8}"
export QC_RUN_CONCURRENCY="${QC_RUN_CONCURRENCY:-10}"
export QC_SAMPLE_CONCURRENCY="${QC_SAMPLE_CONCURRENCY:-10}"
export SALMON_CONCURRENCY="${SALMON_CONCURRENCY:-10}"
export STAR_QUANT_CONCURRENCY="${STAR_QUANT_CONCURRENCY:-2}"
export DEG_CONCURRENCY="${DEG_CONCURRENCY:-2}"
export PIPELINE_EXECUTOR="${PIPELINE_EXECUTOR:-slurm}"
export LOCAL_CPUS_PER_TASK="${LOCAL_CPUS_PER_TASK:-$THREADS}"
export RUN_STAR_INDEX="${RUN_STAR_INDEX:-0}"
if [[ "${QUANT_METHOD}" == "star" ]]; then
    export RUN_SALMON_INDEX="${RUN_SALMON_INDEX:-0}"
    export RUN_STAR_GTF_INDEX="${RUN_STAR_GTF_INDEX:-1}"
else
    export RUN_SALMON_INDEX="${RUN_SALMON_INDEX:-1}"
    export RUN_STAR_GTF_INDEX="${RUN_STAR_GTF_INDEX:-0}"
fi
export RUN_BATCH_CORRECTION="${RUN_BATCH_CORRECTION:-0}"
export RUN_GENE_REPORT="${RUN_GENE_REPORT:-0}"
export PIPELINE_WAIT_FOR_CHILD_JOBS="${PIPELINE_WAIT_FOR_CHILD_JOBS:-1}"

export FASTQ_LAYOUT="${FASTQ_LAYOUT:-paired}"
export TRIM_QUALITY="${TRIM_QUALITY:-20}"
export TRIM_LENGTH="${TRIM_LENGTH:-20}"

export BATCH_COLUMN="${BATCH_COLUMN:-dataset}"
export BATCH_COVARIATES="${BATCH_COVARIATES:-}"
export DEG_TEST_VARIABLES="${DEG_TEST_VARIABLES:-condition,stage,sex,tissue,infection_mode}"
export DEG_DESIGN_COVARIATES="${DEG_DESIGN_COVARIATES:-}"
export GENE_REPORT_TITLE="${GENE_REPORT_TITLE:-Candidate gene report}"

# Generic defaults used by 090-search-gene. Projects with organism-specific
# life-cycle vocabularies can override these values here.
export LIFE_STAGE_LEVELS="${LIFE_STAGE_LEVELS:-unknown}"
export STAGE_SYNONYM_MAP="${STAGE_SYNONYM_MAP:-}"
export ORGANISM_SPECIFIC_REPORTS="${ORGANISM_SPECIFIC_REPORTS:-0}"

# ---------------------------------------------------------------------------
# Conda environments
# ---------------------------------------------------------------------------
if command -v conda >/dev/null 2>&1; then
    export CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
else
    export CONDA_BASE="${CONDA_BASE:-}"
fi

export RNA_TOOLS_ENV="${RNA_TOOLS_ENV:-rna-tools}"
export R_ANALYSIS_ENV="${R_ANALYSIS_ENV:-r-analysis}"
export PYTHON_ENV="${PYTHON_ENV:-python-list}"
export BATCH_CORRECTION_ENV="${BATCH_CORRECTION_ENV:-batch-correction}"

pipeline_projects() {
    local projects="${PIPELINE_PROJECTS//,/ }"
    for project in $projects; do
        [[ -n "$project" ]] && printf '%s\n' "$project"
    done
}

require_pipeline_projects() {
    if [[ -z "${PIPELINE_PROJECTS//,/ }" ]]; then
        echo "[ERRO] Defina PIPELINE_PROJECTS em config/pipeline_config.sh." >&2
        exit 1
    fi
}

metadata_default() {
    if [[ -n "${METADATA_FINAL_NEW:-}" && -f "$METADATA_FINAL_NEW" ]]; then
        echo "$METADATA_FINAL_NEW"
    else
        echo "$METADATA_FINAL"
    fi
}

activate_conda_env() {
    local env_name="$1"
    if [[ -z "${CONDA_BASE:-}" || ! -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]]; then
        echo "[ERRO] Conda nao encontrado. Ajuste CONDA_BASE em config/pipeline_config.sh." >&2
        exit 1
    fi
    # shellcheck disable=SC1090
    source "${CONDA_BASE}/etc/profile.d/conda.sh"
    conda activate "$env_name"
}

activate_rna_tools() {
    activate_conda_env "$RNA_TOOLS_ENV"
}

activate_python_env() {
    activate_conda_env "$PYTHON_ENV"
}

activate_r_analysis() {
    activate_conda_env "$R_ANALYSIS_ENV"
}

activate_batch_correction() {
    activate_conda_env "$BATCH_CORRECTION_ENV"
}

check_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[ERRO] Comando '$cmd' nao encontrado no ambiente ativo." >&2
        exit 1
    fi
}

require_file() {
    local path="$1"
    local label="${2:-arquivo}"
    if [[ ! -f "$path" ]]; then
        echo "[ERRO] ${label} nao encontrado: $path" >&2
        exit 1
    fi
}

require_dir() {
    local path="$1"
    local label="${2:-diretorio}"
    if [[ ! -d "$path" ]]; then
        echo "[ERRO] ${label} nao encontrado: $path" >&2
        exit 1
    fi
}

download_if_needed() {
    local url="$1"
    local output="$2"
    if [[ -z "$url" ]]; then
        return 0
    fi
    if [[ -s "$output" ]]; then
        echo "[INFO] Ja existe: $output"
        return 0
    fi
    mkdir -p "$(dirname "$output")"
    echo "[INFO] Baixando $url"
    wget -O "$output" "$url"
}

decompress_gzip_if_needed() {
    local gz_path="$1"
    local out_path="${2:-${gz_path%.gz}}"
    if [[ -s "$out_path" ]]; then
        echo "[INFO] Ja existe: $out_path"
        return 0
    fi
    require_file "$gz_path" "arquivo compactado"
    echo "[INFO] Descompactando $gz_path"
    gzip -dc "$gz_path" > "$out_path"
}

submit_sbatch() {
    local output job_id
    echo "+ sbatch $*" >&2
    output=$(sbatch "$@")
    echo "$output" >&2
    job_id=$(echo "$output" | tail -n 1 | awk '{print $NF}' | cut -d';' -f1)
    if [[ ! "$job_id" =~ ^[0-9]+([._][0-9]+)?$ ]]; then
        echo "[ERRO] Nao foi possivel extrair job id de: $output" >&2
        exit 1
    fi
    echo "$job_id"
}

run_local_array() {
    local label="$1"
    local total="$2"
    shift 2

    if ! [[ "$total" =~ ^[0-9]+$ ]] || [[ "$total" -lt 1 ]]; then
        echo "[ERRO] Total invalido para array local ${label}: ${total}" >&2
        exit 1
    fi

    local task_id
    for ((task_id = 1; task_id <= total; task_id++)); do
        echo "[INFO] Local ${label}: tarefa ${task_id}/${total}"
        SLURM_ARRAY_TASK_ID="$task_id" \
        SLURM_CPUS_PER_TASK="${SLURM_CPUS_PER_TASK:-$LOCAL_CPUS_PER_TASK}" \
        PIPELINE_EXECUTOR="local" \
        bash "$@"
    done
}

wait_for_slurm_jobs() {
    if [[ "${PIPELINE_WAIT_FOR_CHILD_JOBS:-1}" -ne 1 ]]; then
        return 0
    fi
    if ! command -v squeue >/dev/null 2>&1; then
        echo "[WARN] squeue nao encontrado; nao sera possivel aguardar jobs filhos." >&2
        return 0
    fi
    local jobs=("$@")
    local remaining
    while true; do
        remaining=0
        for job in "${jobs[@]}"; do
            [[ -z "$job" || "$job" == "DRYRUN_JOB" || "$job" == "DRYRUN" ]] && continue
            if squeue -h -j "$job" | grep -q .; then
                remaining=1
                break
            fi
        done
        [[ "$remaining" -eq 0 ]] && break
        sleep 60
    done
}
