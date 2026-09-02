#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
scratch_root=${2:?dedicated scratch root is required}
python_bin=${3:-python3}
samtools=${4:?samtools executable is required}
case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-*) ;;
    *) echo "unsafe scratch root: $scratch_root" >&2; exit 2 ;;
esac
test -d "$repo_root/.git"
test -s "$scratch_root/benchmark_state.json"
test ! -e "$scratch_root/reference/bundle"
test ! -e "$scratch_root/reference/reference_manifest.json"
test -x "$samtools"
updater="$repo_root/benchmark/integrative/scripts/real/update_real_benchmark_state.py"
repo_commit=$(git -C "$repo_root" rev-parse HEAD)
export HF_STATE_TIME_UTC
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$scratch_root/benchmark_state.json" \
    --phase REFERENCE_PREPARED --status PREPARED --repo-commit "$repo_commit" \
    --workdir "$scratch_root/reference" --expected-output reference/reference_manifest.json
job_id=$(sbatch --parsable --job-name=hf-int-real-ref --cpus-per-task=2 --mem=8G --time=04:00:00 \
    --output="$scratch_root/logs/reference-%j.out" --error="$scratch_root/logs/reference-%j.err" \
    --export="ALL,HF_REPO_ROOT=$repo_root,HF_SCRATCH_ROOT=$scratch_root,HF_PYTHON_BIN=$python_bin,HF_SAMTOOLS=$samtools" \
    "$repo_root/benchmark/integrative/scripts/real/slurm_prepare_gse133183_reference.sh")
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$scratch_root/benchmark_state.json" \
    --phase REFERENCE_SUBMITTED --status SUBMITTED --job-id "$job_id" \
    --job-kind reference_preparation --repo-commit "$repo_commit" --workdir "$scratch_root/reference"
printf 'JOB_ID=%s\nSTATE=%s\n' "$job_id" "$scratch_root/benchmark_state.json"
