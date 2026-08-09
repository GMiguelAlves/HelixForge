#!/usr/bin/env bash
set -euo pipefail

# Runs the same reduced module graph with one invalid compatibility input at a
# time. Each invocation must fail before a final BAM is published.
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
fixture="$root/tests/fixtures/native_chipseq_bam"
result="$root/tests/results/native_chipseq_bam/invalid"
input="$result/input"
mkdir -p "$input"
samtools view -b "$fixture/reads.sam" | samtools sort -o "$input/reads.bam" -
samtools index "$input/reads.bam"

run_expected_failure() {
    local name=$1 reference=$2 blacklist=$3
    if "$nextflow_bin" run "$root/tests/native_chipseq_bam/main.nf" \
        -c "$root/tests/native_chipseq_bam/nextflow.config" -ansi-log false \
        --bam "$input/reads.bam" --bai "$input/reads.bam.bai" \
        --reference "$reference" --blacklist "$blacklist" \
        --target_root "$result/$name/final" --outdir "$result/$name" \
        --trace_file "$result/$name/execution_trace.tsv"; then
        echo "ERROR: $name unexpectedly succeeded" >&2
        exit 1
    fi
}

run_expected_failure incompatible_reference "$fixture/reference_incompatible.fa" "$fixture/blacklist.bed"
run_expected_failure incompatible_blacklist "$fixture/reference.fa" "$fixture/blacklist_incompatible.bed"
printf 'native ChIP-seq BAM invalid-input tests: PASS\n'
