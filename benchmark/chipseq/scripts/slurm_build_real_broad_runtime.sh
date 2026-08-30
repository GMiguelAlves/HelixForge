#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
target_prefix=${2:?target runtime prefix is required}
conda_binary=${3:?Conda executable is required}
expected=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830/runtime/chipseq-frozen

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Runtime construction must run in a Slurm allocation." >&2
    exit 2
}
[[ "$target_prefix" == "$expected" ]]
[[ ! -e "$target_prefix" ]]

mkdir -p "$(dirname "$target_prefix")"
"$conda_binary" env create --yes \
    --prefix "$target_prefix" \
    --file "$repo_root/benchmark/chipseq/configs/chipseq-frozen.environment.yml"

"$target_prefix/bin/python" --version
"$target_prefix/bin/bowtie2" --version
"$target_prefix/bin/samtools" --version
"$target_prefix/bin/macs3" --version
"$target_prefix/bin/fastqc" --version
"$target_prefix/bin/multiqc" --version
"$target_prefix/bin/bedtools" --version
