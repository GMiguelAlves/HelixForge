#!/usr/bin/env bash
#SBATCH --job-name=hf-gse52778-finalize
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00

set -euo pipefail

if [[ $# -ne 7 ]]; then
    echo "usage: $0 CASE_ROOT INDEPENDENT_ROOT REPOSITORY RSCRIPT PYTHON DOWNLOAD_ROOT REFERENCE_ROOT" >&2
    exit 2
fi

case_root=$1
independent_root=$2
repository=$3
rscript=$4
python=$5
download_root=$6
reference_root=$7
scripts="$repository/benchmark/rnaseq/scripts/gse52778"
validation="$case_root/validation"

"$rscript" "$scripts/plot_gse52778_benchmark.R" \
    --helix-de "$case_root/pipeline/060-deg-analysis/benchmark_airway_primary/DEGs_all_results.tsv" \
    --reference-de "$independent_root/analysis/de_results.tsv" \
    --qc "$validation/sample_qc.tsv" \
    --biology "$validation/biological-expectations.tsv" \
    --pca "$case_root/pipeline/060-deg-analysis/benchmark_airway_primary/plots/PCA_condition.png" \
    --output-dir "$validation/figures"

"$python" "$scripts/summarize_gse52778_performance.py" \
    --case-root "$case_root" \
    --independent-root "$independent_root" \
    --download-root "$download_root" \
    --reference-root "$reference_root" \
    --external-job 15986 \
    --external-job 15988 \
    --sacct-file "$validation/external_jobs.sacct.tsv" \
    --output "$validation/performance_summary.json" \
    --table-output "$validation/performance_summary.tsv"
