#!/usr/bin/env bash
set -euo pipefail

repo_root=${HF_REPO_ROOT:?HF_REPO_ROOT is required}
scratch_root=${HF_SCRATCH_ROOT:?HF_SCRATCH_ROOT is required}
array_job_id=${HF_ARRAY_JOB_ID:?HF_ARRAY_JOB_ID is required}
sacct_input=${HF_SACCT_INPUT:?HF_SACCT_INPUT is required}
python_bin=${HF_PYTHON_BIN:-python3}
test -n "${SLURM_JOB_ID:-}"
case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-*) ;;
    *) echo "unsafe scratch root: $scratch_root" >&2; exit 2 ;;
esac
audit="$scratch_root/download_validation"
test ! -e "$audit"
test -s "$sacct_input"
"$python_bin" "$repo_root/benchmark/integrative/scripts/real/finalize_gse133183_downloads.py" \
    --scratch-root "$scratch_root" \
    --download-manifest "$scratch_root/metadata/download_manifest.tsv" \
    --array-job-id "$array_job_id" \
    --sacct "$sacct_input" \
    --output-dir "$audit"
export HF_STATE_TIME_UTC
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$repo_root/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
    --state "$scratch_root/benchmark_state.json" \
    --phase FASTQ_DOWNLOAD_COMPLETE --status COMPLETE \
    --job-id "$array_job_id" --job-kind fastq_download_array \
    --expected-output download_validation/download_validation.json \
    --expected-output download_validation/fastq_inventory.tsv
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$repo_root/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
    --state "$scratch_root/benchmark_state.json" \
    --phase FASTQ_DOWNLOAD_COMPLETE --status COMPLETE \
    --job-id "$SLURM_JOB_ID" --job-kind download_validation
