#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen runtime prefix is required}
expected=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Metadata validation must run in a Slurm allocation." >&2
    exit 2
}
[[ "$(realpath -m "$benchmark_root")" == "$expected" ]]

"$runtime_prefix/bin/python" \
    "$repo_root/benchmark/chipseq/scripts/real_broad/collect_real_broad_metadata.py" \
    --samples "$repo_root/benchmark/chipseq/datasets/real_broad_samples.tsv" \
    --references "$repo_root/benchmark/chipseq/datasets/reference_sources.tsv" \
    --execution-config "$repo_root/benchmark/chipseq/configs/real_broad_execution.json" \
    --output-json "$benchmark_root/metadata/encode_metadata_snapshot.json" \
    --output-tsv "$benchmark_root/metadata/encode_files.tsv"
