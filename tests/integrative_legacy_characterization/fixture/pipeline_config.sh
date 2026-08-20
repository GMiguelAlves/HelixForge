#!/usr/bin/env bash

set -euo pipefail

fixture_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && (pwd -W 2>/dev/null || pwd))"
repo_root="$(cd "${fixture_dir}/../../.." && (pwd -W 2>/dev/null || pwd))"
input_dir="${fixture_dir}/inputs"

export PROJECT_DIR="${repo_root}/pipelines/integrative/legacy"
export INTEGRATION_OUTPUT_DIR="${INTEGRATION_OUTPUT_DIR:-${fixture_dir}/../wrapper-actual}"

export RNA_COUNTS_MATRIX="${input_dir}/counts_matrix.tsv"
export RNA_NORMALIZED_MATRIX="${input_dir}/tpm_matrix.tsv"
export RNA_DEG_RESULTS="${input_dir}/deg_results.tsv"
export RNA_METADATA_FILE="${input_dir}/rna_metadata.tsv"
export RNA_GENE_CATALOG="${input_dir}/gene_catalog.tsv"
export RNA_GENE_CATALOG_EXTRA=""
export RNA_EXPRESSION_CONTEXT=""
export RNA_WGCNA_HITS="${input_dir}/wgcna_hits.tsv"
export RNA_MFUZZ_HITS="${input_dir}/mfuzz_hits.tsv"
export RNA_DTU_HITS="${input_dir}/dtu_hits.tsv"
export RNA_SPLICING_HITS="${input_dir}/splicing_hits.tsv"

export CHIP_METADATA_FILE="${input_dir}/chip_metadata.tsv"
export CHIP_ANNOTATED_PEAKS_GLOB="${input_dir}/annotated_peaks*.tsv"
export CHIP_PEAK_BED_GLOB="${input_dir}/unused/*.bed"
export CHIP_PEAK_COUNT_GLOB="${input_dir}/unused/*.counts.tsv"
export CHIP_DIFF_BINDING_FILE="${input_dir}/differential_binding.tsv"

export GENOME_FASTA="${input_dir}/genome.fa"
export ANNOTATION_FILE="${input_dir}/annotation.gtf"
export FUNCTIONAL_ANNOTATION="${input_dir}/functional_annotation.tsv"
export GENES_OF_INTEREST_FILE="${input_dir}/genes_of_interest.txt"

export GENE_ID_COLUMN="gene_id"
export GENE_NAME_COLUMN="gene_name"
export SAMPLE_ID_COLUMN="sample_id"
export GROUP_COLUMNS="stage,condition"
export RNA_STAGE_COLUMNS="stage,condition"
export CONTRAST_ID_COLUMN="contrast_id"
export MARK_COLUMN="mark_or_factor"
export CONDITION_COLUMN="condition"

export PEAK_GENE_WINDOW_BP="5000"
export PROMOTER_UPSTREAM_BP="2000"
export PROMOTER_DOWNSTREAM_BP="500"
export DEG_PADJ_THRESHOLD="0.05"
export DEG_LOG2FC_THRESHOLD="1"
export DIFF_BINDING_PADJ_THRESHOLD="0.05"
export DIFF_BINDING_LOG2FC_THRESHOLD="1"
export TOP_CANDIDATES_N="4"
export GENE_PANEL_TOP_N="0"

export RUN_MODE="local"
export PYTHON_BIN="${PYTHON_BIN:-python}"
export RSCRIPT_BIN="${RSCRIPT_BIN:-Rscript}"
export ENV_BACKEND="none"
export OVERWRITE="true"
export CREATE_DONE_FILES="true"
