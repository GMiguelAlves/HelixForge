#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
test -d "$repo/.git"
test -s "$root/reference/reference_manifest.json"
test ! -e "$root/cases"
mkdir -p "$root/logs"
job_id=$(sbatch --parsable "$repo/benchmark/integrative/scripts/real/slurm_prepare_gse133183_upstream_inputs.sh" "$repo" "$root")
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
    python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
    --state "$root/benchmark_state.json" --phase UPSTREAM_INPUTS_SUBMITTED --status SUBMITTED \
    --job-id "$job_id" --job-kind upstream_input_preparation --repo-commit "$(git -C "$repo" rev-parse HEAD)" \
    --workdir "$root/cases" --expected-output cases/cases_manifest.json
printf '%s\n' "$job_id"
