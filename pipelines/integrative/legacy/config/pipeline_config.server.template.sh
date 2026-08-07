#!/usr/bin/env bash
# Copy to config/pipeline_config.local.sh on the server and edit the paths below.
# These paths must point to the server-side results, not to the local Windows
# working copies that only contain code/templates.

export RNASEQ_RESULTS_DIR="/path/on/server/rnaseq_results"
export CHIPSEQ_RESULTS_DIR="/path/on/server/chipseq_results"

# If the ChIP-seq pipeline uses WORK_ROOT outside the repository, point these
# directly to the heavy output directories.
export CHIP_METADATA_FILE="${CHIPSEQ_RESULTS_DIR}/config/metadata.tsv"
export CHIP_ANNOTATED_PEAKS_GLOB="/path/on/server/chipseq_work/090-peak-annotation/*.annotated.tsv*"
export CHIP_PEAK_BED_GLOB="/path/on/server/chipseq_work/110-consensus-peaks/groups/*.consensus.bed*"
export CHIP_PEAK_COUNT_GLOB="/path/on/server/chipseq_work/110-consensus-peaks/counts/*.counts.tsv*"
export CHIP_DIFF_BINDING_FILE="/path/on/server/chipseq_work/120-differential-binding/differential_binding_results.tsv.gz"

# Optional but strongly recommended for coordinate-based peak-gene rescue when
# annotated peak tables are absent.
export ANNOTATION_FILE="/path/on/server/reference/annotation.gtf.gz"
export GENOME_FASTA="/path/on/server/reference/genome.fa.gz"

# Optional curated machinery catalog, if it lives outside the RNA-seq pipeline.
export RNA_GENE_CATALOG_EXTRA="/path/on/server/results/tables/gene_catalog.tsv"

# Optional: override when the RNA metadata uses different life-cycle stage
# column names.
export RNA_STAGE_COLUMNS="stage,life_stage,lifecycle_stage,life_cycle_stage,developmental_stage,condition,treatment,tissue,source_name,title,description,characteristics_ch1"

export RUN_MODE="slurm"
