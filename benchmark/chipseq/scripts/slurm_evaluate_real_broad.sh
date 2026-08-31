#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}
expected=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830

[[ -n "${SLURM_JOB_ID:-}" ]] || { echo "Real Broad evaluation must run under Slurm." >&2; exit 2; }
[[ "$(realpath -m "$benchmark_root")" == "$expected" ]] || { echo "Unexpected benchmark root." >&2; exit 2; }

export PATH="$runtime_prefix/bin:/usr/bin:/bin"
"$runtime_prefix/bin/python" "$repo_root/benchmark/chipseq/scripts/evaluate_real_broad.py" \
    --repo-root "$repo_root" \
    --benchmark-root "$benchmark_root" \
    --output-dir "$benchmark_root/evaluation"
