#!/usr/bin/env bash

# Copy this file to config/user_settings.sh and edit only this small block.
# Leave config/pipeline_config.sh alone unless you need advanced behavior.

# 1) Name your analysis.
export PIPELINE_NAME="chipseq_project"
export ORGANISM_NAME="My organism"

# 2) Point to input data and metadata.
# FASTQ paths in config/metadata.tsv may be absolute or relative to FASTQ_DIR.
export FASTQ_DIR="/path/to/fastq"
export METADATA_FILE="${PROJECT_DIR}/config/metadata.tsv"

# 3) Provide reference files for the organism.
export REFERENCE_DIR="/path/to/reference"
export GENOME_FASTA="${REFERENCE_DIR}/genome.fa"
export ANNOTATION_FILE="${REFERENCE_DIR}/annotation.gtf"

# Optional organism/project annotations.
export BLACKLIST_BED=""
export EFFECTIVE_GENOME_SIZES=""
export FUNCTIONAL_ANNOTATION=""

# 4) Choose where outputs are written.
# OUTPUT_DIR is for light project outputs such as logs, copied configs, and reports.
# WORK_ROOT is for large work/results such as indexes, trimmed FASTQs, BAMs,
# peaks, tracks, and matrices. Keep WORK_ROOT on scratch for real analyses.
export OUTPUT_DIR="${PROJECT_DIR}"
export WORK_ROOT="${PROJECT_DIR}"
# Example for HPC:
# export WORK_ROOT="/scratch/my_user/chipseq_project"

# Large TSV-like results are written as .tsv.gz by default, like the RNA-seq
# pipeline. Set this to 0 only if you need plain text tables.
export PIPELINE_COMPRESS_RESULTS=1

# 5) Point to Conda on the Slurm server.
# Absolute paths are safest. Relative paths are resolved from this file's
# directory, so "../miniconda3" means "<project>/miniconda3".
export CONDA_BASE="/path/to/miniconda3"

# 6) Choose tools.
export ALIGNER="bowtie2"          # bowtie2 or bwa
export TRIM_TOOL="fastp"          # fastp or trim_galore
export PEAK_CALLER="macs3"        # macs3 or macs2
export PEAK_TYPE="auto"           # auto, narrow, or broad
# Set to true only when matched input/control FASTQs are not available.
# MACS will then run without -c for IP samples with an empty control_id.
export ALLOW_MISSING_CONTROLS="false"

# 7) Choose where jobs run.
export PIPELINE_EXECUTOR="slurm"  # Use "local" to run without sbatch.
export LOCAL_CPUS_PER_TASK=8      # Used only when PIPELINE_EXECUTOR="local".

# 8) Slurm resources.
export THREADS=8
export MEMORY="32G"
export SLURM_TIME="12:00:00"
# Leave empty unless your cluster requires a partition.
export SLURM_PARTITION=""
export SLURM_ACCOUNT=""
export SLURM_QOS=""

# 9) Conda environment names. Change only if your server uses other names.
export ENV_BACKEND="conda"
export CONDA_ENV="chipseq"
export CHIPSEQ_TOOLS_ENV="${CONDA_ENV}"
export PYTHON_ENV="${CONDA_ENV}"
export R_ANALYSIS_ENV="${CONDA_ENV}"

# 10) ChIP-seq parameters.
export READ_LAYOUT="metadata"     # metadata, paired, or single
export MIN_MAPQ=30
export REMOVE_DUPLICATES="true"
export PROMOTER_UPSTREAM=2000
export PROMOTER_DOWNSTREAM=500
export BIGWIG_NORMALIZATION="CPM"
export DIFF_CONTRASTS=""          # Example: treated:control,drug:vehicle
export MIN_REPLICATES_DIFF=2
export DIFF_PEAK_SET_SCOPE="mark_all" # mark_all uses MARK__all consensus sets for differential binding.

# 11) Slurm arrays and concurrency for sample-level jobs.
# array matches the RNA-seq pipeline style: one queued job array per step.
# individual keeps the older one-sbatch-per-sample behavior.
export SLURM_SAMPLE_SUBMISSION_MODE="array"

# These limits avoid running all samples at once. Increase only if your account
# and filesystem can handle it.
export QC_CONCURRENCY=8
export TRIM_CONCURRENCY=4
export ALIGN_CONCURRENCY=2
export FILTER_CONCURRENCY=2
export BAM_QC_CONCURRENCY=4
export PEAKS_CONCURRENCY=4
export TRACKS_CONCURRENCY=4

# 12) Storage mode.
# full: keep everything. Best for debugging and reruns.
# balanced: remove temporary uncompressed reference copies and individual
#           FastQC folders after the final report.
# minimal: also remove trimmed FASTQs after final BAMs/reports exist.
export PIPELINE_STORAGE_MODE="full"
