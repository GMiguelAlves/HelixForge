#!/usr/bin/env bash
set -euo pipefail

nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
fixture="$root/tests/fixtures/native_chipseq_bam"
result="$root/tests/results/native_chipseq_bam/functional"
input="$result/input"

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

command -v samtools >/dev/null 2>&1 || {
    echo "SKIP: samtools is not available" >&2
    exit 77
}
case "$result" in
    "$root"/tests/results/native_chipseq_bam/functional) rm -rf "$result" ;;
    *) echo "Refusing to clean unexpected result path: $result" >&2; exit 2 ;;
esac
mkdir -p "$input"
samtools view -b "$fixture/reads.sam" | samtools sort -o "$input/reads.bam" -
samtools index "$input/reads.bam"

run_pipeline() {
    run_nextflow run "$root/tests/native_chipseq_bam/main.nf" \
        -c "$root/tests/native_chipseq_bam/nextflow.config" \
        -ansi-log false "$@" \
        --bam "$input/reads.bam" \
        --bai "$input/reads.bam.bai" \
        --reference "$fixture/reference.fa" \
        --upstream_manifest "$fixture/alignment.manifest.json" \
        --blacklist "$fixture/blacklist.bed" \
        --target_root "$result/final" \
        --outdir "$result" \
        --trace_file "$result/execution_trace.tsv"
}

run_pipeline
run_pipeline -resume

metric() {
    local path=$1 name=$2
    awk -F '\t' -v key="$name" '$1 == key {print $2; exit}' "$path"
}

select_metrics="$result/pipeline_info/native_chipseq/bam_select/rep_blacklist.bam_select_reports/metrics.tsv"
duplicate_metrics="$result/pipeline_info/native_chipseq/bam_duplicates/rep_blacklist.bam_duplicates_reports/metrics.tsv"
blacklist_metrics="$result/pipeline_info/native_chipseq/bam_blacklist/rep_blacklist.bam_blacklist_reports/metrics.tsv"
no_blacklist_metrics="$result/pipeline_info/native_chipseq/bam_blacklist/rep_no_blacklist.bam_blacklist_reports/metrics.tsv"

[[ $(metric "$select_metrics" total_before) == 12 ]]
[[ $(metric "$select_metrics" total_after) == 8 ]]
[[ $(metric "$duplicate_metrics" duplicates_detected) == 2 ]]
[[ $(metric "$duplicate_metrics" reads_after) == 6 ]]
[[ $(metric "$blacklist_metrics" reads_removed) == 2 ]]
[[ $(metric "$blacklist_metrics" reads_after) == 4 ]]
[[ $(metric "$no_blacklist_metrics" blacklist_enabled) == false ]]
[[ $(metric "$no_blacklist_metrics" reads_removed) == 0 ]]

[[ $(samtools view -c "$result/final/rep_blacklist/rep_blacklist.filtered.bam") == 4 ]]
[[ $(samtools view -c "$result/final/rep_no_blacklist/rep_no_blacklist.filtered.bam") == 8 ]]
samtools quickcheck "$result/final/rep_blacklist/rep_blacklist.filtered.bam"
samtools quickcheck "$result/final/rep_no_blacklist/rep_no_blacklist.filtered.bam"
grep -q $'\tCACHED\t' "$result/execution_trace.tsv"

printf 'native ChIP-seq BAM functional test: PASS\n'
