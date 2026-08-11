#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
runtime_env=${3:-rna-tools}
queue=${4:-general}
mode=${5:-driver}
case_name=${6:-trim-real}
cache_dir=${7:-}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
input_dir="${case_root}/input"
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

if [[ -z "$cache_dir" ]]; then
    cache_dir="$repo_root/.nextflow"
fi
case "$cache_dir" in
    "$validation_root"/*|/tmp/helixforge-nextflow-cache-*) ;;
    *) echo "Refusing unexpected Nextflow cache path: $cache_dir" >&2; exit 2 ;;
esac

if [[ "$mode" == "legacy-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    mkdir -p "$input_dir" "$legacy_dir"
    gzip -n -c "$repo_root/tests/fixtures/trim_galore/input_R1.fastq" \
        > "$input_dir/input_R1.fastq.gz"
    gzip -n -c "$repo_root/tests/fixtures/trim_galore/input_R2.fastq" \
        > "$input_dir/input_R2.fastq.gz"

    "$conda_bin" run -n "$runtime_env" trim_galore --paired \
        --quality 20 \
        --length 20 \
        --cores 1 \
        --output_dir "$legacy_dir" \
        "$input_dir/input_R1.fastq.gz" \
        "$input_dir/input_R2.fastq.gz"

    mv "$legacy_dir/input_R1_val_1.fq.gz" \
        "$legacy_dir/synthetic_R1_trimmed.fastq.gz"
    mv "$legacy_dir/input_R2_val_2.fq.gz" \
        "$legacy_dir/synthetic_R2_trimmed.fastq.gz"
    exit 0
fi

if [[ "$mode" != "driver" && "$mode" != "resume" ]]; then
    echo "mode must be driver, resume, or legacy-job" >&2
    exit 2
fi

mkdir -p "$case_root"

if [[ "$mode" == "driver" ]]; then
    if [[ -e "$legacy_dir" || -e "$native_dir" || -e "$nextflow_out" ]]; then
        echo "Refusing to overwrite an existing validation case: $case_root" >&2
        exit 2
    fi

    legacy_start=$(date +%s%N)
    legacy_job=$(sbatch --wait --parsable \
        --job-name=hf-trim-legacy \
        --partition="$queue" \
        --cpus-per-task=1 \
        --mem=1G \
        --time=00:05:00 \
        --output="$case_root/slurm-legacy-%j.out" \
        "$0" "$validation_root" "$conda_bin" "$runtime_env" "$queue" \
        legacy-job "$case_name" "$cache_dir")
    legacy_end=$(date +%s%N)
    printf '%s\n' "$legacy_job" > "$case_root/legacy_job_id.txt"
    resume_args=()
else
    test -s "$case_root/legacy_job_id.txt"
    test -s "$native_dir/synthetic_R1_trimmed.fastq.gz"
    test -s "$native_dir/synthetic_R2_trimmed.fastq.gz"
    legacy_start=0
    legacy_end=0
    resume_args=(-resume)
fi

cd "$repo_root"
native_start=$(date +%s%N)
env NXF_HOME="$validation_root/.nextflow-home" \
    NXF_CACHE_DIR="$cache_dir" \
    "$conda_bin" run -n "$runtime_env" java \
    -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" \
    run tests/native_trim_galore/main.nf \
    -c tests/native_trim_galore/nextflow.config \
    "${resume_args[@]}" \
    -ansi-log false \
    -process.executor=slurm \
    -process.queue="$queue" \
    -work-dir "$validation_root/work/$case_name" \
    --read1 "$input_dir/input_R1.fastq.gz" \
    --read2 "$input_dir/input_R2.fastq.gz" \
    --target_dir "$native_dir" \
    --outdir "$nextflow_out"
native_end=$(date +%s%N)

if [[ "$mode" == "resume" ]]; then
    exit 0
fi

for mate in R1 R2; do
    legacy_file="$legacy_dir/synthetic_${mate}_trimmed.fastq.gz"
    native_file="$native_dir/synthetic_${mate}_trimmed.fastq.gz"
    gzip -t "$legacy_file"
    gzip -t "$native_file"
    legacy_content=$(gzip -dc "$legacy_file" | sha256sum | awk '{print $1}')
    native_content=$(gzip -dc "$native_file" | sha256sum | awk '{print $1}')
    [[ "$legacy_content" == "$native_content" ]]
    legacy_reads=$(gzip -dc "$legacy_file" | awk 'END { print NR / 4 }')
    native_reads=$(gzip -dc "$native_file" | awk 'END { print NR / 4 }')
    [[ "$legacy_reads" == "$native_reads" ]]
    printf '%s\t%s\t%s\n' "$mate" "$legacy_content" "$legacy_reads"
done > "$case_root/scientific_comparison.tsv"

for report in \
    input_R1.fastq.gz_trimming_report.txt \
    input_R2.fastq.gz_trimming_report.txt; do
    test -s "$legacy_dir/$report"
    test -s "$native_dir/$report"
    grep -E '^(Total reads processed|Reads with adapters|Reads written)' \
        "$legacy_dir/$report" > "$case_root/legacy.$report.stats"
    grep -E '^(Total reads processed|Reads with adapters|Reads written)' \
        "$native_dir/$report" > "$case_root/native.$report.stats"
    diff -u "$case_root/legacy.$report.stats" \
        "$case_root/native.$report.stats"
done

printf 'implementation\telapsed_ms\nlegacy_slurm\t%s\nnextflow_native_slurm\t%s\n' \
    "$(((legacy_end - legacy_start) / 1000000))" \
    "$(((native_end - native_start) / 1000000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real Trim Galore legacy/native Slurm comparison passed."
echo "[OK] Case root: $case_root"
