#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
repo_commit=$(git -C "$repo" rev-parse HEAD)
test -s "$root/reference/reference_manifest.json"
test -s "$root/reference/sources/gencode.v50.transcripts.fa.gz"
test ! -e "$root/reference/transcriptome_normalization.json"
job_id=$(sbatch --parsable "$repo/benchmark/integrative/scripts/real/slurm_normalize_gse133183_transcriptome.sh" \
    "$repo" "$root" "$repo_commit")
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
    python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
    --state "$root/benchmark_state.json" --phase RNASEQ_REFERENCE_FIX_SUBMITTED --status SUBMITTED \
    --job-id "$job_id" --job-kind rnaseq_reference_correction --repo-commit "$repo_commit" \
    --expected-output reference/transcriptome_normalization.json
printf '%s\n' "$job_id"
