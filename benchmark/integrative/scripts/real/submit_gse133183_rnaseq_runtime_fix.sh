#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
repo_commit=$(git -C "$repo" rev-parse HEAD)
test -s "$root/cases/rnaseq/user_settings.sh"
test ! -e "$root/cases/rnaseq/runtime_correction.json"
job_id=$(sbatch --parsable "$repo/benchmark/integrative/scripts/real/slurm_correct_gse133183_rnaseq_runtime.sh" \
    "$repo" "$root" "$repo_commit")
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
    python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
    --state "$root/benchmark_state.json" --phase RNASEQ_RUNTIME_FIX_SUBMITTED --status SUBMITTED \
    --job-id "$job_id" --job-kind rnaseq_runtime_correction --repo-commit "$repo_commit" \
    --expected-output cases/rnaseq/runtime_correction.json
printf '%s\n' "$job_id"
