#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}
expected=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Reference preparation must run in a Slurm allocation." >&2
    exit 2
}
[[ "$(realpath -m "$benchmark_root")" == "$expected" ]]

manifest="$benchmark_root/reference/reference_manifest.json"
if [[ -s "$manifest" ]]; then
    "$runtime_prefix/bin/python" \
        "$repo_root/benchmark/chipseq/scripts/real_broad/prepare_real_broad_reference.py" \
        --manifest "$manifest" --validate-existing
    exit 0
fi

"$runtime_prefix/bin/python" \
    "$repo_root/benchmark/chipseq/scripts/real_broad/prepare_real_broad_reference.py" \
    --download-manifest "$benchmark_root/downloads/provenance/download_manifest.json" \
    --output-dir "$benchmark_root/reference" \
    --samtools "$runtime_prefix/bin/samtools" \
    --manifest "$manifest"
