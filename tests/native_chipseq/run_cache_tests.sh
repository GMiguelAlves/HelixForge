#!/usr/bin/env bash
set -euo pipefail

nextflow_bin=${NEXTFLOW_BIN:-nextflow}
outdir=tests/results/native_chipseq/cache
trace="$outdir/pipeline_info/execution_trace.tsv"

"$nextflow_bin" run . -profile test -stub-run -ansi-log false \
    --workflow chipseq --chipseq_run_mode alignment --outdir "$outdir"
"$nextflow_bin" run . -profile test -stub-run -resume -ansi-log false \
    --workflow chipseq --chipseq_run_mode alignment --outdir "$outdir"

grep -q $'\tCACHED\t' "$trace" || {
    echo "ERROR: resumed ChIP-seq stub did not report cached tasks" >&2
    exit 1
}

