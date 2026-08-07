#!/usr/bin/env bash

set -euo pipefail

nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

for workflow_name in rnaseq chipseq integrative all; do
    echo "[TEST] Stub workflow: ${workflow_name}"
    run_nextflow run . \
        -profile test \
        -stub-run \
        -ansi-log false \
        --workflow "${workflow_name}" \
        --outdir "results/test/${workflow_name}"
done
