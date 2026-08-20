#!/usr/bin/env bash

set -euo pipefail

project_root="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

required=(
    "pipelines/integrative/legacy/integrative_pipeline.sh"
    "pipelines/integrative/legacy/config/pipeline_config.sh"
    "pipelines/integrative/legacy/scripts/integrative_core.py"
    "pipelines/integrative/legacy/scripts/r/visualize_integrative.R"
)

missing=0
for relative in "${required[@]}"; do
    if [[ ! -f "${project_root}/${relative}" ]]; then
        echo "MISSING ${relative}" >&2
        missing=1
    fi
done

[[ "$missing" -eq 0 ]] || exit 1
printf 'Validated %d legacy entry points.\n' "${#required[@]}"
