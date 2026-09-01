#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
scratch_root=${2:?dedicated scratch root is required}
python_bin=${3:-python3}
max_concurrent=${4:-5}
case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-*) ;;
    *) echo "unsafe scratch root: $scratch_root" >&2; exit 2 ;;
esac
[[ "$max_concurrent" =~ ^[1-5]$ ]]
test -d "$repo_root/.git"
test -s "$scratch_root/metadata/download_manifest.tsv"
test -s "$scratch_root/benchmark_state.json"
test ! -e "$scratch_root/fastq"

state="$scratch_root/benchmark_state.json"
updater="$repo_root/benchmark/integrative/scripts/real/update_real_benchmark_state.py"
worker="$repo_root/benchmark/integrative/scripts/real/slurm_download_gse133183_sample.sh"
export HF_STATE_TIME_UTC
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$state" \
    --phase FASTQ_DOWNLOAD_PREPARED --status PREPARED \
    --workdir "$scratch_root/fastq" \
    --expected-output download_manifests/GSM4817452.execution.tsv \
    --expected-output download_manifests/GSM4817467.execution.tsv

job_id=$(sbatch --parsable \
    --job-name=hf-int-real-fastq \
    --array="1-16%${max_concurrent}" \
    --cpus-per-task=1 --mem=2G --time=18:00:00 \
    --output="$scratch_root/logs/download-%A_%a.out" \
    --error="$scratch_root/logs/download-%A_%a.err" \
    --export="ALL,HF_SCRATCH_ROOT=$scratch_root,HF_DOWNLOAD_MANIFEST=$scratch_root/metadata/download_manifest.tsv" \
    "$worker")
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$state" \
    --phase FASTQ_DOWNLOAD_SUBMITTED --status SUBMITTED \
    --job-id "$job_id" --job-kind fastq_download_array \
    --workdir "$scratch_root/fastq"
printf 'JOB_ID=%s\nARRAY=1-16%%%s\nSTATE=%s\n' "$job_id" "$max_concurrent" "$state"
