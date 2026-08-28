#!/usr/bin/env bash

set -euo pipefail

conda_binary=${1:?Conda executable is required}
environment_prefix=${2:?toolchain environment prefix is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "The ChIPs toolchain must be prepared in a Slurm allocation." >&2
    exit 2
}
[[ ! -e "$environment_prefix" ]] || {
    echo "Refusing to overwrite existing toolchain: $environment_prefix" >&2
    exit 2
}

"$conda_binary" create --yes --override-channels --channel conda-forge \
    --prefix "$environment_prefix" \
    gxx_linux-64=12 cmake=3.31.8 make=4.4.1 git

"$conda_binary" list --explicit --prefix "$environment_prefix" \
    > "$environment_prefix/conda-explicit.txt"
"$environment_prefix/bin/x86_64-conda-linux-gnu-c++" --version \
    > "$environment_prefix/compiler-version.txt"

