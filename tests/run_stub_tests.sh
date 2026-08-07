#!/usr/bin/env bash

set -euo pipefail

for workflow_name in rnaseq chipseq integrative all; do
    echo "[TEST] Stub workflow: ${workflow_name}"
    nextflow run . \
        -profile test \
        -stub-run \
        -ansi-log false \
        --workflow "${workflow_name}" \
        --outdir "results/test/${workflow_name}"
done

