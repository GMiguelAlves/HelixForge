#!/usr/bin/env bash
#SBATCH --job-name=hf-int-evaluate
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00

set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "This launcher must execute inside a Slurm job" >&2
  exit 2
fi
if [[ "$#" -ne 6 ]]; then
  echo "Usage: $0 PYTHON RESULTS_DIR TRACE GTF OUTPUT_DIR GIT_COMMIT" >&2
  exit 2
fi

exec "$1" benchmark/integrative/scripts/real/evaluate_gse133183_integration.py \
  --results-dir "$2" \
  --trace "$3" \
  --annotation "$4" \
  --output-dir "$5" \
  --git-commit "$6"
