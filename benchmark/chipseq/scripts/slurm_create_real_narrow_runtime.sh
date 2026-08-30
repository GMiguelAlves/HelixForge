#!/usr/bin/env bash

set -euo pipefail

environment_file=${1:?frozen environment file is required}
runtime_prefix=${2:?runtime prefix is required}
conda_binary=${3:?Conda executable is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "The frozen runtime must be created in a Slurm allocation." >&2
    exit 2
}

runtime_prefix=$(realpath -m "$runtime_prefix")
expected_prefix=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830/runtime/chipseq-frozen
[[ "$runtime_prefix" == "$expected_prefix" ]] || {
    echo "Refusing unexpected runtime prefix: $runtime_prefix" >&2
    exit 2
}

[[ ! -e "$runtime_prefix" ]] || {
    echo "Refusing to modify an existing runtime: $runtime_prefix" >&2
    exit 2
}

"$conda_binary" env create \
    --prefix "$runtime_prefix" \
    --file "$environment_file"

"$conda_binary" list --prefix "$runtime_prefix" --explicit \
    > "${runtime_prefix}.explicit.txt"

printf 'RUNTIME_READY\n' > "${runtime_prefix}.status"
