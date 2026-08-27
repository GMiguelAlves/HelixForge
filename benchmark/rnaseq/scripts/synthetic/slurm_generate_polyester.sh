#!/usr/bin/env bash
set -euo pipefail

rscript=${1:?Rscript is required}
generator=${2:?generator script is required}
design=${3:?design is required}
reference=${4:?reference directory is required}
output=${5:?candidate output directory is required}
log=${6:?log path is required}
test -n "${SLURM_JOB_ID:-}"
test ! -e "$output"
mkdir -p "$(dirname "$output")" "$(dirname "$log")"

start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$rscript" "$generator" --design "$design" --reference-dir "$reference" --output-dir "$output" \
    > "$log" 2>&1
end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"status":"complete","slurm_job_id":"%s","node":"%s","started_utc":"%s","ended_utc":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$start" "$end" > "$output/generation_execution.json"
