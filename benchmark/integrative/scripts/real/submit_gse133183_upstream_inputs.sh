#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
attempt=${3:-initial}
test -d "$repo/.git"
test -s "$root/reference/reference_manifest.json"
test ! -e "$root/cases"
mkdir -p "$root/logs"
repo_commit=$(git -C "$repo" rev-parse HEAD)
if [[ "$attempt" == retry ]]; then
    phase=UPSTREAM_INPUTS_RETRY_SUBMITTED
else
    phase=UPSTREAM_INPUTS_SUBMITTED
fi
job_id=$(sbatch --parsable "$repo/benchmark/integrative/scripts/real/slurm_prepare_gse133183_upstream_inputs.sh" "$repo" "$root" "$repo_commit" "$attempt")
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
    python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
    --state "$root/benchmark_state.json" --phase "$phase" --status SUBMITTED \
    --job-id "$job_id" --job-kind upstream_input_preparation --repo-commit "$repo_commit" \
    --workdir "$root/cases" --expected-output cases/cases_manifest.json
printf '%s\n' "$job_id"
