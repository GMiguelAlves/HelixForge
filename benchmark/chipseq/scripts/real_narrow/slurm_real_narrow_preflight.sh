#!/usr/bin/env bash

set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}
idr_prefix=${4:?IDR runtime prefix is required}
java_home=${5:?Java home is required}
r_binary=${6:?R executable is required}
nextflow_launcher=${7:?Nextflow launcher is required}
git_binary=${8:?Git executable is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "The preflight must run in a Slurm allocation." >&2
    exit 2
}

"$runtime_prefix/bin/python" \
    "$repo_root/benchmark/chipseq/scripts/real_narrow/collect_real_narrow_preflight.py" \
    --repo "$repo_root" \
    --scratch /scratch/Schisto-epigenetics/gustavo \
    --home /home/ra236875@bio.ib.unicamp.br \
    --runtime "$runtime_prefix" \
    --idr "$idr_prefix" \
    --java-home "$java_home" \
    --r-bin "$r_binary" \
    --nextflow "$nextflow_launcher" \
    --git "$git_binary" \
    --output "$benchmark_root/preflight/preflight.json"
