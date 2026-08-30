#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?ChIP-seq runtime prefix is required}
java_home=${4:?Java 21 home is required}
nextflow_launcher=${5:?Nextflow 25.10.7 launcher is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "The preflight must run in a Slurm allocation." >&2
    exit 2
}

"$runtime_prefix/bin/python" \
    "$repo_root/benchmark/chipseq/scripts/collect_real_broad_preflight.py" \
    --repo "$repo_root" \
    --scratch /scratch/Schisto-epigenetics/gustavo \
    --home /home/ra236875@bio.ib.unicamp.br \
    --runtime "$runtime_prefix" \
    --java-home "$java_home" \
    --nextflow "$nextflow_launcher" \
    --output "$benchmark_root/preflight/environment.json"
