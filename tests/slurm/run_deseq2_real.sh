#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
r_env=${4:-r-analysis}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-deseq2-real}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
fixture_root="${repo_root}/tests/fixtures/native_de"
legacy_out="${case_root}/legacy"
native_out="${case_root}/native"
nextflow_out="${case_root}/nextflow"
trace_file="${nextflow_out}/pipeline_info/execution_trace.tsv"
analysis_spec="${case_root}/analysis_spec.json"
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
    mkdir -p "$legacy_out"
    cd "$case_root"
    env PATH="$runtime_path" Rscript \
        "$repo_root/pipelines/rnaseq/legacy/scripts/060-deg-analysis/deseq2_analysis.R" \
        --counts "$fixture_root/counts_matrix.tsv" \
        --samples "$fixture_root/quant_samples.tsv" \
        --gff "$fixture_root/annotation.gff" \
        --output-dir "$legacy_out" \
        --analysis-id golden \
        --test-variables condition \
        --design-covariates batch
    exit 0
fi

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python3 \
        "$repo_root/tests/native_de/compare_results.py" \
        "$legacy_out" "$native_out" \
        > "$case_root/comparison.txt"
    exit 0
fi

finalize_case() {
    test -s "$case_root/comparison.txt"
    test -s "$trace_file"
    legacy_job=$(cat "$case_root/legacy_job_id.txt")
    native_jobs=$(awk 'NR > 1 { print $3 }' "$trace_file" | paste -sd, -)
    legacy_seconds=$(sacct -j "$legacy_job" -X -n -o ElapsedRaw \
        | awk 'NF { print $1; exit }')
    native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw \
        | awk 'NF { total += $1 } END { print total + 0 }')
    printf 'implementation\telapsed_ms\ttest_threads\nlegacy_deseq2_slurm\t%s\t1\nnextflow_de_api_tasks\t%s\t1\n' \
        "$((legacy_seconds * 1000))" "$((native_seconds * 1000))" \
        > "$case_root/benchmark.tsv"

    echo "[OK] Real DESeq2 legacy/DE API Slurm comparison passed."
    echo "[OK] Case root: $case_root"
}

if [[ "$mode" == "finalize" ]]; then
    finalize_case
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver, legacy-job, compare-job, or finalize" >&2
    exit 2
fi
if [[ -e "$legacy_out" || -e "$native_out" || -e "$nextflow_out" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root"
python3 - "$fixture_root/analysis_spec.json" "$analysis_spec" "$native_out" <<'PY'
import json
import sys
from pathlib import Path

source, target, output = map(Path, sys.argv[1:])
document = json.loads(source.read_text(encoding="utf-8"))
document["target_dir"] = str(output)
target.write_text(json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8")
PY

legacy_job=$(sbatch --wait --parsable \
    --job-name=hf-de-legacy \
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
    run tests/native_de/main.nf \
    -profile test \
    -ansi-log false \
    -process.executor=slurm \
    -process.queue="$queue" \
    -process.memory=2GB \
    -executor.queueSize=1 \
    -work-dir "$validation_root/work/$case_name" \
    --de_analysis_spec "$analysis_spec" \
    --de_target_dir "$native_out" \
    --outdir "$nextflow_out" \
    --deseq2_model_queue "$queue" \
    --deseq2_contrast_queue "$queue"

compare_job=$(sbatch --wait --parsable \
    --job-name=hf-de-compare \
    --partition="$queue" \
    --cpus-per-task=1 \
    --mem=1G \
    --time=00:05:00 \
    --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$r_env" "$queue" \
    compare-job "$case_name")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

finalize_case
