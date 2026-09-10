#!/usr/bin/env bash
#SBATCH --job-name=hf-db-evidence
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=02:00:00

set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "This launcher must execute inside a Slurm job" >&2
  exit 2
fi
if [[ "$#" -ne 10 ]]; then
  echo "Usage: $0 PYTHON TERMINAL_MANIFEST REFERENCE_MANIFEST FASTA GTF CONTEXT_VALIDATOR ANNOTATOR OUTPUT_DIR MARK GIT_COMMIT" >&2
  exit 2
fi

exec "$1" benchmark/integrative/scripts/real/prepare_differential_binding_evidence.py \
  --terminal-manifest "$2" \
  --reference-manifest "$3" \
  --reference "$4" \
  --annotation "$5" \
  --context-validator "$6" \
  --annotator "$7" \
  --output-dir "$8" \
  --mark "$9" \
  --git-commit "${10}"
