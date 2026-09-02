#!/usr/bin/env bash
#SBATCH --job-name=hf-int-rna-ref-fix
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901/logs/%x.%j.out
#SBATCH --error=/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901/logs/%x.%j.err
set -euo pipefail

repo=${1:?repository checkout is required}
root=${2:?benchmark root is required}
repo_commit=${3:?repository commit captured on the head node is required}
state="$root/benchmark_state.json"

update() {
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
        --state "$state" --phase "$1" --status "$2" --job-id "$SLURM_JOB_ID" \
        --job-kind rnaseq_reference_correction --repo-commit "$repo_commit" \
        --expected-output reference/transcriptome_normalization.json
}
trap 'update RNASEQ_REFERENCE_FIX_FAILED FAILED' ERR
update RNASEQ_REFERENCE_FIX_SUBMITTED RUNNING
python3 "$repo/benchmark/integrative/scripts/real/normalize_gse133183_transcriptome.py" \
    --root "$root" --repo-commit "$repo_commit"
update RNASEQ_REFERENCE_FIX_COMPLETE COMPLETE
trap - ERR
