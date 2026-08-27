#!/usr/bin/env bash
set -euo pipefail

source_file=${1:?versioned candidate-gene source is required}
target_file=${2:?prepared case candidate-gene file is required}
output=${3:?audit manifest is required}
expected_old_sha256=dd52355b75f0e6cb60f00a9b34f719b980568d013e38149a3911c2305f7d2556

test -n "${SLURM_JOB_ID:-}"
test -s "$source_file"
test -s "$target_file"
observed_old_sha256=$(sha256sum "$target_file" | awk '{print $1}')
[[ "$observed_old_sha256" == "$expected_old_sha256" ]]
grep -Fxq 'Glucocorticoid_response: CRISPLD2,DUSP1,KLF15,PER1,TSC22D3' "$source_file"
grep -Fxq 'Reference_controls: B2M,GABARAP,GAPDH,RPL19' "$source_file"

cp "$source_file" "${target_file}.nextflow.tmp"
mv "${target_file}.nextflow.tmp" "$target_file"
new_sha256=$(sha256sum "$target_file" | awk '{print $1}')
printf '{"status":"complete","slurm_job_id":"%s","node":"%s","target":"%s","old_sha256":"%s","new_sha256":"%s","groups":2,"queries":9}\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$target_file" "$observed_old_sha256" "$new_sha256" > "$output"
