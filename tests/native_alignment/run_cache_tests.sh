#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
case_root="${project_root}/results/test/native-alignment-cache-v6"
fixture_root="${project_root}/tests/fixtures/native_alignment"
input_dir="${case_root}/input"
launch_root=$(mktemp -d /tmp/omicsflow-native-alignment-cache.XXXXXX)

cleanup() {
    case "$launch_root" in
        /tmp/omicsflow-native-alignment-cache.*) rm -rf "$launch_root" ;;
        *) echo "Refusing to remove unsafe launch path: $launch_root" >&2 ;;
    esac
}
trap cleanup EXIT

case "$case_root" in
    "${project_root}"/results/test/*) ;;
    *) echo "Unsafe test path: $case_root" >&2; exit 2 ;;
esac
rm -rf "$case_root"

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

mkdir -p "$input_dir"
gzip -n -c "${fixture_root}/reads_R1.fastq" > "${input_dir}/reads_R1.fastq.gz"
gzip -n -c "${fixture_root}/reads_R2.fastq" > "${input_dir}/reads_R2.fastq.gz"
cd "$launch_root"

run_case() {
    local label=$1 extra_args=$2 resume_mode=$3
    local nextflow_args=(run "${project_root}/tests/native_alignment/main.nf" \
        -c "${project_root}/tests/native_alignment/nextflow.config" \
        -profile docker -ansi-log false \
        --reference "${fixture_root}/reference.fa" \
        --annotation "${fixture_root}/annotation.gtf" \
        --read1 "${input_dir}/reads_R1.fastq.gz" \
        --read2 "${input_dir}/reads_R2.fastq.gz" \
        --target_root "${case_root}/outputs" \
        --docker_bind_root "$case_root" \
        --extra_args "$extra_args" \
        --outdir "${case_root}/results" \
        --trace_file "${case_root}/current_trace.tsv")
    if [[ "$resume_mode" == true ]]; then
        nextflow_args+=(-resume)
    fi
    run_nextflow "${nextflow_args[@]}"
    mkdir -p "${case_root}/${label}"
    cp "${case_root}/current_trace.tsv" "${case_root}/${label}/execution_trace.tsv"
}

run_case baseline '--outTmpDir /tmp/omicsflow_star_tmp' false
run_case resumed '--outTmpDir /tmp/omicsflow_star_tmp' true
run_case changed_params '--outTmpDir /tmp/omicsflow_star_tmp --outFilterMismatchNmax 3' true

baseline_trace="${case_root}/baseline/execution_trace.tsv"
resumed_trace="${case_root}/resumed/execution_trace.tsv"
changed_trace="${case_root}/changed_params/execution_trace.tsv"
grep -q $'STAR_INDEX.*CACHED' "$resumed_trace"
grep -q $'STAR_ALIGN.*CACHED' "$resumed_trace"
grep -q $'STAR_INDEX.*CACHED' "$changed_trace"
grep -q $'STAR_ALIGN.*COMPLETED' "$changed_trace"

printf '@changed/1\nACGTACGTACGTACGTACGT\n+\nIIIIIIIIIIIIIIIIIIII\n' | gzip -n -c \
    >> "${input_dir}/reads_R1.fastq.gz"
printf '@changed/2\nACGTACGTACGTACGTACGT\n+\nIIIIIIIIIIIIIIIIIIII\n' | gzip -n -c \
    >> "${input_dir}/reads_R2.fastq.gz"
run_case changed_reads '--outTmpDir /tmp/omicsflow_star_tmp --outFilterMismatchNmax 3' true
changed_reads_trace="${case_root}/changed_reads/execution_trace.tsv"
grep -q $'STAR_INDEX.*CACHED' "$changed_reads_trace"
grep -q $'STAR_ALIGN.*COMPLETED' "$changed_reads_trace"

echo '[OK] Cache reuse and parameter/read invalidation validated.'
