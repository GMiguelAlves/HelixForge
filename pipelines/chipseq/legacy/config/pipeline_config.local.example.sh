#!/usr/bin/env bash
# Backward-compatible local config example.
# Prefer using:
#   cp config/user_settings_template.sh config/user_settings.sh

FASTQ_DIR="/path/to/fastq"
REFERENCE_DIR="/path/to/reference"
GENOME_FASTA="${REFERENCE_DIR}/genome.fa"
ANNOTATION_FILE="${REFERENCE_DIR}/annotation.gtf"
METADATA_FILE="${PROJECT_DIR}/config/metadata.tsv"
OUTPUT_DIR="${PROJECT_DIR}"
WORK_ROOT="${PROJECT_DIR}"

PIPELINE_EXECUTOR="slurm"
THREADS="16"
MEMORY="48G"
SLURM_TIME="24:00:00"
SLURM_PARTITION=""
SLURM_ACCOUNT=""

ENV_BACKEND="conda"
CONDA_ENV="chipseq"

ALIGNER="bowtie2"
TRIM_TOOL="fastp"
PEAK_CALLER="macs3"
PEAK_TYPE="auto"
