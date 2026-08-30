#!/usr/bin/env bash
set -euo pipefail

source_prefix=${1:?source Conda environment is required}
target_prefix=${2:?target runtime prefix is required}
conda_binary=${3:?Conda executable is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Runtime relocation must run in a Slurm allocation." >&2
    exit 2
}
[[ "$target_prefix" == /scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830/runtime/chipseq-frozen ]]
[[ -d "$source_prefix" ]]
[[ ! -e "$target_prefix" ]]

mkdir -p "$(dirname "$target_prefix")"
"$conda_binary" create --yes --clone "$source_prefix" --prefix "$target_prefix"

"$target_prefix/bin/python" --version
"$target_prefix/bin/bowtie2" --version | head -1
"$target_prefix/bin/samtools" --version | head -1
"$target_prefix/bin/macs3" --version
"$target_prefix/bin/fastqc" --version
"$target_prefix/bin/multiqc" --version
"$target_prefix/bin/bedtools" --version
"$target_prefix/bin/R" --version | head -1
