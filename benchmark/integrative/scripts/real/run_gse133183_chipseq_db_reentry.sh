#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/CLUSTER_USER/helixforge-integrative-post-qc-20260902}
root=${2:-/scratch/HELIXFORGE_WORKSPACE/helixforge-integrative-real-20260901}
queue=${3:-general}
case_root="$root/cases/chipseq_h3k27me3"
analysis=gse133183_h3k27me3.gse133183_h3k27me3.H3K27me3.H3K27me3.GRCh38.p14_GENCODE_50.broad
preflight="$case_root/work-runtime_path_fix/11/4426c4ff12c53475dda4d9ea164c5c"
counts_dir="$case_root/results/chipseq/differential_binding/$analysis/counts/$analysis.peak_counts"
output="$case_root/db_reentry_results"
work="$case_root/db_reentry_work"
logs="$case_root/logs"
nextflow_jar=/home/CLUSTER_USER/.nextflow/framework/25.10.7/nextflow-25.10.7-one.jar
java_runtime=/scratch/HELIXFORGE_WORKSPACE/helixforge-rnaseq-benchmark-20260825/envs/rna-tools-rc
python_runtime=/scratch/HELIXFORGE_WORKSPACE/helixforge-rnaseq-benchmark-20260825/envs/python-runtime-rc
r_runtime=/scratch/HELIXFORGE_WORKSPACE/helixforge-rnaseq-benchmark-20260825/envs/r-analysis-rc
chip_runtime=/home/CLUSTER_USER/miniconda3/envs/chipseq
config="$repo/benchmark/integrative/configs/real_upstream_slurm.config"

test -z "${SLURM_JOB_ID:-}"
test -s "$counts_dir/raw_peak_counts.tsv"
test -s "$counts_dir/count_spec.json"
test -s "$counts_dir/manifest.json"
test -s "$preflight/sample_tables/$analysis.tsv"
test -s "$preflight/model_specs/$analysis.model.json"
test -s "$preflight/contrast_specs/$analysis--GSK343_vs_DMSO.json"
test -s "$preflight/peak_universes/$analysis.bed"
test -s "$case_root/db_spec.json"
test -s "$config"
test -x "$java_runtime/bin/java"
test -x "$r_runtime/bin/Rscript"
test -x "$repo/benchmark/integrative/scripts/real/runtime/Rscript"
"$r_runtime/bin/Rscript" -e 'stopifnot(as.character(getRversion()) == "4.3.3", as.character(packageVersion("BiocVersion")) == "3.18.1", as.character(packageVersion("DESeq2")) == "1.42.0", as.character(packageVersion("jsonlite")) == "1.8.8")'

test ! -e "$output"
test ! -e "$work"
mkdir -p "$output" "$work" "$logs" "$case_root/db_reentry_nxf_home" "$case_root/db_reentry_nxf_cache"
runtime_path="$repo/benchmark/integrative/scripts/real/runtime:$chip_runtime/bin:$python_runtime/bin:/usr/bin:/bin"

cd "$repo"
env PATH="$runtime_path" \
    NXF_HOME="$case_root/db_reentry_nxf_home" \
    NXF_CACHE_DIR="$case_root/db_reentry_nxf_cache" \
    "$java_runtime/bin/java" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$logs/db_reentry.nextflow.log" \
    run benchmark/integrative/workflows/gse133183_chipseq_db_reentry.nf \
    -c "$config" \
    -ansi-log false \
    -work-dir "$work" \
    -process.queue="$queue" \
    --outdir "$output" \
    --chipseq_db_target_dir "$output/differential_binding" \
    --counts_dir "$counts_dir" \
    --count_spec "$counts_dir/count_spec.json" \
    --count_manifest "$counts_dir/manifest.json" \
    --sample_table "$preflight/sample_tables/$analysis.tsv" \
    --model_spec "$preflight/model_specs/$analysis.model.json" \
    --contrast_spec "$preflight/contrast_specs/$analysis--GSK343_vs_DMSO.json" \
    --peak_bed "$preflight/peak_universes/$analysis.bed" \
    --db_spec "$case_root/db_spec.json" \
    --db_model_queue "$queue" \
    --db_contrast_queue "$queue"

test -s "$output/pipeline_info/native_chipseq/differential_binding/aggregate/db_manifest.json"
test -s "$output/differential_binding/differential_binding_results/differential_binding_results.tsv"
