#!/usr/bin/env bash
set -euo pipefail

target_prefix=${1:?partial runtime prefix is required}
expected=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830/runtime/chipseq-frozen

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Runtime cleanup must run in a Slurm allocation." >&2
    exit 2
}
[[ "$target_prefix" == "$expected" ]]
[[ -d "$target_prefix" ]]
[[ ! -f "$target_prefix/conda-meta/history" ]]

rm -rf -- "$target_prefix"
[[ ! -e "$target_prefix" ]]
echo "Removed incomplete benchmark runtime: $target_prefix"
