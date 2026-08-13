#!/usr/bin/env bash

# Copy this file to config/user_settings.sh and edit only this small block.
# Leave config/pipeline_config.sh alone unless you need advanced behavior.

# 1) Name your analysis.
export PIPELINE_NAME="rnaseq_project"
export ORGANISM_NAME="My organism"

# 2) List the ENA/SRA projects to process.
# Use spaces or commas.
export PIPELINE_PROJECTS="PRJXXXX PRJYYYY"

# 3) Set the scratch/work directory on the Slurm server.
export SCRATCH_ROOT="/scratch/my_user/rnaseq_project"

# 4) Point to Conda on the Slurm server.
export CONDA_BASE="/path/to/miniconda3"

# 5) Provide reference inputs.
# Option A: URLs. The pipeline downloads and decompresses them.
export GENOME_URL="https://example.org/genome.fa.gz"
export TRANSCRIPTS_URL="https://example.org/transcripts.fa.gz"
export GFF3_URL="https://example.org/annotation.gff3.gz"
# If your organism provides GTF instead of GFF3, use this line instead.
# export GTF_URL="https://example.org/annotation.gtf.gz"

# Option B: local files already present on the server.
# If using local files, uncomment and edit these instead of the URLs above.
# export REF_GENOME_FA="/path/to/genome.fa"
# export REF_TRANSCRIPTS_FA="/path/to/transcripts.fa"
# export REF_GFF3="/path/to/annotation.gff3"
# export REF_GTF="/path/to/annotation.gtf"

# 6) Choose the quantification method.
# salmon: transcript-level quantification, imported with tximport.
# star: genome alignment plus STAR GeneCounts. Needs genome + GTF/GFF3.
export QUANT_METHOD="salmon"       # Use "salmon" or "star".
export STAR_GENECOUNT_COLUMN="unstranded"

# 7) Choose where jobs run.
export PIPELINE_EXECUTOR="slurm"   # Use "local" to run without sbatch/squeue.
export LOCAL_CPUS_PER_TASK=8       # Used only when PIPELINE_EXECUTOR="local".

# 8) Usually keep these defaults.
if [[ "$QUANT_METHOD" == "star" ]]; then
  export RUN_SALMON_INDEX=0
  export RUN_STAR_GTF_INDEX=1
else
  export RUN_SALMON_INDEX=1
  export RUN_STAR_GTF_INDEX=0
fi
export RUN_STAR_INDEX=0
export RUN_BATCH_CORRECTION=0
export RUN_GENE_REPORT=0

# 9) Conda environment names. Change only if your server uses other names.
export RNA_TOOLS_ENV="rna-tools"
export PYTHON_ENV="python-list"
export R_ANALYSIS_ENV="r-analysis"
export BATCH_CORRECTION_ENV="batch-correction"
