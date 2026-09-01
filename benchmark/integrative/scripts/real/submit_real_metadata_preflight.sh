#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
scratch_root=${2:?dedicated scratch root is required}
python_bin=${3:-python3}
case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-*) ;;
    *) echo "unsafe scratch root: $scratch_root" >&2; exit 2 ;;
esac
test -d "$repo_root/.git"
test ! -e "$scratch_root"
mkdir -p "$scratch_root/logs"

state="$scratch_root/benchmark_state.json"
updater="$repo_root/benchmark/integrative/scripts/real/update_real_benchmark_state.py"
worker="$repo_root/benchmark/integrative/scripts/real/slurm_real_metadata_preflight.sh"
session_uuid=$($python_bin -c 'import uuid; print(uuid.uuid4())')
repo_commit=$(git -C "$repo_root" rev-parse HEAD)
export HF_STATE_TIME_UTC
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$state" \
    --phase METADATA_PREFLIGHT_PREPARED --status PREPARED \
    --session-uuid "$session_uuid" --repo-commit "$repo_commit" \
    --workdir "$scratch_root" \
    --expected-output metadata/dataset_metadata.tsv \
    --expected-output metadata/download_manifest.tsv \
    --expected-output metadata/metadata_validation.json \
    --expected-output metadata/storage_plan.json

job_id=$(sbatch --parsable \
    --job-name=hf-int-real-meta \
    --cpus-per-task=1 --mem=2G --time=00:30:00 \
    --output="$scratch_root/logs/metadata-%j.out" \
    --error="$scratch_root/logs/metadata-%j.err" \
    --export="ALL,HF_REPO_ROOT=$repo_root,HF_SCRATCH_ROOT=$scratch_root,HF_PYTHON_BIN=$python_bin" \
    "$worker")
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$state" \
    --phase METADATA_PREFLIGHT_SUBMITTED --status SUBMITTED \
    --session-uuid "$session_uuid" --repo-commit "$repo_commit" \
    --job-id "$job_id" --workdir "$scratch_root"
printf 'JOB_ID=%s\nSESSION_UUID=%s\nSTATE=%s\n' "$job_id" "$session_uuid" "$state"
