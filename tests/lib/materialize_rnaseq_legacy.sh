#!/usr/bin/env bash

set -euo pipefail

materialize_rnaseq_legacy() {
    local repository_root=${1:?repository root is required}
    local relative_path=${2:?legacy relative path is required}
    local destination=${3:?destination is required}
    local reference=${HELIXFORGE_RNASEQ_LEGACY_REF:-rnaseq-legacy-v1.0.0}
    local object="${reference}:pipelines/rnaseq/legacy/${relative_path}"

    mkdir -p "$(dirname "$destination")"
    if ! git -C "$repository_root" cat-file -e "$object" 2>/dev/null; then
        echo "[ERROR] RNA-seq legacy reference is unavailable: ${object}" >&2
        echo "Fetch the release tag or set HELIXFORGE_RNASEQ_LEGACY_REF to an equivalent archived revision." >&2
        return 2
    fi
    git -C "$repository_root" show "$object" > "$destination"
}
