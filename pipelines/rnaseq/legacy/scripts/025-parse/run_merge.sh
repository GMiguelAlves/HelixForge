#!/usr/bin/env bash
#SBATCH --job-name=merge_meta
#SBATCH --output=logs/%x_%A.out
#SBATCH --error=logs/%x_%A.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck disable=SC1091
source "${PIPELINE_CONFIG:-${PROJECT_DIR}/config/pipeline_config.sh}"

mkdir -p "${PARSE_DIR}/logs" "$METADATA_FINAL_DIR" "$METADATA_PARSED_DIR"
cd "$PARSE_DIR"

activate_python_env
check_command metaqc

echo "[INFO] Parsed metadata dir: $METADATA_PARSED_DIR"
echo "[INFO] Output: $METADATA_FINAL"

metaqc merge "$METADATA_PARSED_DIR" --output "$METADATA_FINAL"

if [[ "$METADATA_FINAL_NEW" != "$METADATA_FINAL" ]]; then
    cp "$METADATA_FINAL" "$METADATA_FINAL_NEW"
fi

echo "[OK] Merge concluido: $METADATA_FINAL"
