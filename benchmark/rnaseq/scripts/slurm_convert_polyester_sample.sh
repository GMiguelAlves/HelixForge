#!/usr/bin/env bash
set -euo pipefail

python=${1:?Python is required}
converter=${2:?converter script is required}
candidate=${3:?candidate directory is required}
test -n "${SLURM_JOB_ID:-}"
task=${SLURM_ARRAY_TASK_ID:?array task ID is required}

sample=$(awk -F '\t' -v row="$((task + 1))" 'NR == row {print $1}' "$candidate/truth/sample_table.tsv")
test -n "$sample"
mkdir -p "$candidate/fastq" "$candidate/conversion_manifests"
"$python" "$converter" \
    --r1-fasta "$candidate/polyester_fasta/${sample}_R1.fasta" \
    --r2-fasta "$candidate/polyester_fasta/${sample}_R2.fasta" \
    --r1-fastq "$candidate/fastq/${sample}_R1.fastq.gz" \
    --r2-fastq "$candidate/fastq/${sample}_R2.fastq.gz" \
    --quality I \
    --manifest "$candidate/conversion_manifests/${sample}.json"

