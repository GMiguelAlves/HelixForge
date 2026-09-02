#!/usr/bin/env bash
#SBATCH --job-name=hf-int-rna-runtime
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901/logs/%x.%j.out
#SBATCH --error=/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901/logs/%x.%j.err
set -euo pipefail

repo=${1:?repository checkout is required}
root=${2:?benchmark root is required}
repo_commit=${3:?repository commit captured on the head node is required}
state="$root/benchmark_state.json"
case_root="$root/cases/rnaseq"

update() {
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
        --state "$state" --phase "$1" --status "$2" --job-id "$SLURM_JOB_ID" \
        --job-kind rnaseq_runtime_correction --repo-commit "$repo_commit" \
        --expected-output cases/rnaseq/runtime_correction.json
}
trap 'update RNASEQ_RUNTIME_FIX_FAILED FAILED' ERR
update RNASEQ_RUNTIME_FIX_SUBMITTED RUNNING
test -f /home/ra236875@bio.ib.unicamp.br/miniconda3/etc/profile.d/conda.sh
test -x /home/ra236875@bio.ib.unicamp.br/miniconda3/envs/python-list/bin/python
test -x /home/ra236875@bio.ib.unicamp.br/miniconda3/envs/r-analysis/bin/Rscript
test -x /home/ra236875@bio.ib.unicamp.br/miniconda3/envs/rna-tools/bin/salmon
python3 "$repo/benchmark/integrative/scripts/real/correct_gse133183_rnaseq_runtime.py" \
    --case-root "$case_root" --repository-commit "$repo_commit"
update RNASEQ_RUNTIME_FIX_COMPLETE COMPLETE
trap - ERR
