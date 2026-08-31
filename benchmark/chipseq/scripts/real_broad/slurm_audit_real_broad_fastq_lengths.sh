#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen runtime prefix is required}
expected=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "FASTQ auditing must run in a Slurm allocation." >&2
    exit 2
}
[[ "$(realpath -m "$benchmark_root")" == "$expected" ]]

"$runtime_prefix/bin/python" \
    "$repo_root/benchmark/chipseq/scripts/real_broad/audit_real_broad_fastq_lengths.py" \
    --samples "$repo_root/benchmark/chipseq/datasets/real_broad_samples.tsv" \
    --download-root "$benchmark_root/downloads" \
    --output "$benchmark_root/downloads/provenance/fastq_length_audit.json"
