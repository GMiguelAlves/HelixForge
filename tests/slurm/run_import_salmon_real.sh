#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
r_env=${4:-r-analysis}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-import-salmon-real}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
fixture_root="${repo_root}/tests/fixtures/native_import"
legacy_root="${case_root}/legacy_root"
legacy_out="${case_root}/legacy"
native_out="${case_root}/native"
nextflow_out="${case_root}/nextflow"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${r_env}/bin:${conda_root}/envs/${rna_env}/bin:/usr/bin:/bin"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac

test -d "$repo_root/.git"
test -x "$conda_bin"
test -x "${conda_root}/envs/${rna_env}/bin/java"
test -x "${conda_root}/envs/${r_env}/bin/Rscript"
test -s "$validation_root/nextflow.jar"

if [[ "$mode" == "legacy-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    mkdir -p "$legacy_root/SYNTHETIC/sample_a" \
        "$legacy_root/SYNTHETIC/sample_b" "$legacy_out"
    cp "$fixture_root/salmon/sample_a/quant.sf" \
        "$legacy_root/SYNTHETIC/sample_a/"
    cp "$fixture_root/salmon/sample_b/quant.sf" \
        "$legacy_root/SYNTHETIC/sample_b/"
    cd "$case_root"
    env PATH="$runtime_path" Rscript \
        "$repo_root/pipelines/rnaseq/legacy/scripts/050-quantification/txtimport_quant.R" \
        --metadata "$fixture_root/metadata_single.csv" \
        --quant-root "$legacy_root" \
        --gtf "$fixture_root/annotation.gtf" \
        --output-dir "$legacy_out" \
        > "$case_root/legacy.log" 2>&1
    exit 0
fi

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    cp "$nextflow_out/pipeline_info/native_import/tximport/import_manifest.json" \
        "$native_out/import_manifest.json"
    env PATH="$runtime_path" python3 \
        "$repo_root/tests/native_import/compare_outputs.py" \
        "$legacy_out" "$native_out" --provider salmon \
        --output "$case_root/comparison.tsv"
    env PATH="$runtime_path" Rscript \
        "$repo_root/tests/native_import/validate_experiment.R" \
        "$native_out/summarized_experiment.rds" \
        "$native_out/counts_matrix.tsv" \
        "$native_out/tpm_matrix.tsv" \
        "$native_out/length_matrix.tsv" \
        "$native_out/quant_samples.tsv" \
        > "$case_root/experiment_validation.txt"
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver, legacy-job, or compare-job" >&2
    exit 2
fi
if [[ -e "$legacy_out" || -e "$native_out" || -e "$nextflow_out" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root"
legacy_job=$(sbatch --wait --parsable \
    --job-name=hf-import-legacy \
    --partition="$queue" \
    --cpus-per-task=1 \
    --mem=2G \
    --time=00:10:00 \
    --output="$case_root/slurm-legacy-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$r_env" "$queue" \
    legacy-job "$case_name")
printf '%s\n' "$legacy_job" > "$case_root/legacy_job_id.txt"

mkdir -p "$native_out" "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" \
    NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" \
    -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" \
    run tests/native_import/main.nf \
    -c tests/native_import/nextflow.config \
    -ansi-log false \
    -process.executor=slurm \
    -process.queue="$queue" \
    -executor.queueSize=1 \
    -work-dir "$validation_root/work/$case_name" \
    --provider salmon \
    --fixture_root "$fixture_root" \
    --metadata_file "$fixture_root/metadata_single.csv" \
    --target_root "$native_out" \
    --outdir "$nextflow_out" \
    --trace_file "$nextflow_out/execution_trace.tsv" \
    --tx2gene_queue "$queue" \
    --tximport_queue "$queue"

compare_job=$(sbatch --wait --parsable \
    --job-name=hf-import-compare \
    --partition="$queue" \
    --cpus-per-task=1 \
    --mem=2G \
    --time=00:05:00 \
    --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$r_env" "$queue" \
    compare-job "$case_name")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 { print $3 }' "$nextflow_out/execution_trace.tsv" \
    | paste -sd, -)
legacy_seconds=$(sacct -j "$legacy_job" -X -n -o ElapsedRaw \
    | awk 'NF { print $1; exit }')
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw \
    | awk 'NF { total += $1 } END { print total + 0 }')
printf 'implementation\telapsed_ms\ttest_threads\nlegacy_tximport_slurm\t%s\t1\nnextflow_import_api_tasks\t%s\t1\n' \
    "$((legacy_seconds * 1000))" "$((native_seconds * 1000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real Salmon legacy/Import API Slurm comparison passed."
echo "[OK] Case root: $case_root"
