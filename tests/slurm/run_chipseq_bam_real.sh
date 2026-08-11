#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-chipseq-bam-real}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
fixture_root="${repo_root}/tests/fixtures/native_chipseq_bam"
input_dir="${case_root}/input"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${chip_env}/bin:${conda_root}/envs/${rna_env}/bin:/usr/bin:/bin"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac

test -d "$repo_root/.git"
test -x "${conda_root}/envs/${rna_env}/bin/java"
test -x "${conda_root}/envs/${chip_env}/bin/samtools"
test -s "$validation_root/nextflow.jar"

metric() {
    local path=$1 name=$2
    awk -F '\t' -v key="$name" '$1 == key {print $2; exit}' "$path"
}

if [[ "$mode" == "prepare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    mkdir -p "$input_dir"
    env PATH="$runtime_path" samtools view -b "$fixture_root/reads.sam" \
        | env PATH="$runtime_path" samtools sort -@ 1 -o "$input_dir/reads.bam" -
    env PATH="$runtime_path" samtools index -@ 1 "$input_dir/reads.bam"
    env PATH="$runtime_path" samtools quickcheck "$input_dir/reads.bam"
    exit 0
fi

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    select_metrics="$nextflow_out/pipeline_info/native_chipseq/bam_select/rep_blacklist.bam_select_reports/metrics.tsv"
    duplicate_metrics="$nextflow_out/pipeline_info/native_chipseq/bam_duplicates/rep_blacklist.bam_duplicates_reports/metrics.tsv"
    blacklist_metrics="$nextflow_out/pipeline_info/native_chipseq/bam_blacklist/rep_blacklist.bam_blacklist_reports/metrics.tsv"
    no_blacklist_metrics="$nextflow_out/pipeline_info/native_chipseq/bam_blacklist/rep_no_blacklist.bam_blacklist_reports/metrics.tsv"

    [[ $(metric "$select_metrics" total_before) == 12 ]]
    [[ $(metric "$select_metrics" total_after) == 8 ]]
    [[ $(metric "$duplicate_metrics" duplicates_detected) == 2 ]]
    [[ $(metric "$duplicate_metrics" reads_after) == 6 ]]
    [[ $(metric "$blacklist_metrics" reads_removed) == 2 ]]
    [[ $(metric "$blacklist_metrics" reads_after) == 4 ]]
    [[ $(metric "$no_blacklist_metrics" blacklist_enabled) == false ]]
    [[ $(metric "$no_blacklist_metrics" reads_removed) == 0 ]]

    blacklisted_bam="$native_dir/rep_blacklist/rep_blacklist.filtered.bam"
    unfiltered_bam="$native_dir/rep_no_blacklist/rep_no_blacklist.filtered.bam"
    [[ $(env PATH="$runtime_path" samtools view -c "$blacklisted_bam") == 4 ]]
    [[ $(env PATH="$runtime_path" samtools view -c "$unfiltered_bam") == 8 ]]
    env PATH="$runtime_path" samtools quickcheck "$blacklisted_bam" "$unfiltered_bam"
    printf 'check\texpected\tobserved\tresult\nblacklist_reads\t4\t4\tPASS\nno_blacklist_reads\t8\t8\tPASS\nduplicate_reads\t2\t2\tPASS\n' \
        > "$case_root/comparison.tsv"
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver, prepare-job, or compare-job" >&2
    exit 2
fi
if [[ -e "$case_root" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root"
prepare_job=$(sbatch --wait --parsable \
    --job-name=hf-bam-prepare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 \
    --output="$case_root/slurm-prepare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    prepare-job "$case_name")
printf '%s\n' "$prepare_job" > "$case_root/prepare_job_id.txt"

mkdir -p "$native_dir" "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" \
    -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" \
    run tests/native_chipseq_bam/main.nf \
    -c tests/native_chipseq_bam/nextflow.config \
    -ansi-log false -process.executor=slurm -process.queue="$queue" \
    -executor.queueSize=1 -work-dir "$validation_root/work/$case_name" \
    --bam "$input_dir/reads.bam" --bai "$input_dir/reads.bam.bai" \
    --reference "$fixture_root/reference.fa" \
    --upstream_manifest "$fixture_root/alignment.manifest.json" \
    --blacklist "$fixture_root/blacklist.bed" \
    --target_root "$native_dir" --outdir "$nextflow_out" \
    --trace_file "$nextflow_out/execution_trace.tsv" \
    --bam_select_queue "$queue" --bam_duplicates_queue "$queue" \
    --bam_blacklist_queue "$queue" --bam_index_qc_queue "$queue"

compare_job=$(sbatch --wait --parsable \
    --job-name=hf-bam-compare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 \
    --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    compare-job "$case_name")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 && $3 != "-" {print $3}' "$nextflow_out/execution_trace.tsv" | paste -sd, -)
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw | awk 'NF {sum += $1} END {print sum + 0}')
printf 'implementation\telapsed_ms\tprocesses\nnative_bam_processing_slurm\t%s\t8\n' \
    "$((native_seconds * 1000))" > "$case_root/benchmark.tsv"

echo "[OK] Real ChIP-seq BAM processing Slurm validation passed."
echo "[OK] Case root: $case_root"
