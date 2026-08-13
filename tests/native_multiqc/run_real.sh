#!/usr/bin/env bash

set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW:-nextflow}
image=${MULTIQC_TEST_IMAGE:-quay.io/biocontainers/multiqc:1.17--pyhdfd78af_1}
case_root=${MULTIQC_TEST_ROOT:-$(mktemp -d "${TMPDIR:-/tmp}/helixforge-multiqc.XXXXXX")}

mkdir -p "$case_root/results" "$case_root/out" "$case_root/work" "$case_root/nxf-home"

NXF_HOME="$case_root/nxf-home" "$nextflow_bin" run "$root/tests/native_multiqc/main.nf" \
    -c "$root/tests/native_multiqc/nextflow.config" \
    -ansi-log false \
    -work-dir "$case_root/work" \
    --input_dir "$root/tests/fixtures/native_multiqc" \
    --target_root "$case_root/results" \
    --outdir "$case_root/out" \
    --multiqc_container "$image"

python3 "$root/tests/native_multiqc/validate_real.py" --root "$case_root"
printf '[OK] MultiQC real certification: %s\n' "$case_root/certification.json"
