#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?benchmark repository root is required}
python_bin=${2:?Python executable is required}
rscript_bin=${3:?Rscript executable is required}
scratch_root=${4:?benchmark scratch root is required}
output_dir=${5:?figure output directory is required}

test -n "${SLURM_JOB_ID:-}"
expected_scratch=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825
[[ "$(realpath "$scratch_root")" == "$expected_scratch" ]]
test ! -e "$output_dir"
mkdir -p "$output_dir/data"

scripts="$repo_root/benchmark/rnaseq/scripts/synthetic"
truth="$scratch_root/dataset/polyester-ground-truth-v1/truth"
results="$scratch_root/cases/synthetic-primary-run3/results"
validation="$scratch_root/validation"

"$python_bin" "$scripts/prepare_stage9b1_figures.py" \
    --truth-dir "$truth" \
    --tpm-matrix "$results/pipeline_info/native_import/tximport/tpm_matrix.tsv" \
    --de-results "$results/pipeline_info/native_de/aggregate/DEGs_all_results.tsv" \
    --metrics "$scratch_root/metrics/synthetic-primary-run3/synthetic_metrics.json" \
    --performance "$scratch_root/metrics/performance-summary.json" \
    --clean-comparison "$validation/helixforge-clean-repeat-comparison-v2.json" \
    --independent-comparison "$validation/independent-comparison-run3-v4-shared-index.json" \
    --reference-repeat-comparison "$validation/shared-index-repeat-comparison.json" \
    --output-dir "$output_dir/data"

"$rscript_bin" "$scripts/plot_stage9b1_figures.R" "$output_dir/data" "$output_dir"
{
    "$python_bin" --version
    "$rscript_bin" --version
} > "$output_dir/render_versions.txt" 2>&1
"$python_bin" "$scripts/finalize_stage9b1_figures.py" "$output_dir"
