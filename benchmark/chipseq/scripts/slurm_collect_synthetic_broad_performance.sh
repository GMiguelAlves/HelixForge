#!/usr/bin/env bash

set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen ChIP runtime is required}
slurm_user=${4:?Slurm account user is required}
start_date=${5:?accounting start date is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Synthetic broad performance collection must run under Slurm." >&2
    exit 2
}
output_root="$benchmark_root/performance"
[[ ! -e "$output_root" ]] || {
    echo "Refusing to overwrite broad performance output: $output_root" >&2
    exit 2
}
export PATH="$runtime_prefix/bin:/usr/bin:/bin"
mkdir -p "$output_root"

sacct -S "$start_date" -u "$slurm_user" -n -P --units=K \
    --format=JobIDRaw,JobName,State,ExitCode,ElapsedRaw,MaxRSS,AllocCPUS,NodeList \
    > "$output_root/slurm_accounting.psv"

python "$repo_root/benchmark/chipseq/scripts/collect_synthetic_narrow_performance.py" \
    --benchmark-kind broad \
    --trace "helixforge=$benchmark_root/helixforge/trace.tsv" \
    --sacct "$output_root/slurm_accounting.psv" \
    --storage "dataset=$benchmark_root/dataset" \
    --storage "helixforge=$benchmark_root/helixforge" \
    --storage "independent=$benchmark_root/independent" \
    --storage "evaluation=$benchmark_root/evaluation" \
    --output-json "$output_root/performance_summary.json" \
    --output-tsv "$output_root/process_performance.tsv"

sha256sum "$output_root/slurm_accounting.psv" "$output_root/performance_summary.json" \
    "$output_root/process_performance.tsv" > "$output_root/checksums.sha256"

