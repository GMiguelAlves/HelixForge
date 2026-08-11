#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
runtime_env=${3:-rna-tools}
queue=${4:-general}
mode=${5:-driver}
case_name=${6:-salmon-real}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
fixture_root="${repo_root}/tests/fixtures/native_quantification"
legacy_dir="${case_root}/legacy"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac

test -d "$repo_root/.git"
test -x "$conda_bin"
test -s "$validation_root/nextflow.jar"

if [[ "$mode" == "legacy-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    mkdir -p "$legacy_dir/index" "$legacy_dir/quant"
    "$conda_bin" run -n "$runtime_env" salmon index \
        -t "$fixture_root/transcriptome.fa" \
        -i "$legacy_dir/index" \
        -p 1 \
        -k 31 \
        > "$legacy_dir/salmon_index.log" 2>&1
    "$conda_bin" run -n "$runtime_env" salmon quant \
        -i "$legacy_dir/index" \
        -l A \
        -1 "$fixture_root/reads_R1.fastq" \
        -2 "$fixture_root/reads_R2.fastq" \
        -p 1 \
        --validateMappings \
        -o "$legacy_dir/quant" \
        > "$legacy_dir/salmon_quant.process.log" 2>&1
    exit 0
fi

finalize_case() {
    test -s "$case_root/legacy_job_id.txt"
    test -s "$nextflow_out/execution_trace.tsv"
    python3 "$repo_root/tests/native_quantification/compare_salmon_outputs.py" \
        "$legacy_dir/quant" \
        "$native_dir/quants/SYNTHETIC/synthetic_sample" \
        "$case_root/comparison.tsv"

    legacy_job=$(cat "$case_root/legacy_job_id.txt")
    native_jobs=$(awk 'NR > 1 { print $3 }' "$nextflow_out/execution_trace.tsv" \
        | paste -sd, -)
    legacy_seconds=$(sacct -j "$legacy_job" -X -n -o ElapsedRaw \
        | awk 'NF { print $1; exit }')
    native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw \
        | awk 'NF { total += $1 } END { print total + 0 }')
    legacy_bytes=$(du -sb "$legacy_dir/quant" | awk '{ print $1 }')
    native_bytes=$(du -sb "$native_dir/quants/SYNTHETIC/synthetic_sample" \
        | awk '{ print $1 }')
    printf 'implementation\telapsed_ms\toutput_bytes\ttest_threads\nlegacy_slurm\t%s\t%s\t1\nnextflow_native_slurm_tasks\t%s\t%s\t1\n' \
        "$((legacy_seconds * 1000))" "$legacy_bytes" \
        "$((native_seconds * 1000))" "$native_bytes" \
        > "$case_root/benchmark.tsv"

    echo "[OK] Real Salmon legacy/native Slurm comparison passed."
    echo "[OK] Case root: $case_root"
}

if [[ "$mode" == "finalize" ]]; then
    finalize_case
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver, finalize, or legacy-job" >&2
    exit 2
fi
if [[ -e "$legacy_dir" || -e "$native_dir" || -e "$nextflow_out" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root"
legacy_job=$(sbatch --wait --parsable \
    --job-name=hf-salmon-legacy \
    --partition="$queue" \
    --cpus-per-task=1 \
    --mem=1G \
    --time=00:10:00 \
    --output="$case_root/slurm-legacy-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$runtime_env" "$queue" \
    legacy-job "$case_name")
printf '%s\n' "$legacy_job" > "$case_root/legacy_job_id.txt"

mkdir -p "$native_dir" "$nextflow_out"
cd "$repo_root"
env NXF_HOME="$validation_root/.nextflow-home" \
    "$conda_bin" run -n "$runtime_env" java \
    -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" \
    run tests/native_quantification/main.nf \
    -c tests/native_quantification/nextflow.config \
    -ansi-log false \
    -process.executor=slurm \
    -process.queue="$queue" \
    -work-dir "$validation_root/work/$case_name" \
    --transcriptome "$fixture_root/transcriptome.fa" \
    --read1 "$fixture_root/reads_R1.fastq" \
    --read2 "$fixture_root/reads_R2.fastq" \
    --target_root "$native_dir" \
    --outdir "$nextflow_out" \
    --salmon_index_queue "$queue" \
    --salmon_quant_queue "$queue"

finalize_case
