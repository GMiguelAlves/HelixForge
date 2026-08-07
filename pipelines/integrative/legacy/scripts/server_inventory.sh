#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/server_inventory.sh RNASEQ_RESULTS_DIR CHIPSEQ_RESULTS_DIR [CHIPSEQ_WORK_ROOT]

Run this on the server where the RNA-seq and ChIP-seq outputs exist. The script
prints the exact files the integration pipeline can consume.

Examples:
  bash scripts/server_inventory.sh /scratch/me/rnaseq_results /scratch/me/chipseq_results
  bash scripts/server_inventory.sh /scratch/me/rnaseq_results /home/me/chipseq_results /scratch/me/chipseq_work
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "$#" -lt 2 ]]; then
  usage
  exit 0
fi

RNASEQ_RESULTS_DIR="$1"
CHIPSEQ_RESULTS_DIR="$2"
CHIPSEQ_WORK_ROOT="${3:-$CHIPSEQ_RESULTS_DIR}"

find_first() {
  local root="$1"
  shift
  find "$root" "$@" -type f 2>/dev/null | sort | head -n 1 || true
}

find_many() {
  local root="$1"
  shift
  find "$root" "$@" -type f 2>/dev/null | sort || true
}

echo "## RNA-seq inputs"
printf 'RNA_COUNTS_MATRIX=%s\n' "$(find_first "$RNASEQ_RESULTS_DIR" -path '*/050-quantification/counts_matrix.tsv' -o -path '*/050-quantification/counts_matrix.tsv.gz')"
printf 'RNA_NORMALIZED_MATRIX=%s\n' "$(find_first "$RNASEQ_RESULTS_DIR" -path '*/050-quantification/tpm_matrix.tsv' -o -path '*/050-quantification/tpm_matrix.tsv.gz' -o -path '*/050-quantification/star_cpm_matrix.tsv' -o -path '*/050-quantification/star_cpm_matrix.tsv.gz')"
printf 'RNA_DEG_RESULTS=%s\n' "$(find_first "$RNASEQ_RESULTS_DIR" \
  -path '*/060-deg-analysis/DEGs_annotated_results.tsv' -o \
  -path '*/060-deg-analysis/DEGs_annotated_results.tsv.gz' -o \
  -path '*/060-deg-analysis/DEGs_results.tsv' -o \
  -path '*/060-deg-analysis/DEGs_results.tsv.gz' -o \
  -path '*/060-deg-analysis/all_projects/batch_corrected/DEGs_all_results.tsv' -o \
  -path '*/060-deg-analysis/all_projects/batch_corrected/DEGs_all_results.tsv.gz' -o \
  -path '*/060-deg-analysis/all_projects/raw/DEGs_all_results.tsv' -o \
  -path '*/060-deg-analysis/all_projects/raw/DEGs_all_results.tsv.gz' -o \
  -path '*/060-deg-analysis/all_projects/batch_corrected/DEGs_significant.tsv' -o \
  -path '*/060-deg-analysis/all_projects/batch_corrected/DEGs_significant.tsv.gz' -o \
  -path '*/060-deg-analysis/all_projects/raw/DEGs_significant.tsv' -o \
  -path '*/060-deg-analysis/all_projects/raw/DEGs_significant.tsv.gz')"
printf 'RNA_METADATA_FILE=%s\n' "$(find_first "$RNASEQ_RESULTS_DIR" -path '*/025-parse/030-metadata_final/AllProjects_metadata_new.csv' -o -path '*/025-parse/030-metadata_final/AllProjects_metadata.csv')"
printf 'RNA_GENE_CATALOG=%s\n' "$(find_first "$RNASEQ_RESULTS_DIR" -path '*/090-search-gene/results/tables/gene_catalog.tsv' -o -path '*/090-search-gene/results/tables/gene_catalog.tsv.gz')"

echo
echo "## ChIP-seq inputs"
printf 'CHIP_METADATA_FILE=%s\n' "$(find_first "$CHIPSEQ_RESULTS_DIR" -path '*/config/metadata.tsv' -o -path '*/config/metadata_srp034587_no_input.tsv')"
echo "CHIP_ANNOTATED_PEAKS:"
find_many "$CHIPSEQ_WORK_ROOT" -name '*.annotated.tsv' -o -name '*.annotated.tsv.gz'
echo "CHIP_CONSENSUS_BEDS:"
find_many "$CHIPSEQ_WORK_ROOT" -name '*.consensus.bed' -o -name '*.consensus.bed.gz'
echo "CHIP_PEAK_COUNTS:"
find_many "$CHIPSEQ_WORK_ROOT" -name '*.counts.tsv' -o -name '*.counts.tsv.gz'
printf 'CHIP_DIFF_BINDING_FILE=%s\n' "$(find_first "$CHIPSEQ_WORK_ROOT" -name 'differential_binding_results.tsv' -o -name 'differential_binding_results.tsv.gz')"

echo
echo "## Reference candidates"
find_many "$CHIPSEQ_WORK_ROOT" -name '*.gtf' -o -name '*.gtf.gz' -o -name '*.gff3' -o -name '*.gff3.gz' -o -name '*.fa' -o -name '*.fa.gz' | head -n 30
