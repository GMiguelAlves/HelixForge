#!/usr/bin/env bash
#SBATCH --job-name=hf-multimark-manifest
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00

set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "This launcher must execute inside a Slurm job" >&2
  exit 2
fi
if [[ "$#" -ne 5 ]]; then
  echo "Usage: $0 PYTHON H3K27AC_MANIFEST H3K27ME3_MANIFEST OUTPUT_DIR GIT_COMMIT" >&2
  exit 2
fi

python_runtime="$1"
h3k27ac_manifest="$2"
h3k27me3_manifest="$3"
output_dir="$4"
git_commit="$5"

exec "$python_runtime" benchmark/integrative/scripts/real/prepare_gse133183_multimark_manifest.py \
  --h3k27ac-manifest "$h3k27ac_manifest" \
  --h3k27me3-manifest "$h3k27me3_manifest" \
  --output-dir "$output_dir" \
  --git-commit "$git_commit"
