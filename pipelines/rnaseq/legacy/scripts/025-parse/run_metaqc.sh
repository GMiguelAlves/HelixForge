#!/usr/bin/env bash
#SBATCH --job-name=metaqc
#SBATCH --output=logs/metaqc_%A_%a.out
#SBATCH --error=logs/err/metaqc_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=03:00:00

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck disable=SC1091
source "${PIPELINE_CONFIG:-${PROJECT_DIR}/config/pipeline_config.sh}"

PROJECT="${1:-}"
if [[ -z "$PROJECT" ]]; then
    require_pipeline_projects
fi

RAW_METADATA_DIR="${PARSE_DIR}/010-raw_metadata"
mkdir -p "${PARSE_DIR}/logs/err" "$METADATA_INTERMEDIATE_DIR" "$RAW_METADATA_DIR"
cd "$PARSE_DIR"

activate_python_env
check_command wget
check_command metaqc

run_project() {
    local project="$1"
    local raw_tsv="${RAW_METADATA_DIR}/${project}.tsv"
    local base_csv="${METADATA_INTERMEDIATE_DIR}/${project}_base.csv"
    local ena_url

    ena_url="https://www.ebi.ac.uk/ena/portal/api/filereport?accession=${project}&result=${ENA_RESULT}&fields=${ENA_FIELDS}&format=tsv&download=true&limit=0"

    echo "[INFO] Baixando metadata ENA: $project"
    wget -O "$raw_tsv" "$ena_url"

    local cmd=(metaqc validate "$raw_tsv" --output "$base_csv")
    if [[ -n "$METAQC_KEEP_COLUMNS" ]]; then
        cmd+=(--keep "$METAQC_KEEP_COLUMNS")
    fi
    if [[ -n "$METADATA_SCHEMA_FILE" ]]; then
        cmd+=(--schema-file "$METADATA_SCHEMA_FILE")
    fi

    echo "+ ${cmd[*]}"
    "${cmd[@]}"
    rm -f validation_report.txt
    echo "[OK] Metadata base: $base_csv"
}

if [[ -n "$PROJECT" ]]; then
    run_project "$PROJECT"
else
    while read -r project; do
        run_project "$project"
    done < <(pipeline_projects)
fi
