#!/usr/bin/env bash

set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Real Narrow evaluation must run in a Slurm allocation." >&2
    exit 2
}
expected_root=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830
[[ "$(realpath -m "$benchmark_root")" == "$expected_root" ]] || {
    echo "Refusing unexpected benchmark root: $benchmark_root" >&2
    exit 2
}

"$runtime_prefix/bin/python" \
    "$repo_root/benchmark/chipseq/scripts/evaluate_real_narrow.py" \
    --benchmark-root "$benchmark_root" \
    --output-dir "$benchmark_root/evaluation"
