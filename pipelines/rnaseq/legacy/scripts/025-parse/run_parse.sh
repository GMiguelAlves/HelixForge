#!/usr/bin/env bash
#SBATCH --job-name=parse_metadata
#SBATCH --output=logs/parse/%x_%A.out
#SBATCH --error=logs/parse/%x_%A.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00

set -euo pipefail

if [[ $# -eq 0 ]]; then
    echo "Uso: sbatch $0 <PROJECT>"
    exit 1
fi

PROJ="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck disable=SC1091
source "${PIPELINE_CONFIG:-${PROJECT_DIR}/config/pipeline_config.sh}"

mkdir -p "${PARSE_DIR}/logs/parse" "$METADATA_PARSED_DIR" "$METADATA_INTERMEDIATE_DIR"
cd "$PARSE_DIR"

activate_python_env
check_command metaqc

BASE_FILE="${METADATA_INTERMEDIATE_DIR}/${PROJ}_base.csv"
ENRICHED_FILE="${METADATA_INTERMEDIATE_DIR}/${PROJ}_enriched.csv"
PROJECT_PARSE_DIR="${METADATA_PARSER_DIR}/${PROJ}"
PARSE_CONFIG="${PROJECT_PARSE_DIR}/configs/${PROJ}.yaml"
ENRICH_CONFIG="${PROJECT_PARSE_DIR}/configs/${PROJ}_enrich.yaml"
AUTHOR_METADATA="${PROJECT_PARSE_DIR}/author_metadata.tsv"
OUTPUT_FILE="${METADATA_PARSED_DIR}/${PROJ}_parsed.csv"

require_file "$BASE_FILE" "metadata base"
require_file "$PARSE_CONFIG" "YAML de parse"

INPUT_FILE="$BASE_FILE"
if [[ -f "$ENRICH_CONFIG" ]]; then
    require_file "$AUTHOR_METADATA" "metadata de autor para enrich"
    echo "[INFO] Rodando metaqc enrich: $PROJ"
    metaqc enrich "$BASE_FILE" "$AUTHOR_METADATA" "$ENRICH_CONFIG" --output "$ENRICHED_FILE"
    INPUT_FILE="$ENRICHED_FILE"
else
    echo "[INFO] Sem enrich config para $PROJ"
fi

echo "[INFO] Rodando metaqc parse: $PROJ"
metaqc parse "$INPUT_FILE" --config "$PARSE_CONFIG" --output "$OUTPUT_FILE"
echo "[OK] Parsed metadata: $OUTPUT_FILE"
