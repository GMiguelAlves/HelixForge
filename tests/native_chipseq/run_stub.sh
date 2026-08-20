#!/usr/bin/env bash
set -euo pipefail

nextflow_bin=${NEXTFLOW_BIN:-nextflow}

"$nextflow_bin" run . \
    -profile test \
    -stub-run \
    -ansi-log false \
    --workflow chipseq \
    --chipseq_run_mode alignment \
    --outdir tests/results/native_chipseq/stub
