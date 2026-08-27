#!/usr/bin/env bash
set -euo pipefail

conda_bin=${1:?conda executable is required}
environment_file=${2:?environment file is required}
prefix=${3:?environment prefix is required}
provenance_dir=${4:?provenance directory is required}
test -n "${SLURM_JOB_ID:-}"
test -x "$conda_bin"
test -f "$environment_file"
test ! -e "$prefix"

mkdir -p "$(dirname "$prefix")" "$provenance_dir"
start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$conda_bin" env create --prefix "$prefix" --file "$environment_file" --yes
"$conda_bin" list --prefix "$prefix" --explicit > "$provenance_dir/explicit.txt"
"$conda_bin" list --prefix "$prefix" --json > "$provenance_dir/packages.json"
sha256sum "$environment_file" > "$provenance_dir/environment.sha256"
end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"status":"complete","slurm_job_id":"%s","node":"%s","started_utc":"%s","ended_utc":"%s","prefix":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$start" "$end" "$prefix" > "$provenance_dir/creation.json"
