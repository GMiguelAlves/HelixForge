#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
image=${SALMON_CONTAINER:-quay.io/biocontainers/salmon@sha256:f83ebb158845ee8138d793347f83b92c75e83c58dd8f4600c6fea2a2453ef08e}
case_root="${project_root}/results/test/native-quantification-cache"
fixture_root="${project_root}/tests/fixtures/native_quantification"
input_dir="${case_root}/input"
launch_root=$(mktemp -d /tmp/omicsflow-native-quantification-cache.XXXXXX)

cleanup() {
    case "$launch_root" in
        /tmp/omicsflow-native-quantification-cache.*)
            docker run --rm -v "${launch_root}:/cleanup" "$image" \
                chmod -R a+rwX /cleanup >/dev/null 2>&1 || true
            rm -rf "$launch_root" || true
            ;;
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
cp "${fixture_root}/transcriptome.fa" "${input_dir}/transcriptome.fa"
cp "${fixture_root}/reads_R1.fastq" "${input_dir}/reads_R1.fastq"
cp "${fixture_root}/reads_R2.fastq" "${input_dir}/reads_R2.fastq"
cd "$launch_root"

run_case() {
    local label=$1 lib_type=$2 resume_mode=$3
    local nextflow_args=(run "${project_root}/tests/native_quantification/main.nf" \
        -c "${project_root}/tests/native_quantification/nextflow.config" \
        -profile docker -ansi-log false \
        --transcriptome "${input_dir}/transcriptome.fa" \
        --read1 "${input_dir}/reads_R1.fastq" \
        --read2 "${input_dir}/reads_R2.fastq" \
        --target_root "${case_root}/outputs" \
        --docker_bind_root "$case_root" \
        --lib_type "$lib_type" \
        --outdir "${case_root}/results" \
        --trace_file "${case_root}/current_trace.tsv")
    [[ "$resume_mode" == true ]] && nextflow_args+=(-resume)
    run_nextflow "${nextflow_args[@]}"
    mkdir -p "${case_root}/${label}"
    cp "${case_root}/current_trace.tsv" "${case_root}/${label}/execution_trace.tsv"
}

run_case baseline A false
run_case resumed A true
grep -q $'SALMON_INDEX.*CACHED' "${case_root}/resumed/execution_trace.tsv"
grep -q $'SALMON_QUANT.*CACHED' "${case_root}/resumed/execution_trace.tsv"

run_case changed_params IU true
grep -q $'SALMON_INDEX.*CACHED' "${case_root}/changed_params/execution_trace.tsv"
grep -q $'SALMON_QUANT.*COMPLETED' "${case_root}/changed_params/execution_trace.tsv"

printf '@changed/1\nTCGTGAATTTGAGCTTATCAAGTTGCGGGGTCAACATGTCACACCTTATG\n+\nIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n' \
    >> "${input_dir}/reads_R1.fastq"
printf '@changed/2\nAACCACATCCGGCCGCTAAGGTCCGACAACCGTACAATAGGTCCCCGGGC\n+\nIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n' \
    >> "${input_dir}/reads_R2.fastq"
run_case changed_reads IU true
grep -q $'SALMON_INDEX.*CACHED' "${case_root}/changed_reads/execution_trace.tsv"
grep -q $'SALMON_QUANT.*COMPLETED' "${case_root}/changed_reads/execution_trace.tsv"

printf '>tx_added\nACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT\n' \
    >> "${input_dir}/transcriptome.fa"
run_case changed_transcriptome IU true
grep -q $'SALMON_INDEX.*COMPLETED' "${case_root}/changed_transcriptome/execution_trace.tsv"
grep -q $'SALMON_QUANT.*COMPLETED' "${case_root}/changed_transcriptome/execution_trace.tsv"

echo '[OK] Salmon index and quantification cache invalidation validated.'
