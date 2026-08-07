#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
fixture_root="${project_root}/tests/fixtures/native_quantification"
case_root="${project_root}/results/test/native-quantification-stub"

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

run_nextflow run "${project_root}/tests/native_quantification/main.nf" \
    -c "${project_root}/tests/native_quantification/nextflow.config" \
    -profile local -stub-run -ansi-log false \
    --transcriptome "${fixture_root}/transcriptome.fa" \
    --read1 "${fixture_root}/reads_R1.fastq" \
    --read2 "${fixture_root}/reads_R2.fastq" \
    --target_root "${case_root}/outputs" \
    --outdir "${case_root}/results"

test -s "${case_root}/outputs/quants/SYNTHETIC/synthetic_sample/quant.sf"
echo '[OK] Quantification API stub contract validated.'
